# 锁成品 V17 特例效能后端配置与接口说明

## 1. 适用范围

本后端仅用于把锁成品 V17 冻结模型接入现有效能服务 `:18102`。推荐系统、数据库、DataMaster、价格服务和生成器不感知派生字段，也不需要增加 `e`。

普通效能模型继续使用 `OriginalRuntimeBackend`、`FrozenRuntimeBackend` 或 `SnapshotBackend`。锁 V17 不是新的通用效能模型标准。

## 2. 生产输入

训练软件导出的生产运行包应为：

```text
lock_v17_reuse_model_<digest>.zip
```

解压后至少包含：

```text
lock_v17_runtime_manifest.json
model/frozen_lock_reuse_model.json
source/frozen_lock_model.py
source/lock_utility_model.py
source/preference_models.py
source/project_excel.py
```

开发交付包 `02_锁成品V17_界面接口版.zip` 不能直接作为 `EFFECT_RUNTIME_PACKAGE`。它含训练界面和示例工作簿，但不含训练完成后的冻结模型。

## 3. 派生字段

业务对应关系为：

| 任务书代号 | 业务名称 |
|---|---|
| `a` | 钩锁力-1 |
| `b` | 钩锁力-2 |
| `c` | 钩锁刚度-1 |
| `d` | 钩锁刚度-2 |
| `e` | 两组差值乘积（模型内部派生字段） |

两组均存在时：

```text
e = abs(钩锁力-1 - 钩锁力-2)
    * abs(钩锁刚度-1 - 钩锁刚度-2)
```

配置中的 `x1=[a,c]`、`x2=[b,d]` 表示每一套钩锁的“力 + 刚度”必须成组存在。

- 两组均存在：按公式计算 `e`。
- 任一整组为 `-1/-1` 或整组缺失：`e=0`。
- 组内一个正常、另一个为 `-1` 或缺失：返回 400，不猜测。
- 请求中即使带 `e`，服务端也会忽略并重新计算。

`e` 不进入 `parameter_definitions`、`agreements.params_json`、DataMaster 或生成器搜索空间。

## 4. 配置文件

复制：

```text
services/effectiveness_service/config/lock_v17_adapter.example.json
```

为：

```text
services/effectiveness_service/config/lock_v17_adapter.json
```

然后完成以下配置：

1. 把示例键 `a/b/c/d` 替换为 DataMaster 中四个业务属性的真实 `parameter_id`，不要填中文名称。
2. `target_field` 必须与冻结模型 Schema 中真实的派生字段 ID 一致。
3. 填写真实单位、数据类型、生成上下限和偏好方向。
4. 只有确认了真实搜索范围后，才将 `participates_generation` 和 `improvement.enabled` 改为 `true`。

四个派生源字段的公共 Schema 固定为 `required=false`。这是“条件必需”而非“全局必需”：一整组可以合法缺失，但只填写组内一个字段会由 Adapter 明确拒绝。

示例配置故意将改进搜索关闭并把范围留空，防止现场用猜测范围生成参数。

启动时会验证：四个源字段唯一、每组恰好两个字段、`target_field` 存在于冻结模型、缺失组规则为归零、partial 规则为拒绝、物理兼容占位为 `0.65`。

## 5. 启动

PowerShell：

```powershell
$env:EFFECT_RUNTIME_PACKAGE="D:\models\lock_v17_current\lock_v17_runtime_manifest.json"
$env:EFFECT_LOCK_V17_ADAPTER_CONFIG="D:\recommend_prototype\services\effectiveness_service\config\lock_v17_adapter.json"
python services\effectiveness_service\app.py --port 18102
```

或使用：

```text
services/effectiveness_service/START_EFFECTIVENESS_LOCK_V17_WIN7.bat
```

脚本优先使用 `EFFECT_SERVICE_PYTHON`，没有配置时使用 PATH 中的 `python`。

## 6. Schema 契约

`GET /api/v1/schema`：

