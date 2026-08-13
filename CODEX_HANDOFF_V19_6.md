# IndustrialProtocolDemo V19.6：Codex 接手说明

## 最新增量：简化价格服务训练导出与模型停机历史推荐

- 新增 `TRAIN_PRICE_SERVICE_MODEL_WIN7.bat` 和 `tools/train_price_service_model.py`：输入一张历史成品 CSV/XLSX 与成品代号即可训练并安装独立价格服务 bundle，不再需要 `model-dir`、Notebook、固定模型数量或手工权重。
- 通用训练器自动识别价格列、中文是/否、枚举、IP等级、数值与缺失值；自动训练可用的 Ridge、Random Forest、Extra Trees、GBDT、SVR，单个可选模型失败不阻断整体导出。
- Notebook 兼容导出器遇到遗留权重数量与实际模型数不一致时自动退回等权重；显式传入的错误权重仍严格报错。
- 数据管理的模型页在独立服务模式下只读 `/health`、在线 Schema，并按当前成品属性生成示例 JSON，明确不读本地模型文件。
- 任一独立模型服务异常时主系统仍可启动，自动切换为纯历史推荐：按历史价格、业务属性和标签筛选已有成品；不伪造任何模型结果，并暂停生成、计算和改进。
- 专项测试 `tests/service_outage_historical_fallback_test.py` 8 项通过；原价格动态模型、服务治理与历史成品导入回归继续通过。

更新日期：2026-08-12

## 最新增量：历史范围内快速搜索与深度越界探索自动分流

- 生成任务启动前读取数据库中的历史价格、效能、可行性和数值属性边界，不调用模型即可判断筛选条件是否明显越界。
- 单项超过历史输出边界3%（保留浮点容差），或两个及以上维度同时越界时，自动从快速`batched_directional_beam_search`切换到`deep_extrapolation_multistage_beam_search`；范围内和浅层越界继续使用原快速算法。
- 深度算法第一轮完整执行快速探针，保证结果不劣于快速搜索；后续按轮预留预算，进行公平多种子束搜索、精英父代交叉、插值/轻度外推和逐轮收敛，最多7轮，默认预算至少360个候选。
- 前端在任务排队时立即显示“越界较多、等待时间偏长、外推预测仅供参考”，进度状态显示当前深度探索轮次；完成后结果消息继续保留相同风险提示。
- 航空舱门锁夹具：历史最低预测价12.6526万元；越界1%/2%/3%仍走快速路径，约3.6～3.7秒；越界5%自动深搜，7轮360候选约17.4秒，最优探索价12.2162万元，未达到12.0200万元时如实标记为非严格解。
- 基础航空舱门锁正式后端回归增加到20项，并新增`tests/price_boundary_generation_benchmark.py`边界性能诊断。

## 最新增量：合格候选生成算法提速

- 已确认主要瓶颈是候选搜索内部重复模型试算，而非历史成品读取：旧生成器会在每个搜索中心内部执行坐标下降试算，外层随后再次评价相同候选。
- 生成算法改为`batched_directional_beam_search`：先构造覆盖各属性方向、边界和离散值的探针，每轮仅执行一次双模型批量评价，再由真实评价结果推进下一轮搜索中心。
- 历史种子投影也由逐种子评价改成一次批量评价；所有候选在一次生成任务内按参数签名去重，模型评价不再被隐藏调用或重复计算。
- 提前收敛以“能够通过最终差异性筛选的严格新方案数量”为准，不会让未改变的历史种子虚增合格数。
- 原生价格模型批量接口改为矩阵预测：每个集成子模型每批只调用一次`predict`，同时保留逐行缺失补全、适用域提示和预测区间。
- 航空舱门锁真实双HTTP服务回归中，中等偏低价格上限下生成3个严格合格候选约2.04秒，只发出2轮批量评价、0次隐藏单方案试算；完整Pipeline 45项继续通过。

## V10兼容改进、批量推荐、业务值编码与直接交付

