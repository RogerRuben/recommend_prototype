# 工业技术协议智能推荐系统

当前开发线：V21.3.2

本项目面向工业成品技术协议的需求录入、历史方案推荐、候选方案生成、价格预测、效能评价和业务数据维护。系统采用“推荐主应用 + 价格模型服务 + 效能模型服务”的三服务结构，并支持 Windows 7、Python 3.8 和完全离线部署。

本文是项目主入口文档，重点说明当前代码如何实现、服务之间如何调用、关键数据语义和开发维护边界。历史版本说明和专项交付说明保留在 `docs/` 目录中。

## 1. 核心设计原则

下面的规则属于系统业务语义，不应被 UI 优化、模型升级或生成算法修改破坏。

### 1.1 用户显式需求优先

- 用户选择的标签、价格目标、效能目标、技术指标条件和冻结参数属于显式需求。
- 搜索只帮助用户找到指标，不能自动选择第一个匹配项。
- 标签刷新、分组切换、显示映射和排序操作不能静默修改已有显式条件。
- 用户手动排序的优先级高于场景默认排序，场景默认排序高于系统默认排序。

### 1.2 参考范围只用于诊断

DataMaster 工程范围、模型 Schema 范围和训练范围都可能滞后于真实业务，只用于解释风险和提示外推。

它们不能静默执行：

- 拒绝用户输入；
- 把用户输入截断到范围边界；
- 把连续数值吸附到历史离散值；
- 在 0 次模型评价、0 轮搜索时终止 Generator。

只有明确工程硬规则、非法数据类型、模型服务实际拒绝或系统故障可以阻断计算。

### 1.3 三层值语义必须分离

| 层级 | 用途 | 示例 |
| --- | --- | --- |
| Business Value | 数据库、筛选、生成、保存方案中的规范业务值 | `0`、`1`、`-1` |
| Display Value | 页面向操作人员展示的文本 | `无`、`有`、`无该属性` |
| Model Value | 发送给价格或效能模型的编码值 | 由模型映射决定 |

显示映射只能改变用户看到的文本。数据库值、生成值、筛选值、保存方案和模型输入必须保持规范语义。相关实现位于 `app/value_semantics.py`、`app/display_mapping.py` 和 `app/store.py`。

数值字段还可以通过 `special_value_keys_json` 声明特殊业务状态，例如把 `-1` 声明为“无该属性”。特殊状态仍保存原业务值，通过 `special_is` 参与筛选；它不参与普通数值范围、距离和插值计算。主应用的 Bootstrap/Workbench Schema 会把 DataMaster 中的特殊状态元数据提供给前端，浏览器缓存不能成为这类语义的唯一来源。

### 1.4 先尽力生成，再判断满足程度

| 层级 | 含义 |
| --- | --- |
| Strict | 满足全部显式需求，且没有明确工程硬冲突 |
| Best Effort | 无法严格满足，但给出可复核、尽量接近要求的方向 |
| Exploratory | 参数组合已经生成，但模型没有完成评价或明确拒绝评价 |

多样性不能把不满足条件的方案伪装成 Strict，也不能为了不同而返回明显劣质方案。

## 2. 系统架构

```text
浏览器
  │ HTTP / JSON
  ▼
推荐主应用（默认 127.0.0.1:17891）
  ├─ 页面与认证
  ├─ 业务数据与规则
  ├─ 历史方案推荐
  ├─ 智能生成任务
  ├─ 场景策略与推荐解释
  └─ 数据管理中心
       │
       ├──── HTTP ────► 价格服务（127.0.0.1:18101）
       │                 ├─ Schema
       │                 ├─ 单条预测
       │                 └─ 批量预测
       │
       └──── HTTP ────► 效能服务（127.0.0.1:18102）
                         ├─ Schema
                         ├─ 单条/批量评价
                         └─ 改进建议
```

推荐主应用负责业务语义和流程编排。两个模型服务只负责各自的字段选择、模型输入验证和推理，不直接修改业务数据库。

### 2.1 三个进程的职责

