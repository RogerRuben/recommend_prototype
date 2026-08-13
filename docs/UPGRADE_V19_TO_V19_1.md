# 从V19升级到V19.1

1. 关闭V19程序。
2. 备份 `data/protocol_demo.db`、`models/`、`data_master/DataMaster_Current.xlsx` 和 `backups/`。
3. 将升级补丁中的文件复制到V19根目录并覆盖代码文件。
4. 补丁不会包含活动数据库、活动模型或当前DataMaster。
5. 运行 `RUN_FULL_PIPELINE_TEST.bat`。
6. 测试通过后运行 `START_ALL_WIN7.bat`。

V19.1沿用V19模型契约3.0和DataMaster八表结构，无需因本次交互调整重新训练模型。