- `backend=lock_v17_frozen_runtime`
- `fields` 包含四个真实业务源字段和其它直接模型输入
- `fields` 不包含 `e`
- `derived_features` 描述 `e` 的公式、依赖和缺失归零规则
- `active_protocol` 和 `protocol_profiles` 只公开基准编号、名称、分数和摘要，不公开包含 `e` 的内部 `reference_values`
- `capabilities.physical_feasibility=false`
- `capabilities.counterfactual_improvement` 取决于适配配置

## 7. 评价输出

V17 `effectiveness_score` 同时映射为标准的 `effectiveness_score` 和 `capability_score`。如果 V17 返回区间，则下界映射为 `conservative_capability_score`。

V17 不评价物理可行性。为兼容当前推荐主线，接口固定返回：

```json
{
  "feasibility_probability": 0.65,
  "feasibility_status": "not_evaluated_lock_v17",
  "physical_feasibility_evaluated": false,
  "physical_gate": {
    "passed": true,
    "decision": "pass_not_evaluated",
    "not_evaluated": true
  }
}
```

`0.65` 不是模型预测概率。V17 的 `not_reusable` 也不会转成物理拒绝；复用结论保存在 `reuse_assessment`。

对接方不能只根据 `physical_gate.passed=true` 显示“物理可行”。必须首先读取 `physical_feasibility_evaluated`：当它为 `false` 时，真实业务状态只能显示为“物理可行性未评价”。这里的 `passed=true` 只是为了让当前主线兼容放行，不是物理评价结论。

## 8. 目标协议

只接受冻结模型 `evaluation_baselines` 中存在的 `profile_id`。公共接口不接受 `reference_values`，也不将内部基准参数返回给调用方。

不支持请求时动态构造新的 V17 基准协议。

## 9. 局部改进

冻结 V17 本身没有 `recommend_improvement()`。特殊后端可在真实业务字段上执行最多两轮、最多 120 个候选的有界局部搜索。

- 目标是提高保守效能分数。
- 平分时优先更少字段、更小归一化改动。
- 返回值只含业务字段，不含 `e`。
- 如果任一派生属性组不存在，四个源字段全部锁定，避免自动创造不存在的结构。
- 没有达到 `min_gain` 时返回 `no_better_local_candidate`。

该搜索是 **effectiveness-only local improvement**：价格不参与 V17 服务内部的候选生成和选择。Gateway 在改进参数返回后可以重新评价价格，但不会回到 V17 候选池中按价格重选。如果业务按钮承诺“价格与效能综合优化”，不能直接把本接口结果解释成综合最优。

## 10. 正式冻结包真实 Smoke

专项单元测试使用可控 runtime 验证 Adapter 和输出映射。最终含派生字段的生产冻结包到位后，还必须运行非 stub smoke：

```powershell
$env:LOCK_V17_REAL_PACKAGE_MANIFEST="D:\models\lock_v17_current\lock_v17_runtime_manifest.json"
$env:LOCK_V17_REAL_ADAPTER_CONFIG="D:\recommend_prototype\services\effectiveness_service\config\lock_v17_adapter.json"
$env:LOCK_V17_REAL_BUSINESS_PARAMS_JSON='{"真实字段A":10,"真实字段B":6,"真实字段C":8,"真实字段D":5,"其它必填字段":1}'
python -m unittest tests.lock_v17_special_backend_test.LockV17RealFrozenPackageSmokeTest
```

该测试会使用运行包中的真实 `FrozenLockReuseRuntime`，检查 Schema、单条评价、批量评价，以及启用时的局部改进。未设置三个环境变量时测试会明确标记为 skipped，不会用 stub 冒充真实 E2E 已通过。

## 11. 上线检查

```text
GET  /health
GET  /api/v1/schema
POST /api/v1/evaluate
POST /api/v1/evaluate/batch
POST /api/v1/improve
```

同时确认：

- 运行包和模型摘要校验通过；
- Schema 不把 `e` 暴露为业务字段；
- 请求携带伪造 `e` 时实际值仍由服务端重算；
- `not_reusable` 不触发物理拒绝；
- 数据库和 DataMaster 中没有新增或回填 `e`。
