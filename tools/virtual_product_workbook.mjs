import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


function columnName(index) {
  let value = index + 1;
  let result = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    value = Math.floor((value - 1) / 26);
  }
  return result;
}


function tableName(sheetName) {
  const names = {
    "方案数据": "VirtualSchemes",
    "属性配置": "VirtualAttributes",
    "耦合关系": "VirtualCouplings",
    "新技术协议": "VirtualProtocol",
  };
  return names[sheetName];
}


function styleSheet(sheet, rows) {
  const rowCount = rows.length;
  const columnCount = Math.max(...rows.map((row) => row.length));
  const lastColumn = columnName(columnCount - 1);
  const used = sheet.getRange(`A1:${lastColumn}${rowCount}`);
  used.format.font = { name: "Microsoft YaHei", size: 10, color: "#243447" };
  used.format.verticalAlignment = "center";

  const header = sheet.getRange(`A1:${lastColumn}1`);
  header.format = {
    fill: "#155E75",
    font: { name: "Microsoft YaHei", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "medium", color: "#0E4F63" },
    rowHeight: 30,
  };
  if (rowCount > 1) {
    sheet.getRange(`A2:${lastColumn}${rowCount}`).format.borders = {
      insideHorizontal: { style: "thin", color: "#DCE6EA" },
    };
  }
  sheet.freezePanes.freezeRows(1);
  sheet.showGridLines = false;

  for (let column = 0; column < columnCount; column += 1) {
    const maxLength = Math.max(
      ...rows.slice(0, Math.min(rows.length, 80)).map((row) =>
        String(row[column] ?? "").length
      )
    );
    const width = Math.min(Math.max(maxLength + 2, 11), column === columnCount - 1 ? 38 : 24);
    sheet.getRangeByIndexes(0, column, rowCount, 1).format.columnWidth = width;
  }
  if (tableName(sheet.name)) {
    const table = sheet.tables.add(`A1:${lastColumn}${rowCount}`, true, tableName(sheet.name));
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
    table.showFilterButton = true;
  }
}


export async function buildVirtualEffectivenessWorkbook(payloadPath, outputPath) {
  const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
  const workbook = Workbook.create();
  for (const [sheetName, rows] of Object.entries(payload.sheets)) {
    const sheet = workbook.worksheets.add(sheetName);
    const rowCount = rows.length;
    const columnCount = Math.max(...rows.map((row) => row.length));
    sheet.getRangeByIndexes(0, 0, rowCount, columnCount).values = rows.map((row) => {
      const padded = [...row];
      while (padded.length < columnCount) padded.push(null);
      return padded;
    });
    styleSheet(sheet, rows);
    if (sheetName === "生成说明" || sheetName === "项目信息") {
      sheet.getRange(`A1:A${rowCount}`).format = {
        fill: "#E6F4F7",
        font: { name: "Microsoft YaHei", bold: true, color: "#155E75" },
      };
      sheet.getRange(`B1:B${rowCount}`).format.wrapText = true;
      sheet.getRange(`B1:B${rowCount}`).format.columnWidth = 58;
      sheet.getRange(`A1:B${rowCount}`).format.rowHeight = 32;
      sheet.getRange(`A1:B${rowCount}`).format.borders = {
        insideHorizontal: { style: "thin", color: "#C8DDE3" },
        top: { style: "thin", color: "#8FB8C4" },
        bottom: { style: "thin", color: "#8FB8C4" },
        left: { style: "thin", color: "#8FB8C4" },
        right: { style: "thin", color: "#8FB8C4" },
      };
    }
    if (sheetName === "新技术协议") {
      const protocolLastColumn = columnName(columnCount - 1);
      sheet.getRange("B1:B2").format.columnWidth = 28;
      sheet.getRange(`${protocolLastColumn}1:${protocolLastColumn}2`).format.columnWidth = 60;
      sheet.getRange(`B2:${protocolLastColumn}2`).format.wrapText = true;
      sheet.getRange(`A2:${protocolLastColumn}2`).format.rowHeight = 32;
    }
  }

  const schemeSheet = workbook.worksheets.getItem("方案数据");
  const schemeLastRow = payload.sheets["方案数据"].length;
  const controlFieldIndex = 3 + 10;
  const controlColumn = columnName(controlFieldIndex);
  schemeSheet.getRange(`${controlColumn}2:${controlColumn}${schemeLastRow}`).dataValidation = {
    rule: { type: "list", values: ["电动", "液压", "电液混合"] },
  };
  const overloadColumn = columnName(3 + 4);
  schemeSheet.getRange(`${overloadColumn}2:${overloadColumn}${schemeLastRow}`).dataValidation = {
    rule: { type: "list", values: [0, 1] },
  };

  const outputDir = path.dirname(outputPath);
  const previewDir = path.join(outputDir, "workbook_previews");
  await fs.mkdir(previewDir, { recursive: true });

  const inspection = await workbook.inspect({
    kind: "workbook,sheet,table",
    maxChars: 9000,
    tableMaxRows: 6,
    tableMaxCols: 16,
    tableMaxCellChars: 80,
  });
  await fs.writeFile(path.join(outputDir, "workbook_inspection.ndjson"), inspection.ndjson, "utf8");
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "virtual effectiveness workbook formula error scan",
  });
  await fs.writeFile(path.join(outputDir, "workbook_formula_errors.ndjson"), errors.ndjson, "utf8");

  for (const sheetName of Object.keys(payload.sheets)) {
    const preview = await workbook.render({
      sheetName,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(previewDir, `${sheetName}.png`),
      new Uint8Array(await preview.arrayBuffer())
    );
  }

  await fs.mkdir(outputDir, { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  return {
    outputPath,
    sheets: Object.keys(payload.sheets),
    rowCounts: Object.fromEntries(
      Object.entries(payload.sheets).map(([name, rows]) => [name, rows.length])
    ),
  };
}