| 进程 | 入口 | 默认端口 | 主要职责 |
| --- | --- | ---: | --- |
| 推荐主应用 | `run_app.py` / `app/server.py` | 17891 | 页面、认证、推荐、生成、评价编排、保存方案、数据管理 |
| 价格服务 | `services/price_service/app.py` | 18101 | 加载价格模型、返回字段契约、价格预测和批量预测 |
| 效能服务 | `services/effectiveness_service/app.py` | 18102 | 加载效能运行包、效能与可行性评价、批量评价、改进建议 |

### 2.2 模型调用关系

推荐主应用通过 `app/model_service_client.py` 调用两个独立 HTTP 服务。

```text
Business Parameters
  ↓ app/store.py：规范化业务值
  ↓ Business → Model 映射
Model Parameters
  ├─ POST 价格 /api/v1/predict 或 /predict/batch
  └─ POST 效能 /api/v1/evaluate 或 /evaluate/batch
  ↓
联合评价、规则诊断、排序与解释
  ↓
Business Parameters + Display Mapping 返回前端
```

配置优先级为：代码默认值 `<` `config/model_services.json` `<` 环境变量。正式三服务模式默认关闭本地模型 fallback；模型服务不能运行时，应明确失败或进入历史方案降级模式，不能偷偷切换为演示模型。

## 3. 目录结构与代码职责

| 路径 | 职责 |
| --- | --- |
| `app/server.py` | 主应用对象、HTTP 路由、认证、推荐/生成/评价编排、Admin API |
| `app/store.py` | SQLite 数据访问、业务值规范化、标签与规则、保存方案、备份恢复 |
| `app/recommender.py` | 历史与生成候选的筛选、评分、排序 |
| `app/scenario_policy.py` | 场景策略单一来源、默认排序、权重和用户排序覆盖 |
| `app/recommendation_explanation.py` | 确定性的候选级推荐理由 |
| `app/local_generator.py` | 历史种子、锚定、候选修复、自适应 Beam、最终选择 |
| `app/demand_branch.py` | AND/OR/冲突需求分支，以及显式分支与标签分支组合 |
| `app/requirement_assessment.py` | 统一需求满足度判断 |
| `app/constraint_projection.py` | 条件约束投影、激活状态和修复轨迹 |
| `app/coupling_pairs.py` | 耦合关系与联合调整 |
| `app/anchor_feasibility.py` | 显式锚点可行性与冲突诊断 |
| `app/range_diagnostics.py` | DataMaster、Schema、训练范围的非阻断诊断 |
| `app/generation_tasks.py` | 异步任务、请求 canonicalization、Fingerprint 和缓存 |
| `app/product_releases.py` | 待发布成品维护、校验、导入导出和激活 |
| `app/data_master.py` | DataMaster 工作簿导入、导出和校验 |
| `app/static/` | 推荐页、Portal、登录页、Admin、价格/效能 Workbench |
| `services/price_service/` | 价格服务、原生 bundle、自定义 ExpertTree/TreeNode |
| `services/effectiveness_service/` | 效能服务和冻结/原始运行包适配 |
| `config/` | 模型服务、优化场景、Portal 和 Workbench 配置 |
| `data/protocol_demo.db` | 当前运行业务数据库 |
| `data_master/` | DataMaster 当前工作簿和模板 |
| `tools/` | 环境检查、运行时选择、离线打包、交付验证 |
| `tests/` | 可直接执行的专项回归脚本 |

## 4. 推荐工作流

### 4.1 前端状态

| 状态 | 行为 |
| --- | --- |
| Initial | 只加载产品、场景、标签、指标和协议，不请求推荐 |
| Ready | 用户已设置需求，但尚未点击推荐 |
| Recommended | 用户主动点击“开始智能推荐”，展示当前请求结果 |
| Dirty | 推荐后需求发生变化，旧结果隐藏并要求重新推荐 |

业务条件变化只更新需求摘要和 Dirty 状态，不自动请求 `/api/recommend`。纯展示排序可以在当前结果有效时重新排序。

