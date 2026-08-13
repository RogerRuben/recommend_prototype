# 从 V18.2 升级到 V19

V19不是简单增加页面按钮，而是恢复DataMaster主数据体系并重写真实生成器。建议先在独立目录验证，再替换正式环境。

## 推荐升级流程

1. 关闭V18.2。
2. 完整备份以下目录：
   - `data/protocol_demo.db`
   - `models/`
   - `backups/`
   - 现有主数据Excel。
3. 使用V19完整包执行 `RUN_FULL_PIPELINE_TEST.bat`，确认虚拟数据流程通过。
4. 在V19数据管理页面下载 `DataMaster_Template.xlsx`，将现有成品、属性、标签、耦合、约束和历史协议整理到八张业务表。
5. 使用“DataMaster校验预览”确认无错误后再提交。
6. 将价格和效能模型转换为V19模型契约3.0，并运行 `VALIDATE_MODELS.bat`。
7. 再次执行完整Pipeline测试，最后由业务专家验收生成方案。

## 补丁包说明

代码升级补丁默认不覆盖：

- `data/protocol_demo.db`；
- `models/`；
- `data_master/DataMaster_Current.xlsx`；
- `backups/`。

因此补丁适合保留现场数据，但升级后必须补充符合V19契约的DataMaster和模型。首次体验建议直接使用完整包。
