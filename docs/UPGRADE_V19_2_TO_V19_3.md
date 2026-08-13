# V19.2 升级到 V19.3

## 升级前

1. 关闭正在运行的V19.2；
2. 备份`data/protocol_demo.db`；
3. 备份`models/`和`data_master/DataMaster_Current.xlsx`；
4. 确认没有正在进行的DataMaster导入或数据库恢复。

## 使用升级补丁

将补丁内容复制到V19.2根目录并覆盖同名程序文件。补丁不包含以下现场数据目录：

```text
data/
models/
data_master/
backups/
uploads/
runtime/
logs/
exports/
```

## 升级后检查

运行：

```bat
RUN_FULL_PIPELINE_TEST.bat
```

测试通过后运行：

```bat
START_ALL_WIN7.bat
```

重点检查：

- 点击“智能生成新方案”后页面仍可操作；
- 连续生成两批后，第一批方案仍可打开详情；
- 设置价格上限后，生成轨迹记录模型输出目标；
- 选中标签后，详情显示标签判定依据；
- 数据管理和原有DataMaster数据正常。

## 数据兼容

V19.3继续使用模型契约3.0和V19系列DataMaster结构，不要求重新制作工作簿。生成批次属于运行时临时数据，不写入已有业务表。