### 4.2 优化场景

场景配置位于 `config/scenario_config.json`。

| 场景 | 默认目标 | 主要权重方向 |
| --- | --- | --- |
| 综合优化 `balanced` | 同等需求匹配下效费比最高 | 技术、价格、效能平衡 |
| 成本优先 `cost` | 同等需求匹配下价格最低 | 提高价格权重，可设最低效能 |
| 性能优先 `performance` | 同等需求匹配下效能最高 | 提高效能权重，可设最高预算 |

前端不自行推断场景。`ScenarioPolicyService` 返回统一策略，前端展示和后端排序都读取同一结构：

```json
{
  "scenario": "cost",
  "scenario_name": "成本优先",
  "ranking_weights": {
    "technical": 0.3,
    "price": 0.6,
    "capability": 0.1
  },
  "applied_ranking": {
    "sort_key": "price",
    "sort_direction": "asc",
    "source": "scenario_default"
  }
}
```

排序优先级：`user_override > scenario_default > system_default`。

### 4.3 技术指标条件

```text
选择指标分组
  ↓
在全集或当前组中搜索/浏览指标
  ↓
用户明确选择指标
  ↓
根据指标类型重建 operator 和 value editor
```

搜索词、标签变化和覆盖提示不能改变已选 `parameter_id/operator/value`。布尔、枚举、连续数值、整数/IP 等编辑器根据真实指标定义生成。

### 4.4 候选级推荐理由

场景说明只解释总体策略；每张候选卡片的理由由 `app/recommendation_explanation.py` 根据当前候选池确定性生成。系统会识别最低价格、最高效能、最高效费比、技术匹配最完整、接近最低价但效能更高、接近最高效能但价格更低，以及最接近未满足条件的 Best Effort 方向。

理由必须由真实指标支持，不调用大模型，也不为了文案不同而制造不真实结论。

## 5. 智能生成实现

### 5.1 异步任务与 Fingerprint

`POST /api/generation/request` 创建或复用异步生成任务，前端通过 `GET /api/generation-tasks/{task_id}` 轮询状态。

Fingerprint 包含会改变生成语义的场景、标签、价格/效能目标、技术条件、冻结参数、生成数量、评价额度、轮数、当前成品、业务语义版本和模型版本。排序、分页和结果来源模式不进入 Fingerprint。

`count`、`generation_budget` 和 `generation_rounds` 在创建任务、同步生成和 stale 比较前统一 canonicalize，避免服务器截断后产生不同指纹。

### 5.2 Anchor 与候选修复

显式技术条件编译为业务锚点。连续数值保持用户输入，不因历史 `allowed_values` 或参考范围而吸附。

模型必需字段缺失时，Preflight 是候选修复阶段，不是任务终止门。补值只允许作用于用户未指定且未冻结的字段：

```text
候选现值
  > 当前历史种子
  > 其它历史协议合法值
  > 业务默认值/允许值
  > 模型 Schema 默认值
  > 训练均值
  > 参考范围中点
```

修复后重新执行完整的缺失、映射和模型允许值验证。

### 5.3 Demand Branch

`app/demand_branch.py` 将需求编译成搜索方向：

- `A AND B`：一个联合分支；
- `A OR B`：分别生成 A、B 两个显式需求分支；
- AND 存在真实冲突：识别 Conflict Core，只放松冲突条件，无冲突显式条件保留在每个方向；
- 显式需求分支与标签规则分支组合，最多保留 24 个 Generation Branch，显式需求优先。

跨字段冲突检测覆盖条件模板、硬 affine 规则和 `feasible_domain + severity=error` 耦合。超大 Conflict Core 使用有界 maximal-set 搜索，优先保留“放松条件最少”的分支。

### 5.4 Seed Family 与多样性 Beam

每个候选从 Stage 1 起携带：

```text
demand_branch_id
seed_id
family_id = demand_branch_id + ":" + seed_id
```

Beam 选择顺序：

```text
质量带内的 Demand Branch 覆盖
  ↓
不同 Seed Family 覆盖
  ↓
剩余位置按全局搜索质量竞争
```

