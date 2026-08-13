# 从V19.1升级到V19.3

## 升级内容

本补丁只修改生成算法、生成风险展示、版本信息、测试和文档。模型契约仍为3.0，DataMaster八张业务表结构不变。

## 升级步骤

1. 关闭V19.1；
2. 备份`data/protocol_demo.db`；
3. 备份`models/`和`data_master/DataMaster_Current.xlsx`；
4. 将补丁中的文件复制到V19.1根目录并覆盖；
5. 运行`RUN_FULL_PIPELINE_TEST.bat`；
6. 测试通过后运行`START_ALL_WIN7.bat`。

## 不覆盖内容

升级补丁不包含：

- `data/protocol_demo.db`；
- `models/`；
- `data_master/`；
- `backups/`；
- `uploads/`；
- `exports/`；
- `runtime/`；
- 现场日志。

## 模型兼容

V19.3不要求重新训练模型。现有V19/V19.1模型契约3.0可以继续使用。算法只改变可行轮廓在生成阶段的使用方式：从强制回投改为软经验参考和反向补偿目标。
