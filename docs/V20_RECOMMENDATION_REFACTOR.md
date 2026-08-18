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

---

## V20 Integration Hardening（`889a7a8`）

Phase 5 之前补齐的集成收口，解决四个阶段之间仍然存在的语义/缓存/降级不一致。

| 编号 | 修复 |
| --- | --- |
| 1 | `frozen_parameters` 进入后端生成指纹 + 前端 generation snapshot |
| 2 | Generator 的 `_request_distance` / `_demand_assessment` 复用共享 `RequirementAssessment` |
| 3 | `rank_historical_products` 离线回退改为软推荐（不再硬过滤） |
| 4 | 前端卡片与详情真正渲染 `requirement_assessment.conditions` |
| 5 | `sort_order` 从 generation snapshot 排除 |
| 6 | 删除详情页“筛选排序采用 P10”旧文案 |
| 7 | mapped enum 接入 `canonical_filter_value` / `values_equal` 比较 |
| 8 | `unknown` 不再计入 `strict_satisfied`；修复离线价格降序缺失价格排最前 |

### 关键文件
- `app/generation_tasks.py`、`app/static/app.js`（指纹 + snapshot）
- `app/local_generator.py`（Seed 距离 / 需求判定复用共享评估，生成结果附 `requirement_assessment`）
- `app/recommender.py`（`filter_match` 枚举映射、`rank_historical_products` 软推荐与降序修复、`agreement_matches` 传 definitions）
- `app/requirement_assessment.py`（`assessment_status`、`strict_satisfied` 语义、`group_matched`）
- `app/server.py`（离线排序传 definitions/tag_map，两处 `_demand_assessment` 解包三元组）
- `app/static/index.html` / `styles.css`（“需求匹配”面板与证据 chips）

### 测试
- 新增 `tests/generation_fingerprint_test.py`、`tests/mapped_enum_value_semantics_test.py`、`tests/offline_soft_unknown_test.py`、`tests/generator_requirement_consistency_test.py`
- 扩展 `tests/requirement_assessment_test.py`（OR 组 strict_satisfied / unknown 不计满足）

### 未包含（Phase 5 增强项）
- DataMaster/模型耦合对优先级选择（当前仍为相邻 `numeric_comp` 组合）
- 完整多步 move trace（当前仅保存最终节点 parent 信息，未嵌完整链）

---

## V20 Pre-Phase5 Patch（`aad8aed`）

Phase 5 前补的三个 P1 + 一个 `-1` 阻断项 + UI 收尾。

| 编号 | 修复 |
| --- | --- |
| 1 | 部分满足方案内部按 `demand_penalty` 排序（`satisfied_rank, fit_rank, score_rank`） |
| 2 | 技术指标规则加连续 `normalized_gap`（AND 求和 / ANY 取最近 alternative），不再 0/1 化 |
| 3 | `store.derive_tags` / `tag_evidence` 经 `_tag_rule_match` 透传 parameter definition |
| 4 | 前端 mapping 优先于 boolean 二值；boolean 编辑器支持第三态（`-1` → 无该属性） |
| 5 | Generator `strict_filter_satisfied` 使用共享 assessment 的 `strict_satisfied` |
| UI | chips 对 AND 逐条显示；actual 经 `displayParameterValue` 显示业务值；离线详情继承卡片 assessment；Saved/CSV 隐藏 P10 与可行概率 |

### 关键文件
- `app/requirement_assessment.py`（`_rule_gap`、`gap` 字段、AND/ANY 聚合）
- `app/recommender.py`（`rank_agreements` / `rank_historical_products` 排序键、生成项 `strict_filter_satisfied`/`fit_penalty`）
- `app/store.py`（`_tag_rule_match`）
- `app/local_generator.py`（strict 状态复用）
- `app/static/app.js`（`booleanOptions`、`displayParameterValue`、`requirementEvidenceHtml`、`openDetail`、`exportCsv`、`openSaved`）

### 测试
- 新增 `tests/partial_ranking_and_gap_test.py`、`tests/tag_rule_definition_test.py`

---

## V20 Phase 5 — 条件属性约束生成（`6a153fb` / `57f6d2c` / `481629d` / `0ce80b2` / `81a987f`）

| 提交 | 阶段 | 主题 |
| --- | --- | --- |
| `6a153fb` | Patch 0 | 保留生成工程 penalty、ANY gap、布尔第三态筛选 |
| `57f6d2c` | 5A | 条件属性约束模板（编译 + schema + 管理 UI + 迁移） |
| `481629d` | 5B | 约束投影 + 活跃搜索空间 |
| `0ce80b2` | 5C | 工程耦合对优先级 + 结构调整惩罚 |
| `81a987f` | 5D | 可回放多步生成路径 + 解释 UI |

### Patch 0
- `rank_agreements` 区分历史/生成：生成项 `strict_filter_satisfied = assessment.strict_satisfied and not hard_conflicts and hard_penalty<=0`，`fit_penalty = demand_penalty + 2.5*hard_penalty`。
- `parameter_group.gap` 与 `demand_penalty` 同语义（ANY=min、AND=sum）。
- 布尔第三态：`value_semantics.mapping_target` + `filter_match` boolean_is 走映射比较；前端 `booleanFilterOptions` 三态。

### 5A 条件属性约束模板
- `constraint_rules` 新增 `rule_kind`（affine/conditional_lower/conditional_upper）、`constraint_group`、`template_metadata_json`，向后兼容迁移（默认 `affine`）。
- `app/conditional_constraint.py`：`compile_conditional_constraint` 把「控制指标→从属指标适用性」编译为两条 affine 规则（`B≥(L−C)A+C`、`B≤(U−C)A+C`）；`inactive_value` 可配置。
- DataMaster「条件属性有效性」管理 UI；`store.upsert_conditional_template` / `delete_conditional_template` 成组原子增删改。

### 5B 约束投影 + 活跃搜索空间
- `app/constraint_projection.py`：`project_constraints`（不适用折叠、激活恢复 seed→default→midpoint、冻结优先级冲突）、`active_parameter_set`。
- Generator 候选最终化在模型评价前应用投影，并记录 `inactive_parameters` / `active_parameters` / `projection_repairs` / `constraint_conflicts`。
- Requirement Assessment 对 inactive 从属指标输出 `actual_state=inactive` + `inactive_reason`，gap 固定 1.0。

### 5C 工程耦合对优先级
- `app/coupling_pairs.py`：pair 池优先级 DataMaster > 学习耦合 > 条件控制器↔从属 > 探索；锁定/inactive 不进 proposal。
- 条件控制器动作标记 `structural_move`，加轻微 `structural_penalty`（0.35）进搜索键。

### 5D 生成路径 + 解释 UI
- 每个候选带 `node_id` / `parent_node_id` / `move_type`（结构枚举）/ `move`（结构化 changes + reason）。
- `_build_generation_path` 回溯生成可回放 `generation_path`；详情页新增「方案形成过程」面板。

### 测试（新增 12 个，累计 31 个全通过）
`generated_engineering_ranking_test.py`、`any_group_gap_test.py`、`boolean_third_state_test.py`、`conditional_constraint_compile_test.py`、`conditional_constraint_admin_test.py`、`constraint_projection_test.py`、`frozen_conditional_conflict_test.py`、`inactive_search_space_test.py`、`inactive_requirement_test.py`、`coupling_pair_priority_test.py`、`structural_move_priority_test.py`、`generation_path_replay_test.py`、`constraint_projection_trace_test.py`



