# V20 工业技术协议智能推荐系统重构

从 develop `e5cecdc` 起，按四个独立阶段完成推荐链路重构。每阶段一个独立提交，均先跑旧回归再跑新用例。未改动价格/效能模型产物，未重写 `HistorySeededGenerator`，内部 `physical_gate / feasibility / anomaly` 检查保留但对用户隐藏。

| 阶段 | 提交 | 主题 |
| --- | --- | --- |
| Phase 1 | `4779d88` | 业务值语义统一 |
| Phase 2 | `907be43` | 价格 + 中心效能指标与排序 |
| Phase 3 | `c2ec9cf` | 共享软需求评估 + 推荐/生成解耦 |
| Phase 4 | `09e88bd` | 冻结参数 + 预算保持多轮 beam + 移动轨迹 |

---

## Phase 1 — 业务值语义统一

### 文件
- 新增 `app/value_semantics.py`
- `app/recommender.py`：`_number`、`filter_match` 布尔分支
- `app/local_generator.py`：`_truth` / `_float` / `_value_equal`

### 数据字段（统一函数）
- `normalize_numeric`：`"IP65"` → `65`
- `normalize_boolean`：真值/假值令牌集，覆盖 `1.0` / `"有"` / `"无"` 等
- `values_equal`：布尔感知；数值容差 `10 ** (-max(2, decimal_places))`
- `canonical_filter_value`、`business_display_value`（反向映射 `model_value_mapping_json`，仅声明时 `-1` → `无该属性`）
- `definition_mapping()`：解析 `model_value_mapping_json`

### 行为
- 筛选匹配与生成器取值共用同一套业务语义，消除业务值与模型编码不一致。

### 测试
- 新增 `tests/value_semantics_test.py`

### 兼容风险
- 不改模型编码，DataMaster 业务值经 `model_value_mapping_json` 桥接；旧历史数据展示保持一致。

---

## Phase 2 — 价格 + 中心效能指标与排序

### 文件
- `app/recommender.py`：`center_capability()`、`agreement_matches` 的 `min_capability` 改用中心值、`rank_agreements` 排序
- `app/static/app.js`：请求体去掉 `min_cost_effectiveness` / `min_feasibility`，新增 `sort_order`
- `app/static/index.html`：`sortBy` / `sortOrder`，指标标签

### 数据字段 / 行为
- 用户可见 `capability_score`（中心值）为权威；`conservative_capability_score`（P10）仅内部。
- `sort_order` asc/desc，价格默认 asc；卡片/详情仅展示 价格 / 效能评分 / 效费比。
- 移除 P10 / 可行概率 / 可信度对外展示。

### 测试
- 新增 `tests/user_facing_score_test.py`、`tests/sort_order_test.py`

### 兼容风险
- 内部 `feasibility` / 工程筛选仍参与判断，只是不再作为用户阈值输入项。

---

## Phase 3 — 共享软需求评估 + 推荐/生成解耦

### 文件
- 新增 `app/requirement_assessment.py`
- `app/recommender.py`：`rank_agreements` 软保留历史方案
- `app/server.py`：`recommend()` 传入 `definitions` / `tag_map`
- `app/static/app.js`：`recommendBtn` 与生成解耦（`recommend(false)`）

### 数据字段 / 行为
- `assess_requirements` 逐条件输出证据 `{kind,key,label,operator,target,actual,matched,gap}`，以及 `matched_count / unmatched_count / unknown_count / demand_penalty / strict_satisfied / fit_ratio`。
- 指示器分组支持 AND/OR；`unknown` ≠ `unmatched`。
- 历史方案改为软匹配：用户阈值（如 `min_feasibility`）不再删除历史，完全满足排前，部分满足按 `demand_penalty` 排后。

### 测试
- 新增 `tests/requirement_assessment_test.py`
- 更新 `tests/historical_not_gated_test.py`（软保留行为）

### 兼容风险
- 语义变更：历史方案不再被用户阈值硬过滤，排序语义从“过滤”转为“严格优先 + 软惩罚”。循环导入通过 `rank_agreements` 内惰性 `import` 规避。

---

## Phase 4 — 冻结参数 + 预算保持多轮 beam + 移动轨迹

### 文件
- `app/local_generator.py`：`_apply_frozen`、`frozen_parameters`、`locked_sources`、快束首轮预算上限
- `app/static/app.js` / `app/static/index.html` / `app/static/styles.css`：生成区“生成时保持不变”勾选

### 数据字段 / 行为
- `frozen_parameters`：锁定每个种子自身的值，搜索/修复/交叉全程不修改。
- `locked_sources`：区分 `user_anchor` 与 `user_frozen`；`locked` 字典在搜索/修复/交叉间共享。
- 快束预算：首轮上限 `max_evaluations` 的 35%，后续轮 `ceil(remaining / remaining_rounds)`，不再 `round_budget = remaining_budget`。
- 轨迹：`origin_seed_id / parent_iteration / parent_attempt / parameters_before_move / changed_from_parent / changed_from_origin / locked_sources`。
- 前端勾选冻结属性，仅在“智能生成方案”请求携带 `frozen_parameters`。

### 测试
- 新增 `tests/frozen_parameter_test.py`、`tests/fast_beam_multiround_test.py`

### 兼容风险
- `sort_by` / `sort_order` 永不进入生成指纹；冻结仅作用于生成，不影响推荐排序请求。
