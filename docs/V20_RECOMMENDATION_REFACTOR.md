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

---

## V20 Phase 5 Hardening + Generation UX

| 提交 | 主题 |
| --- | --- |
| `cc4de87` | 候选模型评价前 canonicalization（单一管线，投影先于签名） |
| `4b89c15` | 约束规则贯穿 + 全移动类型 inactive 过滤 + 耦合方向真实化 |
| `96c2b84` | 条件属性业务化 UI + `parameter_group` 元数据 + 模板/元数据 round-trip |
| `59cbfd4` | 工程友好 nice step + 参数 canonicalization |
| `3a8105a` | 价格/效能服务业务输出默认三位 |
| `e97acb9` | 分组冻结参数（组全选/半选/摘要） |
| `91dfb31` | 用户可配候选评价额度/最大搜索轮数 + 动态 schedule |
| `420cef8` | trace change 带 source/reason_type |

### 关键改动
- `_finalize_params` = 唯一 candidate canonicalization 管线（restore locked → 投影#1 → repair → 投影#2 → round），invariant `model_input==candidate.params==signature==trace.final_params`。
- 冻结条件冲突直接 reject proposal（`conditional_frozen_conflict`）；structural 由实际控制器状态变化判定。
- `active_parameter_set` 过滤所有 move 类型；耦合对带 `relation_type`/`direction`（positive/negative/feasible/learned 符号）。
- `parameter_group` 列（默认「其他」）贯穿 SQLite/DataMaster 导入导出/管理 UI；`rule_kind/constraint_group/template_metadata_json` 贯穿 DataMaster round-trip；编辑换 controller/target 时按 `original_constraint_group` 清旧组。
- `nice_engineering_step`（1/2/2.5/5/10×10ⁿ）+ `canonicalize_parameter_value`；价格/效能业务输出 3 位。
- 分组冻结 Accordion（组全选/indeterminate + 摘要），payload 仍为扁平 `frozen_parameters`。
- `generation_budget`/`generation_rounds` 进 fingerprint + server 上限（`generation_limits`）+ 动态 `build_step_schedule`。
- trace change 带 `source`（search/user_frozen/constraint_projection）与 `reason_type`。

### 测试（累计 37 个全通过）
新增 `batch_projection_consistency_test.py`、`coupling_direction_test.py`、`nice_step_test.py`、`template_roundtrip_test.py`、`generation_budget_rounds_test.py`、`trace_source_test.py`。





---

## V20 Generation Reliability & Admin UX Hardening

从 `fcf2245` 起的可靠性收口：修复条件属性管理事件冲突、指标分组主数据、需求计数语义、生成锚定语义、空结果缓存、失败诊断与前端状态恢复。

| 提交 | 主题 |
| --- | --- |
| `825b792` | 条件属性按钮与通用 CRUD 事件作用域隔离 |
| `f576a55` | 指标分组主数据 + DataMaster round-trip + Frozen 真 Accordion |
| `cb34e04` | 需求匹配按“一个用户输入 = 一个条件”计数 |
| `c40a5a4` | Generator 枚举/布尔第三态/标签规则统一编译为锚定 |
| `f4d2caa` | 空生成结果可重试，不再被 fingerprint 缓存 |
| `ddbfe28` | 暴露 rejection 详情、预算/轮数/停止原因 |
| `95f7e89` | 前端生成条件变化即标记脏状态，requestSnapshot 补 budget/rounds |
| `55b11bc` | 极端门锁混合条件回归测试 |
| `1aba1fc` | 真实 E2E 生成路径回放 + 条件属性高级信息折叠 |

### 关键改动
- `cond-template-edit/delete` 不再携带 `edit-row/purge-row`；通用 CRUD handler 限定 `#mainAdminTable`，根除事件覆盖。
- 新增 `parameter_groups` 主数据（group_name/display_order/description/enabled/default_collapsed），从 `parameter_definitions.parameter_group` 自动迁移；DataMaster 新增「指标分组」sheet，旧工作簿缺表时自动由指标定义推导。
- Frozen 面板按 `parameter_groups` 排序并支持组折叠/全选/半选，组头展开与整组全选分离；删除重复 `collectFrozen`。
- `RequirementAssessment` 对每条价格/标签/技术指标分别计数，`indicator_logic` 独立承载 AND/OR 判定；不再向 `conditions` 塞 `parameter_group` 伪条件。
- `filters_to_anchors` 替代仅数值的 `filters_to_bounds`：mapped enum `text_equals` → `allowed`，布尔第三态保留为 `allowed`，标签分支复用同一编译函数。
- 空 `candidates` 任务标记 `empty_result` 并从 fingerprint 缓存摘除；再次相同请求会真正重新搜索。
- 生成结果新增 `rejection_details`（前 5 条）、`generation_budget`、`actual_budget_used`、`max_rounds`、`actual_rounds`、`stopping_reason`。
- 前端所有生成相关条件变化（标签/价格/效能/技术筛选/AND-OR/Frozen/数量/Budget/Rounds/协议）调用 `markGenerationCriteriaDirty()`；`requestSnapshot()` 纳入 budget/rounds。
- 条件属性管理编辑框增加「高级信息（编译后约束）」折叠；普通需求 chip 对 inactive 属性显示“无该属性”并提供受控关系 tooltip。