- V10固定协议效能包不再接收逐请求动态协议；页面锁定协议选择，主系统自动使用包内协议。
- V10没有原生反事实处方时，主系统改用两轮双服务批量邻域兼容搜索；V11仍使用原生`/api/v1/improve`。
- 历史推荐从逐条价格/效能HTTP调用改为一次批量调用；生成器按轮批量评价候选、缩减自适应预算并在已有足够严格解时提前收敛。
- `parameter_definitions`新增`model_value_mapping_json`，支持“是/否”“类型1/类型2”等业务值在模型调用前编码为0/1/2，页面和数据库继续保留业务显示值。
- 映射可在数据中心指标定义或DataMaster“模型取值映射(JSON)”列维护；无歧义的布尔和连续类型编号会自动生成映射。
- 统一交付构建器新增`--history-workbook`入口，只需原始成品表、价格模型和效能模型即可直接生成并验签成品交付ZIP。
- 新增`BUILD_DELIVERY_FROM_HISTORY_WIN7.bat`和`docs/甲方部署与成品更换流程_无Wheels.md`。
- 基础航空舱门锁正式后端夹具19项回归通过；原V11动态协议和完整生成Pipeline继续通过。

## 最新增量：业务数据中心与HTTP模型彻底解耦

- 成品草稿、普通历史表、DataMaster回导和业务成品切换不再读取或比较当前价格/效能服务Schema。
- “数据检查”只检查数据库可写性和草稿内部引用；它是可选预检，不是模型发布审批。
- 切换业务数据会先备份，但不会调用双模型、不会重算历史协议、不会同步当前模型字段绑定。
- 当前业务成品与HTTP模型成品不一致是允许状态；仅推荐/计算暂停，数据维护与再次切换继续可用。
- 模型服务重新匹配业务成品后，主系统才同步计算字段并恢复推荐计算。
- 修复中文维护工作簿下载头：使用RFC5987编码，避免`ERR_RESPONSE_HEADERS_MULTIPLE_CONTENT_LENGTH`。
- 新增真实HTTP下载回归和模型成品不一致激活回归。

## 最新增量：历史成品表自动建草稿

- 新增 `app/historical_onboarding.py`：上传普通 CSV/XLSX 历史成品宽表后，自动识别价格、属性类型、允许值、缺失情况和必填性。
- 空单元格和用户指定的 `-1`、`\`、`/` 等标识按缺失处理；任一行缺失即先推断为非必填。
- 语义明确的 0/1（是否、有无、启用等）推断为布尔；含义不明确的 0/1 保留为枚举并标记人工确认。
- 自动结果只创建待发布草稿，不依赖当前模型，也不修改运行数据库；后续业务切换也不受当前模型一致性限制。
- 草稿可下载带“自动推断报告”的维护工作簿，修改后整体回导；中途解析失败会恢复导入前草稿。
- 数据中心编辑单条草稿协议时，各属性已展开为独立输入框，不再要求维护人员手写 `params JSON`。
- 新增 `tests/historical_product_onboarding_test.py`，覆盖推断、缺失、0/1 歧义、工作簿往返和失败回滚。

## 1. 项目目标

这是一个面向工业技术协议的本地智能推荐系统。系统根据历史协议、标签、规则、耦合关系、工程约束以及价格/效能模型，完成：

- 历史方案检索与标签筛选；
- 基于历史种子的候选方案生成；
- 对候选方案计算价格、效能、可行性和效费比；
- 编辑方案后动态重新评价；
- 保存专家方案；
- 通过 DataMaster 和数据库管理页面维护业务主数据；
- 将价格预测和效能评价拆成独立 HTTP 服务。

项目的现场约束是 Windows 7、64 位 Python 3.8、离线部署。开发人员当前也会在 Windows 10 上测试。

## 2. 当前真正的代码基线

不要只使用最初的 `IndustrialProtocolDemo_V19_6_ServiceGovernance.zip`。当前最新代码应由以下两部分合成：

1. `IndustrialProtocolDemo_V19_6_ServiceGovernance.zip`；
2. `IndustrialProtocolDemo_V19_6_PriceDynamicModels_Hotfix.zip`。

第二个 Hotfix 是累计修复包，已经包含：

- 效能服务启动 BAT 静默退出修复；
- 一键启动由固定等待 3 秒改为最多等待 60 秒；
- 价格模型动态发现和动态成员预测；
- 对应测试、Notebook 和部署文档。

不要在应用该累计 Hotfix 后再重复覆盖旧版 Startup Hotfix。

当前完整交付 ZIP 本身早于后续两个 Hotfix，因此不能直接视为最新源码。

## 3. 当前架构

```text
浏览器
  │
  ▼
