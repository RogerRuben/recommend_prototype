import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";


const moduleReference = process.env.ARTIFACT_TOOL_MODULE
  ? pathToFileURL(process.env.ARTIFACT_TOOL_MODULE).href
  : "@oai/artifact-tool";
const { FileBlob, SpreadsheetFile } = await import(moduleReference);


const [inputPath, outputDir, ...sheetNames] = process.argv.slice(2);
if (!inputPath || !outputDir || !sheetNames.length) {
  throw new Error("用法：node verify_spreadsheet_render.mjs <xlsx> <输出目录> <工作表名...>");
}

await fs.mkdir(outputDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const overview = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 5000 });
await fs.writeFile(path.join(outputDir, "workbook-inspect.json"), JSON.stringify(overview, null, 2), "utf8");

for (const sheetName of sheetNames) {
  const formulas = await workbook.inspect({
    kind: "formula", sheetId: sheetName, range: "A1:AZ100", maxChars: 3000,
    options: { maxResults: 100 },
  });
  const safeName = sheetName.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(path.join(outputDir, `${safeName}-formulas.json`), JSON.stringify(formulas, null, 2), "utf8");
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, `${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

console.log(JSON.stringify({ inputPath, outputDir, sheetNames }, null, 2));
