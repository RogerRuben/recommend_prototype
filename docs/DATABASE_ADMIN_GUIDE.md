# V19数据库管理说明

运行数据库：`data/protocol_demo.db`。

数据管理页面维护：

- products：成品信息；
- parameter_definitions：完整成品／效能属性；
- tags：标签；
- agreements：历史与宽表导入协议；
- saved_schemes：专家保存方案；
- indicator_couplings：正向、负向和可行域耦合；
- constraint_rules：外置数学约束；
- model_registry：模型版本和文件校验；
- model_input_bindings：价格／效能字段绑定、缺失策略和数据库配置值；
- audit_log：维护记录。

数据库恢复前会自动备份当前数据库。上传数据库必须通过SQLite完整性检查，并包含V19核心业务表。

模型字段绑定中的模型类型、字段编号、类型和缺失策略由当前模型同步，不建议人工修改；`configured_value`用于集中维护价格模型特有字段或统一运行值。模型再次替换时，系统会更新字段定义，但保留同一binding_id原有的configured_value。