单一 Family 在存在其它合理方向时采用约 40% 的软上限。最终候选同样先覆盖 Branch，再覆盖 Family，最后按排名填充。

当 Branch 数大于 Beam 宽度时，系统分别记录：

- `quality_eligible_centers`：比较池中质量合格的中心；
- `selected_beam_centers`：本轮实际获得 Beam 槽位的中心。

质量合格但暂时没有容量的分支进入 `waiting_for_capacity`，不会被误判为 `exhausted_by_quality`。Beam 按已获得的搜索机会轮转，并保留每个分支的最佳中心。

### 5.5 提前停止

提前停止同时考虑 Strict 数量、Demand Branch、Seed Family、参数/结构差异，以及各分支是否已找到 Strict、形成 Best Effort、质量淘汰或完成最低探索。单一 Family 的多个轻微变体不能冒充多方向结果；无法形成 Strict 的分支也不会无限阻止任务结束。

## 6. 数据、规则与持久化

### 6.1 运行数据库

默认数据库为 `data/protocol_demo.db`，保存成品、指标与分组、标签与规则、耦合、条件约束、历史协议和专家方案。

管理操作遵循：

```text
启用 → 停用/归档 → 依赖检查 → 自动备份 → 永久删除
```

普通删除应可恢复；永久删除只用于已停用且无引用的数据。

### 6.2 DataMaster 与待发布成品

DataMaster 文件：

- `data_master/DataMaster_Current.xlsx`
- `data_master/DataMaster_Template.xlsx`

系统支持网页逐项维护、CSV/XLSX 分模块导入、普通历史表自动建草稿、维护工作簿和完整离线发布包。只有“备份并切换业务数据”会改变当前运行数据；激活前先备份 SQLite，再原子切换，不自动替换模型。

### 6.3 Portal 配置

`config/service_portal.json` 控制 `label / description / url / visible / enabled`。Admin 保存时执行 URL 校验、旧文件备份、临时文件写入和原子替换。它只管理导航入口，不修改 `config/model_services.json`。

## 7. 启动与运行

### 7.1 标准启动

```bat
START_ALL_SERVICES_WIN7.bat
```

```text
选择并 smoke 验证价格 Python
  ↓
启动价格与效能服务
  ↓
检查两个 /health
  ↓
执行 Schema + 实际预测/评价验证
  ↓
启动推荐主应用并打开 /portal
```

标准启动脚本默认开启认证。开发环境可使用 `START_ALL_NO_BROWSER.bat`。

### 7.2 三个 Python 运行时相互独立

```bat
set "PRICE_SERVICE_PYTHON=C:\path\to\price_python.exe"
set "EFFECT_SERVICE_PYTHON=C:\path\to\effect_python.exe"
set "MAIN_APP_PYTHON=C:\path\to\main_python.exe"
```

也可以放入不提交 Git 的 `runtime/service_runtime.local.bat`。价格解释器不能只按路径存在判断；`tools/check_price_runtime.py` 会实际导入服务、加载模型并执行预测，只有 smoke 通过的解释器才能启动价格服务。

### 7.3 常用页面

| 页面 | 地址 |
| --- | --- |
| 登录 | `http://127.0.0.1:17891/login` |
| Portal | `http://127.0.0.1:17891/portal` |
| 智能推荐 | `http://127.0.0.1:17891/` |
| 简易价格预测 | `http://127.0.0.1:17891/price` |
| 简易效能评价 | `http://127.0.0.1:17891/effectiveness` |
| 数据管理中心 | `http://127.0.0.1:17891/admin` |
| 价格接口文档 | `http://127.0.0.1:18101/docs` |
| 效能接口文档 | `http://127.0.0.1:18102/docs` |

主应用默认在 17891～17901 之间选择空闲端口，并写入 `runtime/last_port.txt`。

## 8. HTTP API