推荐系统 127.0.0.1:17891
  ├─ SQLite 数据库
  ├─ DataMaster
  ├─ 标签/规则/耦合/约束
  ├─ 历史检索和方案生成
  ├─ 本地 IntegratedModelRuntime（Schema、生成、回退仍依赖）
  └─ ModelServiceGateway
        ├─ 价格服务 127.0.0.1:18101
        │    ├─ native_pickle：正式原生模型
        │    └─ portable_json：演示/回退模型
        └─ 效能服务 127.0.0.1:18102
             ├─ original_effectiveness_runtime：原源码+Workbook+State
             └─ snapshot_json：演示/回退模型
```

推荐系统将一份完整参数 JSON 并行发送给两个服务。各服务自行选择字段、预处理并推理。

## 4. 主要目录

```text
app/
  server.py                 应用入口、HTTP 路由、Application 组装
  store.py                  SQLite、管理数据生命周期、审计、备份
  data_master.py            DataMaster 生成、解析、校验、提交
  model_runtime.py          本地 JSON 模型运行时
  model_contract_v4.py      本地模型契约
  model_service_client.py   价格/效能服务并行调用与结果合并
  local_generator.py        候选生成
  recommender.py            推荐逻辑
  generation_tasks.py       非阻塞生成任务
  static/                   原生 HTML/CSS/JavaScript 前端

services/
  common/http_service.py    两个模型服务共用的轻量 HTTP 框架
  price_service/
    app.py                  价格服务 API、/docs、/openapi.json
    native_bundle.py        原生 pickle 包加载和预测
    export_native_price_bundle.py  Notebook 导出工具
  effectiveness_service/
    app.py                  效能服务 API 和后端选择
    package_effectiveness_runtime.py 原工程打包工具
    model/original_demo/    演示原运行时，不是正式成品模型

data/
  protocol_demo.db          当前业务数据库

data_master/
  DataMaster_Current.xlsx
  DataMaster_Template.xlsx

models/
  effectiveness_bundle.json 本地效能 Schema/回退模型
  price_bundle.json         本地价格 Schema/回退模型

tests/
  full_pipeline_test.py
  v19_6_service_governance_test.py
  price_dynamic_model_hotfix_test.py（应用 Hotfix 后）

docs/api/
  MODEL_SERVICES_API.md
  price_service_openapi.json
  effectiveness_service_openapi.json