### 测试（累计 54 个，2 个因沙箱临时目录权限无法运行）
新增 `conditional_template_ui_wiring_test.py`、`parameter_groups_admin_test.py`、`requirement_count_user_conditions_test.py`、`enum_filter_anchor_test.py`、`empty_generation_retry_test.py`、`generation_failure_diagnostics_test.py`、`frontend_generation_dirty_test.py`、`extreme_mixed_filter_generation_test.py`、`real_generation_path_replay_test.py`、`conditional_advanced_fold_test.py`。

---

## V20 Integration Patch（4 个 P1 收口）

在 `ec242ee` 后的静态 review 收口，只补四个 P1，不引入新 Phase。

| 提交 | 主题 |
| --- | --- |
| `1d6842d` | 旧 DataMaster 缺「指标分组」sheet 不再 KeyError，自动推导 |
| `f0ff52c` | `parameter_group` + `parameter_groups` 完整进入 Product Release/维护工作簿 |
| `861da01` | generation budget 改为严格 hard cap；budget/rounds 在 fingerprint 前规范化 |
| `c14edc6` | 前端消费 `empty_result/rejection_details/stopping_reason`，空结果不自动切空页 |

### 关键改动
- `DataMaster.parse` 的 `parsed` 对可选 sheet 使用 `workbook.get` 语义，缺表时 `[]`，随后由指标定义推导分组。
- Product Release `SECTIONS/HEADER_ALIASES/CSV_COLUMNS/PRIMARY_KEYS/REQUIRED_COLUMNS` 增加 `parameter_groups`；`parameters` 增加 `parameter_group`；维护工作簿增加「指标分组」sheet；旧发布包缺 `parameter_groups` 仍可导入。
- Generator `max_evaluations = int(budget)`，不再被 `count*10` 放大；初始 seed batch 也按预算截断；`actual_budget_used` 报告真实尝试次数。
- `GenerationTaskManager.start()` 在 fingerprint 前把 `generation_budget/generation_rounds` clamp 到 server 上限；`_generate_sync` 对同步调用同样 clamp。
- 前端空结果时保留历史推荐页，显示评价额度/搜索轮数/停止原因/rejection 统计与明细，并提供「按原条件重新生成」。

### 测试（累计 58 个，仍 2 个因沙箱临时目录权限无法运行）
新增 `datamaster_optional_sheet_test.py`、`product_release_parameter_groups_roundtrip_test.py`、`generation_budget_hard_cap_test.py`、`frontend_empty_result_ui_test.py`。

---

## V20 P1 Closure 尾部补丁

在 `7ed59a3` 后收掉 3 个边缘漏口，不再横向扩散。

| 提交 | 主题 |
| --- | --- |
| `2391d09` | 旧发布包 hash 校验先于 optional `parameter_groups` 补齐 |
| `bd3942d` | emergency fallback 纳入 generation hard budget |
| `fbe38e7` | `recommend()` 空任务分支显示诊断面板后 return，避免被 `renderResults()` 隐藏 |

### 关键改动
- `import_package()` 先对 transport payload 验 hash，再 `setdefault("parameter_groups", [])`；旧 JSON 发布包真正可导入。
- `_emergency_candidate()` 接收 `budget` 状态，每次 `_record_from_params` 都计入 `attempted_evaluations`；`actual_budget_used` 与真实模型调用次数一致。
- 前端 `recommend()` 的 completed+empty 分支先 `renderResults(data)` 再 `showEmptyGeneration(gt)` 并 `return`，诊断面板不会被后续 `renderResults()` 隐藏。

### 测试（累计 60 个，全部通过）
新增 `product_release_legacy_package_test.py`、`emergency_budget_hard_cap_test.py`；强化 `frontend_empty_result_ui_test.py` 断言空分支包含 `return`。

---

## V20 封版前修补（P1 + 两个 P2）

在 `038f195` 后补掉发布前检查发现的最后一个 P1 与两个已知 P2。

| 提交 | 主题 |
| --- | --- |
| `5c779f3` | Product Release 维护工作簿保留条件属性模板元数据 |
| `4e1680f` | 停用指标分组语义闭环（Frozen/Admin/后端分配拦截） |
| `d5192b3` | mapped enum 生成锚定支持字符串模型编码 |

### 关键改动
- Product Release `constraints` 的 `HEADER_ALIASES/CSV_COLUMNS/_normalize_item` 补齐 `rule_kind / constraint_group / template_metadata_json`；`conditional_templates()` 的 rule 也暴露 `constraint_group/template_metadata_json`，维护工作簿 round-trip 后 Phase 5 投影仍生效。
- 停用指标分组：已有指标保留原组；新指标/其他指标移入停用组会被后端拒绝；Frozen UI 对停用组标记“已停用”并默认折叠；管理指标分组下拉对停用组禁用（已选中的旧值保留可选）。
- `filters_to_anchors` 对 mapped enum 不再强制 `float(mapped)`；`_anchor_demands` 的 allowed 分支支持字符串模型编码，`"不锈钢"→"SS"` 也能正确锁定。

### 测试（累计 63 个，全部通过）
新增 `product_release_conditional_template_roundtrip_test.py`、`parameter_groups_disabled_semantics_test.py`、`string_enum_anchor_test.py`。