### 8.1 主应用状态接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 主应用健康、模型模式、数据库完整性 |
| GET | `/api/auth/status` | 登录和只读状态 |
| POST | `/api/auth/login` | 登录并写入认证 Cookie |
| POST | `/api/auth/logout` | 退出登录 |
| GET | `/api/portal` | Portal 服务导航配置 |
| GET | `/api/bootstrap` | 当前成品、指标、分组、标签、协议和模型状态 |
| GET | `/api/scenario-policy` | 解析场景和优化强度 |

### 8.2 推荐与生成接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/recommend` | 筛选并排序历史或指定生成批次中的候选 |
| POST | `/api/generation/request` | 创建或复用异步生成任务 |
| GET | `/api/generation-tasks/{task_id}` | 查询生成进度和结果 |
| POST | `/api/generate-live` | 同步生成，主要用于兼容和测试 |
| POST | `/api/clear-live-generated` | 清除指定会话的生成批次 |
| GET | `/api/agreements/{agreement_id}` | 获取历史或生成方案详情 |

推荐请求示例：

```json
{
  "session_id": "operator-001",
  "scenario": "cost",
  "optimization_intensity": "target",
  "scenario_options": {"min_capability": 80},
  "selected_tags": ["TAG-001"],
  "max_price": 15,
  "indicator_filter_mode": "all",
  "indicator_filters": [
    {"parameter_id": "attr_006", "operator": "lte", "value1": 3}
  ],
  "source_mode": "historical",
  "page": 1,
  "page_size": 12
}
```

用户覆盖排序时增加：

```json
{
  "sort_source": "user_override",
  "sort_by": "capability",
  "sort_order": "desc"
}
```

异步生成请求可增加：

```json
{
  "count": 5,
  "generation_budget": 360,
  "generation_rounds": 7,
  "frozen_parameters": ["attr_021"]
}
```

