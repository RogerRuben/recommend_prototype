# V21.1 Critical Workflow Closure

本轮修复需求录入语义、恢复 Generator“先尽力生成，再判断是否满足”的原则，并补齐 Guide、Portal 与 Workbench 的交付体验。

## 不可破坏的业务边界

1. 用户显式技术条件不能被搜索、标签刷新或 UI 辅助行为静默修改。
2. 搜索只帮助用户找到指标，不能替用户选择指标。每条条件必须按“指标分组 → 组内搜索/浏览 → 用户明确选择 → 操作符和值”录入。
3. DataMaster min/max、历史范围、训练范围与模型 Schema 范围均为参考信息。它们用于风险说明和探索引导，不得静默拒绝、截断、吸附或改写用户显式输入。
4. 只有明确工程硬规则、无效数据类型或模型服务真实拒绝可以阻止一次模型计算；模型拒绝不能删除已经生成的参数探索方案。
5. Generator 必须先尝试生成，再判断结果等级：Strict → Best Effort → Exploratory。越出参考范围、历史无匹配值或模型必填字段可补全，均不得造成 0 次评价、0 轮搜索的提前退出。
6. Preflight 是候选修复器和诊断器，不是全局终止门。它只能补全用户未指定的模型必需字段，不能修改显式 anchor 或 frozen 参数。
7. `allowed_values` 的存在不代表数值业务域是有限离散集合。只有明确配置 `search_type=ordered_discrete` 才允许吸附；普通 number/float 是 continuous，integer/ip_grade 是 integer。
8. UI 配置、Guide、Portal 地址和面板宽度不得改变推荐/生成业务语义或 fingerprint。
9. Business Value、Display Value、Model Value 三层继续隔离。显示映射只改变操作员看到的文本，数据库、筛选、保存、模型输入和预测仍使用 canonical 业务值。

## 操作与状态矩阵

| 行为 | 当前指标 | Operator | Value |
| --- | --- | --- | --- |
| 用户明确选择新指标 | 改变 | 重建 | 重建 |
| 用户切换分组 | 等待重新选择 | 清空 | 清空 |
| 行内搜索输入 | 不变 | 不变 | 不变 |
| 标签增删 | 不变 | 不变 | 不变 |
| 隐藏覆盖开关 | 不变 | 不变 | 不变 |
| 修改 Operator | 不变 | 改变 | 重建对应编辑器 |

## Generator 输出等级

- Strict：满足全部显式需求且没有明确工程硬冲突。
- Best Effort：模型评价可用，但受真实业务离散域或工程硬规则限制，无法严格满足全部要求；必须明确展示差距。
- Exploratory：参数组合已经生成，但模型服务拒绝该输入或评价不可用；保留参数方案和拒绝原因，不伪造预测值。

## 配置边界

- 标准 `START_ALL_SERVICES_WIN7.bat` 默认开启认证并进入 Portal。
- 普通生成默认 5 个候选；HTML、JavaScript、Server 和 Generator fallback 保持一致。
- `config/service_portal.json` 使用 `visible` 与 `enabled` 两个独立状态。显示但未启用的服务以“待接入”卡片呈现。
- Admin 的服务导航保存只修改 `service_portal.json`：校验 URL、备份旧文件、写临时文件并原子替换，不得修改 `model_services.json`。