```

## 5. 数据管理现状

V19.6 已经实现：

- 修复管理编辑页保存按钮未关联表单的问题；
- 标签停用后，其规则仍可编辑保存；
- 标签、标签规则、耦合、约束、协议支持启用/停用；
- 普通删除改为归档；
- 永久删除前检查依赖并自动备份；
- 写入审计日志；
- 当前业务成品不能在普通表格中直接停用，需从成品数据工作区备份并切换；指标停用不再受旧模型绑定阻止。

主要入口：

- 前端：`app/static/admin.html`、`app/static/admin.js`；
- 后端：`app/server.py` 的 `/api/admin/*`；
- 数据层：`app/store.py` 的 `admin_upsert`、`admin_toggle`、`admin_delete`、`admin_purge`、`admin_dependencies`。

现有测试主要验证 Store/API 和前端代码结构，没有真正使用浏览器自动化点击全部管理操作。后续建议补 Playwright 或 Selenium E2E。

## 6. DataMaster 现状

当前工作簿有 10 张表：

1. 填写说明；
2. 字典_下拉项；
3. 成品信息；
4. 指标定义；
5. 标签字典；
6. 标签规则；
7. 耦合关系；
8. 约束规则；
9. 历史协议；
10. 模型字段绑定。

已实现：

- 枚举、布尔、搜索类型、缺失策略等下拉；
- 标签编号和指标编号动态引用下拉；
- 布尔“字段类型”和“实际取值”分开说明；
- 当前表导出、模板导出、上传预检和提交；
- 模型字段骨架保留，模板可回导。

仍需改进：

- 校验错误应精确定位到工作表、行和单元格；
- 进一步锁定模型自动生成字段，避免非专业用户误改；
- 自动从两个服务的 `/api/v1/schema` 同步字段，减少本地重复维护；
- 对超宽“历史协议”表提供更清晰的维护方式。

## 7. 价格服务现状

### 7.1 两种后端

- `native_pickle`：正式路径，加载 `services/price_service/model/price_native_bundle.pkl`；
- `portable_json`：当前内置演示回退，加载 `models/price_bundle.json`。

当前交付包没有正式 `price_native_bundle.pkl`，直接启动时看到 `backend=portable_json` 是预期现象，但不能视为正式价格模型。

### 7.2 最新动态模型 Hotfix

旧导出器错误地默认要求七个模型。最新 Hotfix 改为：

- `saved_files`：只打包实际保存并被识别的 pickle；
- `namespace`：只打包 Notebook 内当前存在的模型对象；
- `auto`：优先已保存文件，否则读取内存变量；
- 服务只运行 `bundle["ensemble"]["members"]` 中声明的成员；
- 权重按模型名选取子集并重新归一化；
- 未保存 XGBoost 时，不应要求安装 XGBoost。

默认识别：Lasso、Ridge、XGBoost、Random Forest、Extra Trees、SVR、GBDT 的常见文件名。未知 `.pkl` 不自动加载，必须通过 `saved_model_files` 显式映射，避免加载任意 pickle。

### 7.3 FIELD_METADATA

`FIELD_METADATA` 不是完整字段清单，而是覆盖项。可以设为 `{}`。

自动生成内容包括训练范围和均值。只需要覆盖：

- 与效能模型共享但列名不同的字段；
- 稳定 API 字段编号；
- 布尔/IP/整数等特殊类型；
- 单位；
- 非必填字段和缺失策略。

最新导出器会把 API 字段编号写入 `feature_order`，原训练列顺序写入 `source_feature_order`，然后用原 Scaler 处理向量。

### 7.4 已知使用问题

出现 `got an unexpected keyword argument 'model_source'`，通常表示：

- Notebook 是 Hotfix 版本，但项目中的 `export_native_price_bundle.py` 仍是旧版；或
- Jupyter 内核缓存了旧模块；或
- `sys.path` 指向了另一份项目。

处理方式：应用累计 Hotfix、设置准确项目根目录、重启 Jupyter 内核、检查 `module.__file__` 和函数签名。

### 7.5 依赖

pickle 不依赖 joblib，但模型对象仍依赖训练时使用的库。正式模型可能需要：

- NumPy；
- SciPy；
- scikit-learn；
- 可选 XGBoost。

不能在缺依赖时静默跳过某个正式模型，否则不再等价于原集成模型。

## 8. 效能服务现状

### 8.1 两种后端

- `original_effectiveness_runtime`：直接运行原效能源码、Workbook、可选 State；
- `snapshot_json`：本地兼容/演示快照。

正式效能运行包位置：

```text
services/effectiveness_service/model/current/
  effectiveness_runtime_manifest.json
  source/
  data/
  state/ 或 runtime_state/
```

当前交付包只有 `original_demo` 和本地 snapshot，没有正式 `current` 成品包。

### 8.2 打包入口

- BAT：`PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat`；
- Python：`services/effectiveness_service/package_effectiveness_runtime.py`。

输入：原源码目录、Workbook、可选 State。没有 State 时只能称为 Workbook 基线模型，不能声称包含专家学习结果。

### 8.3 依赖

原运行时通常需要：

- NumPy 1.24.4；
- SciPy 1.10.1；
- openpyxl 3.1.3；
- et-xmlfile 1.1.0。

项目携带 Python 3.8 Windows x64 离线 wheel，但目前尚未在真实 Windows 7 机器上完成全链路实测。现有验证包括 Python 3.8 语法检查和在当前测试环境中执行。

## 9. 服务 API

价格服务：

- `GET /health`；
- `GET /api/v1/schema`；
- `POST /api/v1/predict`；
- `POST /api/v1/predict/batch`；
- `GET /docs`；
- `GET /openapi.json`。

效能服务：

- `GET /health`；
- `GET /api/v1/schema`；
- `POST /api/v1/evaluate`；
- `POST /api/v1/evaluate/batch`；
- `GET /docs`；
- `GET /openapi.json`。

推荐系统通过 `app/model_service_client.py` 并行调用两个服务，并合并价格、区间、效能、可行概率、风险、外推和模型版本。

## 10. 当前启动方式

经过累计 Hotfix 后：

- `START_PRICE_SERVICE_WIN7.bat`：18101；
- `START_EFFECTIVENESS_SERVICE_WIN7.bat`：18102；
- `START_RECOMMENDATION_WITH_SERVICES_WIN7.bat`：17891；
- `START_ALL_SERVICES_WIN7.bat`：依次启动并最多等待 60 秒。

效能启动 BAT 的旧版嵌套 `IF/ELSE` 会导致未设置 `EFFECT_SOURCE_ROOT` 时所有分支都不执行；累计 Hotfix 已修复。

当前仍存在的启动技术债：

- 三个脚本都按“项目 runtime → 当前 Conda → PATH”选择 Python，并未真正配置三个独立解释器；
- 价格 BAT 直接双击时，异常仍主要进入日志，诊断体验弱于修复后的效能 BAT；
- `config/model_services.json` 当前基本没有被 `Application` 读取，实际行为由环境变量控制；
- `START_RECOMMENDATION_WITH_SERVICES_WIN7.bat` 默认 `IPDEMO_MODEL_SERVICE_FALLBACK=1`，正式验收可能发生静默本地回退。

建议后续统一成一个 Python Launcher，并支持：

```text
PRICE_PYTHON=D:\env_price\python.exe
EFFECT_PYTHON=D:\env_effect\python.exe
APP_PYTHON=D:\env_app\python.exe
```

## 11. 更换成品的现状

业务数据切换已与模型部署解耦：

1. 原始历史表可自动生成业务草稿；
2. 草稿可通过页面、分模块CSV或维护工作簿继续维护；
3. 数据检查不访问当前双模型服务；
4. 切换时只备份和替换SQLite业务数据，不执行价格/效能计算；
5. 业务成品与HTTP服务成品不一致时只暂停推荐计算。

正式计算仍需部署对应的价格原生服务模型和效能原运行时包。正式 `services` 模式不依赖本地旧bundle执行推理；本地JSON仅保留给显式允许的兼容/测试模式。统一交付Installer仍可用于一个已经完成配套验收的成品，但它的跨契约验收不应反向成为数据中心日常维护门禁。

## 12. 当前验证状态

在当前合成代码上，13个工程测试脚本已全部通过；新增验证包括：

- 中文自动维护工作簿真实HTTP下载：PASS；
- 业务成品与当前模型成品不一致时导入/检查/切换：PASS；
- 切换过程不调用模型且不预计算历史协议：PASS；
- 正式双HTTP服务虚拟成品端到端安装、激活、推荐和回滚：PASS；
- Python 3.8语法解析：PASS。

需要诚实区分：

- 这些测试证明当前代码路径和测试样本通过；
- 还没有正式业务价格训练数据和正式价格原生 bundle；
- 没有正式专家 State；
- 没有在真实 Windows 7 目标机完成全部依赖、BAT、模型和浏览器的验收；
- 现有前端管理测试不是完整浏览器 E2E。

## 13. 已确认的优先技术债

### P0：先做，避免错误部署

1. 将累计 Hotfix 合并回正式基线，不再维护“主包 + 多个补丁”的状态；
2. 增加唯一版本号和构建信息，更新 `VERSION.txt`；
3. 统一启动器，明确三个 Python 解释器、日志、端口和健康等待；
4. 正式模式默认关闭本地回退，并在 UI 明显显示当前 backend；
5. 让配置文件真正生效，解决配置文件与环境变量两套事实来源；
6. 为价格导出增加自动一致性报告：原 Notebook 推理 vs bundle 服务推理；
7. 为效能运行包增加原 `ProjectApp.evaluate` vs 服务输出的一致性报告；
8. 对产品代号、字段 ID、类型和单位做启动前强校验。

### P1：降低维护成本

1. `/schema` 成为模型字段单一真源，减少本地 JSON Schema 重复；
2. FIELD_METADATA 改为可视化表格或 DataMaster 映射，不要求在 Notebook 里写代码；
3. 制作统一“成品发布包”和一键 Installer；
4. DataMaster 错误精确到单元格；
5. 管理页增加浏览器 E2E 测试；
6. 服务批量调用增加部分失败语义、超时、重试和缓存；
7. 增加服务请求 ID、模型指纹、耗时和审计日志。

### P2：工程质量

1. 拆分过大的 `server.py`、`store.py` 和前端 `admin.js`；
2. 增加类型标注和稳定 DTO；
3. 为 SQLite 增加显式迁移版本，而不是启动时隐式补字段；
4. 增加 CI：Python 3.8、Windows 命令脚本静态检查、API 契约测试；
5. 删除重复/过时文档和旧版本模型转换代码；
6. 对 pickle 做可信路径、哈希白名单和权限控制。

## 14. Codex 修改时不要破坏的行为

- 启动智能推荐后立即返回历史参考方案，生成在后台执行；
- 生成批次稳定，旧批次可继续打开；
- 价格目标搜索、IP 等级邻域、标签规则分支和探索方案继续有效；
- 编辑参数后价格/效能动态重评估；
- 共享、效能专用、价格专用字段角色保持；
- 价格专用字段默认折叠但值不丢失；
- 标签、规则、耦合、约束和协议可启停、归档、恢复；
- 停用标签下规则仍可保存；
- DataMaster 当前表和模板均可回导；
- 正式服务不可用时不能伪造结果；是否允许回退必须显式配置并展示。

## 15. 建议的 Codex 第一轮任务

第一轮不要立即重写算法。先完成“基线收口”：

1. 以累计 Hotfix 后源码建立 Git 仓库；
2. 将版本改为 `V19.6.1`；
3. 新增 `python launcher.py doctor/start/stop/status`；
4. 支持三个解释器路径；
5. 读取一个统一 YAML/JSON 配置；
6. 默认正式模式 `fallback=false`；
7. 启动前校验两个服务的 product_code、schema_hash 和 backend；
8. UI 顶部显示价格/效能 backend、版本及是否回退；
9. 补管理页面真实 E2E；
10. 保持现有 43+21+Hotfix 测试全部通过。

## 16. V19.6.4 统一成品交付包

已经新增 `tools/product_delivery.py`，统一处理价格模型、效能模型和
`industrial-product-release-1.0` 成品数据包：

- `build`：用模型的真实加载器验证可信源文件，检查三方 `product_code`、字段 ID、类型和单位，生成 `industrial-product-delivery-1.0` ZIP 和外部 SHA-256；
- `verify`：不执行 pickle/效能源码，静态检查 ZIP 路径、文件集合、大小、SHA-256、Schema 快照和跨模型契约；
- `install`：要求三个服务已停止，先备份模型和 SQLite，再安装模型，并把成品数据导入为草稿；不会自动激活；
- `rollback`：按备份 ID 恢复安装前模型和 SQLite，覆盖前再保留当前状态快照；
- 任一步安装失败都会自动恢复已经修改的目标。

正式包必须同时使用 `native_pickle` 和 `original_effectiveness_runtime`。
`portable_json`/`snapshot_json` 只有在构建和安装命令都显式传入
`--allow-demo-models` 时才允许。

Win7 入口：

```bat
BUILD_PRODUCT_DELIVERY_WIN7.bat
VERIFY_PRODUCT_DELIVERY_WIN7.bat
INSTALL_PRODUCT_DELIVERY_WIN7.bat
ROLLBACK_PRODUCT_DELIVERY_WIN7.bat
```

详细流程见 `docs/PRODUCT_DELIVERY_WIN7.md`，专项测试为
`python tests\product_delivery_test.py`，当前共 17 项。

## 17. 常用验证命令

```bat
python tests\price_dynamic_model_hotfix_test.py
python tests\v19_6_service_governance_test.py
python tests\product_release_workspace_test.py
python tests\product_delivery_test.py
python tests\full_pipeline_test.py
```

服务检查：

```text
http://127.0.0.1:18101/health
http://127.0.0.1:18102/health
http://127.0.0.1:17891/api/health
```

正式模型预期：

```text
price backend = native_pickle
effectiveness backend = original_effectiveness_runtime
```

看到 `portable_json` 或 `snapshot_json` 表示使用的是演示/回退模型。

## 18. V19.6.5 虚拟正式成品全链路基线

已新增确定性虚拟成品 `VIRTUAL_COUPLED_ACTUATOR`，用于验收正式后端的完整
Pipeline。它包含 15 个模型业务属性（6 共有、4 价格专用、5 效能专用）、
多种数据类型、10 个标签、11 条标签规则、6 条耦合、2 条约束和 40 条协议。

主要入口：

```text
tools/virtual_product_fixture.py
tools/virtual_product_workbook.mjs
tests/virtual_formal_product_e2e_test.py
RUN_VIRTUAL_FORMAL_PRODUCT_E2E_WIN7.bat
outputs/virtual_formal_baseline/virtual_product_delivery.zip
```

价格侧生成双成员原生 pickle bundle；效能侧调用原 `ProjectApp` 模拟专家
偏好和可行性证据，并打包 Workbook+State。统一包仍以草稿方式安装，必须
在当前两个模型服务 Schema 下校验并显式激活。

Python 3.8.19 隔离环境（NumPy 1.24.4、SciPy 1.10.1、openpyxl 3.1.3）
完整验收为 32 项 PASS，覆盖安装、双 HTTP 模型、属性角色隔离、标签/耦合、
智能生成、显式计算令牌、主系统重启和回滚。验收过程中修复：

- 发布校验、启动同步和后台维护使用同一字段类型兼容规则；
- 原生价格包支持无序枚举的显式 `category_mapping`；
- 效能 Workbook 可声明稳定 `product_code`，旧 Workbook 仍兼容；
- 交付备份 ID 和回滚快照采用短路径格式并忽略可再生 Python 字节码缓存。

详细说明见 `docs/VIRTUAL_FORMAL_PRODUCT_BASELINE.md`。

## 19. Python 3.8 离线模型与价格训练环境

价格训练算法本身没有重写。原 Notebook 仍保留 Lasso、Ridge、SVR、GBDT、
ExtraTrees、RandomForest、XGBoost 及其调参流程。本轮补齐的是训练后的动态
原生导出、服务严格加载、离线依赖和可复现环境。

新增入口：

```text
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
CREATE_PRICE_TRAINING_ENV_PY38.bat
DOWNLOAD_PRICE_TRAINING_WHEELS_PY38_WIN64.bat
VERIFY_MODEL_ENVIRONMENTS.bat
RUN_PRICE_TRAINING_ENV_TEST.bat
RUN_PRICE_TRAINING_NOTEBOOK_PY38.bat
tools/verify_model_environment.py
tools/wheelhouse_manifest.py
tests/price_training_environment_test.py
```

固定依赖：

```text
services/price_service/requirements_win7_exact.txt
services/price_service/requirements_training_py38.txt
services/price_service/wheelhouse_win7
services/effectiveness_service/wheelhouse_win7
```

价格 wheelhouse 为 109 个 wheel、199099380 字节；效能 wheelhouse 为 4 个
wheel、57339176 字节，两者均有逐文件 SHA-256 Manifest。

本机 Python 3.8.19 x64 隔离验收：

- `model_runtime38` 能加载当前价格原生 bundle 和原效能运行包；
- `price_training38` 完成 Ridge/SVR/GBDT/XGBoost 训练、Excel、绘图和原生导出；
- 价格训练环境专项 7 项 PASS；
- 服务与数据治理专项 24 项 PASS；
- 两个隔离环境 `pip check` 均 PASS。

这些结果证明随包依赖与当前 Windows/Python 3.8 环境兼容，不替代甲方真实
Windows 7 镜像验收。目标机仍要核验系统补丁、VC++ 运行库、二进制 wheel
加载、服务启动、成品激活和回滚。

详细说明见 `docs/PRICE_TRAINING_AND_OFFLINE_ENVIRONMENT.md`。

## 20. 航空客舱门锁数据人员演练包

已新增确定性虚拟成品 `AIRCRAFT_CABIN_DOOR_LOCK_DEMO`，用于数据人员独立
演练成品数据上传、分模块维护、发布校验、双模型安装和显式计算。当前运行中的
`VIRTUAL_COUPLED_ACTUATOR` 未被覆盖；航空舱门锁统一包需要操作人员停止服务、
安装为草稿并显式激活后才会成为当前成品。

交付目录：

```text
outputs/aircraft_door_lock_data_staff_20260801/
```

其中包含：

- `航空舱门锁_DataMaster.xlsx`：10 个工作表，可整体导入；
- `航空舱门锁_价格训练数据.xlsx`：640 条价格样本；
- `航空舱门锁_效能项目.xlsx`：48 个历史方案和 8 条效能耦合；
- `航空舱门锁_统一成品交付包.zip`：真实四成员价格集成和原效能运行包；
- `数据人员试用说明.md`：验包、安装、激活、DataMaster、显式计算和回滚步骤。

数据共 19 个属性，覆盖连续、整数、布尔、IP 等级和无序枚举；其中效能模型
使用 14 个字段，价格模型使用 14 个字段，9 个为共有字段。业务数据另含 10 个
标签、10 条标签规则、7 条业务耦合、3 条约束和 48 条历史协议。

价格侧训练 Ridge、SVR、GBDT、XGBoost，使用 512 条训练样本和 128 条留出
样本，最佳 Ridge 留出集 R² 为 0.9631；导出的原生 bundle 与训练对象最大预测
误差为 `3.82e-7`。效能侧打包原 `ProjectApp`、Workbook 和模拟专家 State，
State 含 20 次交互、8 条可行性证据和 21 条偏好证据。

新增入口：

```text
tools/aircraft_door_lock_fixture.py
tests/aircraft_door_lock_fixture_test.py
VERIFY_AIRCRAFT_DOOR_LOCK_DEMO_WIN7.bat
INSTALL_AIRCRAFT_DOOR_LOCK_DEMO_WIN7.bat
runtime/venvs/aircraft_door_lock38/
```

本轮同时修复：

- DataMaster/宽表导入支持 enum/text，不再把无序枚举强制转为浮点数；
- 原效能服务 Schema 从 Workbook 正确识别布尔和 IP 等级字段；
- 中文交付包文件名的 SHA-256 sidecar 使用 UTF-8 写出。

专项验收 20 项 PASS；并回归统一交付包 17 项、服务治理 24 项、完整 Pipeline
45 项、发布工作区 14 项。三个工作簿逐表渲染检查通过，公式错误扫描均为 0。

## 21. 80MiB 内非分卷离线交付包

现场部署不直接复制 `runtime/venvs`。两个开发机 venv 合计约 926MiB，包含绝对
解释器路径，跨电脑复制不可靠。交付改为四个相互独立的普通 ZIP，分别完整解压
到同一个空目录；不存在 `.z01/.z02` 或 `.partN.rar` 分卷。

```text
01_Core_And_Price_Base.zip
02_Price_XGBoost_Runtime.zip
03_Effectiveness_Runtime_Wheels.zip
04_Price_Training_Extra_Wheels.zip
```

前三个为系统运行必需，第四个只在断网目标机重新训练价格模型时需要。构建器会
拒绝非空输出目录，并检查每个 ZIP 不超过 80MiB，随后生成 SHA-256 清单和 JSON
Manifest：

```text
BUILD_OFFLINE_DELIVERY_ARCHIVES.bat
tools/build_offline_delivery_archives.ps1
docs/OFFLINE_DELIVERY_ARCHIVES.md
```

2026-08-10 实际包体积为 65.00、67.66、54.19、56.93MiB。验收已逐包核对
SHA-256、重新合并解压、确认无分卷文件/venv，并在解压副本中使用全部离线 wheel
从零创建 Python 3.8.19 运行环境；价格 `native_pickle` 与效能
`original_effectiveness_runtime` 均成功加载，环境检查 PASS。

## 22. V11 效能产物只读合并与无 wheels 源码交付

2026-08-11 按“我方推荐架构为主、复用效能专家产物”的原则完成合并。效能专家的
独立应用继续负责在线学习和 State 演进；推荐系统没有嵌入该在线学习界面，只通过
正式运行包读取 `source + workbook + state + manifest` 并直接计算效能。

当前正式效能运行包：

```text
services/effectiveness_service/model/current/
product_code: VIRTUAL_COUPLED_ACTUATOR
model_version: effect-v11-355494cea084-fa079a21179c
algorithm_version: V11-PAR-UTA
profile_version: 11
```

V11 合并内容包括 P10 保守分、稳健区间、独立物理门控、逐请求动态目标协议、耦合
前沿、专家边界和反事实改进。动态协议和改进搜索使用 State 的私有运行副本，不会
改写专家交付的正式 State。V11 之前已发布的
`original-runtime-<learning_fingerprint>` 运行包保留兼容读取，仍严格校验包内文件
SHA-256 与学习指纹。

边界说明和交付工具：

```text
docs/EFFECTIVENESS_ARTIFACT_CONSUMPTION_V11.md
INSTALL_SOURCE_DEPENDENCIES_WIN7.bat
BUILD_SOURCE_DEPLOYMENT_NO_WHEELS.bat
tools/build_source_deployment_no_wheels.ps1
```

源码交付包不包含 `wheelhouse_win7`、`.whl`、虚拟环境、缓存、日志、备份和交接压缩
档，但包含当前价格模型、当前 V11 效能运行包、主数据、测试数据、源码、文档及测试。
没有网络的现场仍需另行提供依赖 wheels 或已验收运行环境；源码包本身不伪装成离线
依赖包。

验收结果：V11 Stage A 24 项、Stage B/C 32 项、服务治理 24 项、旧航空舱门锁 20
项、虚拟正式成品 32 项、统一产品交付 17 项、完整 Pipeline 45 项均 PASS；Python
3.8 x64 当前价格/效能模型环境检查 PASS。V11 物理门控会从 40 条虚拟历史协议中
排除 1 条不可行方案，因此推荐接口返回 39 条，数据库原始 40 条保持不变。