### 8.3 评价、保存与 Workbench

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/evaluate` | 对编辑后的完整方案重新计算价格与效能 |
| POST | `/api/improve` | 请求效能服务生成调整建议 |
| POST | `/api/save-scheme` | 使用有效 evaluation token 保存专家方案 |
| GET | `/api/saved` | 查询保存方案 |
| GET | `/api/saved/{scheme_id}` | 查询保存方案详情 |
| GET | `/api/price-workbench/schema` | 价格 Workbench 字段和示例 |
| POST | `/api/price-workbench/predict` | 只调用价格服务 |
| GET | `/api/effectiveness-workbench/schema` | 效能 Workbench 字段和示例 |
| POST | `/api/effectiveness-workbench/evaluate` | 只调用效能服务 |

方案详情修改参数后不会自动计算。前端先标记结果过期；重新计算后获得新的 evaluation token。保存时服务端核对参数哈希，禁止把旧评价绑定到已修改参数。

### 8.4 Admin 接口

Admin API 位于 `/api/admin/`，主要包括：

- `snapshot`、`upsert`、`delete`、`toggle`、`purge`；
- `backup`、`backups`、`restore-backup`、`upload-database`；
- `portal-config`；
- `conditional-constraint/upsert` 和 `conditional-constraint/delete`；
- `wide-import/preview` 和 `wide-import/commit`；
- `datamaster/template`、`current`、`preview` 和 `commit`；
- `product-releases/*` 草稿创建、维护、校验、导入导出和激活。

写接口在只读演示模式下会被拒绝；Admin 可通过 `IPDEMO_DISABLE_ADMIN=1` 关闭。

### 8.5 价格服务 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 模型加载和服务健康 |
| GET | `/api/v1/schema` | 产品、字段、允许值和范围契约 |
| POST | `/api/v1/predict` | 单方案价格预测 |
| POST | `/api/v1/predict/batch` | 批量价格预测，最多 1000 条 |
| GET | `/openapi.json` | OpenAPI 3.0 |
| GET | `/docs` | 简易接口测试页 |

```json
{
  "request_id": "PRICE-001",
  "product_code": "PRODUCT_CODE",
  "candidate_id": "CANDIDATE-001",
  "parameters": {"attr_001": 1}
}
```

正式模式使用 `services/price_service/model/price_native_bundle.pkl`。自定义 `ExpertTree` 和 `TreeNode` 位于 `services/price_service/expert_tree.py`，加载逻辑位于 `native_bundle.py`。正式启动不允许用 portable fallback 掩盖原生模型或 sklearn 运行时不兼容。

### 8.6 效能服务 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 模型和运行包健康 |
| GET | `/api/v1/schema` | 产品、字段和目标协议契约 |
| POST | `/api/v1/evaluate` | 单方案效能、可行性和轮廓评价 |
| POST | `/api/v1/evaluate/batch` | 批量评价，最多 1000 条 |
| POST | `/api/v1/improve` | 生成改进建议，取决于后端能力 |
| GET | `/openapi.json` | OpenAPI 3.0 |
| GET | `/docs` | 简易接口测试页 |

效能服务优先读取 `services/effectiveness_service/model/current/effectiveness_runtime_manifest.json`，也支持显式提供原工程 `source-root + workbook + state` 或快照兼容模式。

## 9. 配置与环境变量

### 9.1 主应用

| 环境变量 | 含义 | 默认值 |
| --- | --- | --- |
| `IPDEMO_HOST` | 主应用监听地址 | `127.0.0.1` |
| `IPDEMO_PORT` | 首选端口 | `17891` |
| `IPDEMO_PORT_SPAN` | 自动找空闲端口范围 | `10` |
| `IPDEMO_OPEN_BROWSER` | 是否自动打开浏览器 | `1` |
| `IPDEMO_AUTH_ENABLED` | 是否启用登录 | 开发入口默认关闭，标准 BAT 主动开启 |
| `IPDEMO_AUTH_USERNAME` | 登录用户名 | `ab123` |
| `IPDEMO_AUTH_PASSWORD` | 登录密码 | `ab123` |
| `IPDEMO_AUTH_SECRET` | Cookie 签名密钥 | 未设置时本机生成 |
| `IPDEMO_AUTH_TTL_SECONDS` | 登录有效期 | 8 小时 |
| `IPDEMO_DEMO_READ_ONLY` | 禁止持久化写操作 | `0` |
| `IPDEMO_DISABLE_ADMIN` | 禁用数据管理中心 | `0` |

正式交付必须修改默认账号、密码和认证密钥，不应直接暴露到公网。

### 9.2 模型服务

| 环境变量 | 含义 |
| --- | --- |
| `IPDEMO_MODEL_EXECUTION_MODE` | `services` 或本地兼容模式 |
| `IPDEMO_PRICE_SERVICE_URL` | 价格服务地址 |
| `IPDEMO_EFFECT_SERVICE_URL` | 效能服务地址 |
| `IPDEMO_MODEL_SERVICE_TIMEOUT` | HTTP 超时秒数 |
| `IPDEMO_MODEL_SERVICE_FALLBACK` | 是否允许主应用本地回退 |
| `IPDEMO_MODEL_SERVICE_BATCH_SIZE` | 主应用批量调用大小 |
| `PRICE_NATIVE_BUNDLE` | 原生价格模型路径 |
| `PRICE_ALLOW_MODEL_FALLBACK` | 价格模型 fallback，正式模式应为 `0` |
| `EFFECT_RUNTIME_PACKAGE` | 效能运行清单路径 |
| `EFFECT_SOURCE_ROOT` / `EFFECT_WORKBOOK` / `EFFECT_STATE` | 原效能工程路径 |

## 10. 开发与测试

项目测试多数是可直接执行的 Python 脚本，不依赖 pytest 收集器。

```bat
python tests\v21_3_guided_diverse_generation_test.py
python tests\v21_3_closure_hotfix_test.py
python tests\v21_2_numeric_special_state_test.py
python tests\scenario_frontend_backend_consistency_test.py
python tests\scenario_state_closure_test.py
python tests\v21_workflow_portal_workbench_test.py
```

生成算法重点回归：

```bat
python tests\beam_multi_round_test.py
python tests\fast_beam_multiround_test.py
python tests\generation_budget_hard_cap_test.py
python tests\generation_fingerprint_test.py
python tests\joint_explicit_filter_conflict_test.py
python tests\emergency_anchor_invariant_test.py
python tests\constraint_projection_test.py
python tests\coupling_pair_priority_test.py
```

服务验证运行 `CHECK_MODEL_SERVICES.bat`。该检查在服务健康之后继续执行 Schema 和真实 predict/evaluate，不把“端口已监听”等同于模型可用。

## 11. 离线部署与源码更新

### 11.1 完整离线运行

完全断网机器必须使用已准备好的 Python 3.8 runtime 和依赖。源码本身不能解决 sklearn、numpy、scipy 等二进制兼容问题。

- `PREPARE_OFFLINE_WHEELHOUSE_PY38.bat`：联网环境准备离线依赖；
- `BUILD_OFFLINE_DELIVERY_PY38.bat`：生成离线交付包；
- `START_OFFLINE_WIN7.bat`：从包内运行时启动；
- `BUILD_SOURCE_DEPLOYMENT_NO_WHEELS.bat`：构建不带依赖的源码包。

价格模型如果由 sklearn 0.24.x 训练，价格服务必须使用实际 smoke 通过的兼容运行时。不要重新导出或自动 fallback 来掩盖 `_loss`、pickle 类型或自定义树节点加载问题。

### 11.2 BuildKit 的 `source` 目录

```text
IPDemo_Onedir_Offline_BuildKit/
  runtime/     # 编译运行时，不随源码替换
  wheels/      # 离线依赖，不随源码替换
  tools/       # BuildKit 编译工具
  source/      # 本仓库源码、配置、模型和业务基线
```

更新业务代码时，可以替换 `source` 后重新执行 `BUILD_ONEDIR_WIN7.bat`。必须确认 source 来自确定的 Git 提交，不能把开发机未提交的模型或数据库改动混入现场包。

### 11.3 运行安装的源码热更新

如果甲方已有可正常运行的完整源码安装，可以只替换 `app` 和 `run_app.py`，继续使用现场现有的 runtime、模型、数据库和配置。运行安装热更新和 BuildKit source 替换不能混用：

| 场景 | 替换内容 | 后续动作 |
| --- | --- | --- |
| 已安装源码系统 | `app`、`run_app.py` | 重新启动三服务 |
| 离线 BuildKit | 整个 `source` | 重新运行 `BUILD_ONEDIR_WIN7.bat` |

## 12. 安全与维护注意事项

- 不要提交现场数据库、Portal 备份、日志、运行时或个人路径配置。
- 不要把开发人员电脑的绝对 Python 路径写入仓库；使用 `runtime/service_runtime.local.bat`。
- 修改数据库、模型和配置前先创建可恢复备份。
- 不要把 DataMaster、Schema 或训练范围升级为隐式硬规则。
- 不要让显示映射进入数据库值、生成值或模型值。
- 不要绕过用户显式排序、冻结参数或技术条件。
- 修改生成算法时同时验证 Branch、Family、Fingerprint、预算上限和三层输出语义。
- 修改服务接口时同步更新 `/openapi.json`、Workbench 和本文档。

## 13. 延伸文档

- `docs/api/MODEL_SERVICES_API.md`：模型服务接口；
- `docs/EFFECTIVENESS_ARTIFACT_CONSUMPTION_V11.md`：效能产物复用边界；
- `docs/CLEAN_WIN7_DEPLOYMENT_V19_6_13.md`：Win7 clean 部署；
- `docs/PRICE_TRAINING_AND_OFFLINE_ENVIRONMENT.md`：价格训练与离线环境；
- `docs/DATABASE_ADMIN_GUIDE.md`：数据库管理；
- `docs/DATAMASTER_GUIDE_V19_6.md`：DataMaster；
- `docs/操作人员手册_测试数据运行与成品更换.md`：现场操作流程。

如果代码行为与历史文档冲突，以当前代码、当前 API Schema 和本文“核心设计原则”为准；涉及模型工程结论时，以实际模型服务返回和经确认的工程硬规则为准。
