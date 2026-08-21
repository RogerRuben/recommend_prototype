# 工业技术协议智能推荐系统 V21

V21 聚焦推荐工作流体验、统一服务导航与简易 Workbench：推荐条件栏支持调整宽度，技术指标按分组检索并提示标签覆盖关系；登录默认进入可配置的五入口 Portal；价格和效能 Workbench 使用同一个确定性历史协议作为示例，并由 DataMaster 补充中文字段、单位与显示映射。实现和运维边界见 `docs/V21_WORKFLOW_PORTAL_WORKBENCH.md`。

V20 确立的业务语义继续保持：DataMaster、模型 Schema 与训练范围是非阻断诊断元数据；用户显式业务值不会被参考范围静默截断；显示文本变化不会改变数据库、生成或模型输入。详细规则见 `docs/V20_RECOMMENDATION_REFACTOR.md`。

当前 clean 运行主线：双独立 HTTP 模型服务、原 Notebook 任意模型子集一键导出、独立价格/效能工作台、数据中心可视化指标约束，以及仅以实算 JSON 为准的宽松服务准入。Win7 安装和最终测试见 `docs/CLEAN_WIN7_DEPLOYMENT_V19_6_13.md`。

V19.6在V19.5共享价格／效能属性基础上持续完成数据生命周期治理、模型服务解耦、显式计算和待发布成品工作区重构。随包演示成品和模型只用于验证流程，不代表真实工程结论。

V11 效能模型采用“专家端在线学习、推荐系统只读复用产物”的边界设计，详见 [效能产物复用与服务边界](docs/EFFECTIVENESS_ARTIFACT_CONSUMPTION_V11.md)。需要不含离线 wheels 的源码交付时，运行 `BUILD_SOURCE_DEPLOYMENT_NO_WHEELS.bat`；在可联网或可访问内部 pip 镜像的目标机上，使用 `INSTALL_SOURCE_DEPENDENCIES_WIN7.bat` 创建运行环境。

## 推荐启动方式

本地Windows 7建议使用64位Python 3.8。

### 三服务模式

```bat
START_ALL_SERVICES_WIN7.bat
```

默认端口：

```text
价格预测服务：http://127.0.0.1:18101/docs
效能预测服务：http://127.0.0.1:18102/docs
智能推荐系统：http://127.0.0.1:17891/
数据管理中心：http://127.0.0.1:17891/admin
```

推荐系统将完整方案JSON并行发送给两个模型服务。价格服务和效能服务自行选择字段、执行预处理和推理。

V19.6.1开始，三服务模式直接以两个服务的`/api/v1/schema`构建字段目录，不再由项目内置JSON bundle决定成品代号、字段角色和生成字段。`config/model_services.json`是默认配置来源，环境变量仅用于明确覆盖；正式服务模式默认关闭本地模型回退。

V19.6.2开始，成品业务数据可以先进入独立“待发布成品”草稿。模型服务切换后即使当前运行数据库暂时不匹配，管理中心仍可进入；推荐和计算会明确暂停，直到对应草稿校验并激活。

### 单进程兼容模式

```bat
START_ALL_WIN7.bat
```

该模式继续使用项目内置模型，适合服务尚未部署时的演示和故障回退。

## 模型服务

价格服务支持：

- `native_pickle`：直接加载原Notebook导出的完整原生模型包；
- `portable_json`：无NumPy、scikit-learn、XGBoost和joblib依赖的演示后备模式。

原生价格包使用Python标准库pickle协议4，包含原Scaler、原拟合模型、字段顺序、集成权重、log逆变换、单位换算和残差校准。它不依赖joblib，但仍要求安装模型对象本身需要的scikit-learn和可选XGBoost。

效能服务支持：

- `original_effectiveness_runtime`：直接运行原效能源码、Workbook和可选State；
- `snapshot_json`：当前演示模型兼容模式。

原运行时模式不会把效能工程近似重写成另一个模型。

接口文档：

- `docs/api/MODEL_SERVICES_API.md`
- `docs/MODEL_SERVICE_DEPLOYMENT_WIN7.md`
- 两个服务各自的`/docs`和`/openapi.json`

## 数据生命周期管理

管理页面中的标签、标签规则、耦合关系、约束规则和协议采用：

```text
启用 → 停用/归档 → 依赖检查 → 自动备份 → 永久删除
```

列表直接提供启用/停用操作。普通删除实际为归档，可以恢复。永久删除只对已停用且无引用的记录开放。停用标签下的规则仍可编辑保存，但暂不参与推荐。

当前业务成品不能在普通表格中直接停用，应通过成品数据工作区备份并切换。指标启停不受当前HTTP模型字段约束。

## 成品数据工作区

管理中心的“成品数据工作区”支持四种并行维护方式：

- 在网页中逐条新增、编辑和删除成品信息、指标、标签、标签规则、耦合、约束和历史协议；
- 为上述任一模块单独上传CSV或XLSX，不再要求一张工作簿一次构建整个项目。
- 直接上传包含价格与属性的普通历史成品 CSV/XLSX，指定 `-1`、`\`、`/` 等缺失符，由系统推断字段类型、允许值和必填性并建立草稿；
- 下载草稿维护工作簿，在 Excel 中修订后整体回导当前草稿。

自动推断会把任一行曾经缺失的属性设为非必填。列名具有“是否/有无”语义时，0/1 推断为布尔；含义不明确的 0/1 保留为枚举并标记人工确认。编辑单条历史协议时，属性显示为独立输入框，无需手写 `params JSON`。

新建空白草稿不会读取当前价格/效能服务Schema；从历史表建立草稿也不依赖当前模型。文件预览只检查表格格式和单元格类型；“检查业务数据（可选）”只检查数据库可写性和本地跨模块引用，不比较模型成品、模型字段、单位或必填性。

当前双模型未使用的业务扩展指标会按普通业务字段保留，可继续用于界面展示、筛选和业务规则。模型所需字段是否齐全只在点击计算时由对应HTTP服务处理。

“备份并切换业务数据”是唯一影响运行数据的操作。系统先备份SQLite数据库，再原子替换成品主数据；不会调用模型或重新计算导入的历史协议。原DataMaster仍保留为批量迁移和完整导入入口，但不再是唯一维护方式。

### 断网电脑离线发布

开发机与甲方断网机之间可以使用单个离线发布包：

```text
开发机：复制当前运行数据或建立草稿 → 分模块维护 → 导出完整离线发布包
断网机：导入离线发布包 → 进入草稿 → 检查业务数据（可选） → 备份并切换
```

发布包包含七个业务模块，并带有规范化JSON的SHA256传输完整性校验。SHA256用于发现文件损坏或意外改动，不代表数字签名或发布者身份认证。导入发布包不会直接写入运行主数据；后续业务切换也不读取当前机器上的模型契约。

每个草稿模块均可单独下载UTF-8 CSV模板；历史协议模板会根据该草稿的指标和标签动态生成。也可以点击“复制当前运行数据为草稿”，在现有成品基础上修改，避免从空表重新维护。

### 价格、效能和成品数据统一交付

V19.6.4新增统一离线交付包，将正式价格原生bundle、正式效能运行包和上述成品数据发布包绑定为一个ZIP。构建阶段可对这一套已配套产物做交付验收；安装阶段重新校验文件SHA-256，自动备份旧模型及SQLite，并把业务数据导入为草稿。安装不会自动切换业务数据，由用户检查后确认；数据中心本身不以模型契约作为切换门禁。

```bat
BUILD_PRODUCT_DELIVERY_WIN7.bat --price-model <价格pkl> --effectiveness-package <效能运行包目录> --business-release <成品数据json> --output <交付zip>
VERIFY_PRODUCT_DELIVERY_WIN7.bat <交付zip> --expected-sha256 <已确认摘要>
INSTALL_PRODUCT_DELIVERY_WIN7.bat <交付zip> --expected-sha256 <已确认摘要>
ROLLBACK_PRODUCT_DELIVERY_WIN7.bat <安装返回的备份ID>
```

完整操作和正式/演示模型边界见`docs/PRODUCT_DELIVERY_WIN7.md`。

### 虚拟正式成品验收基线

V19.6.5新增确定性的`VIRTUAL_COUPLED_ACTUATOR`验收基线，覆盖价格专用、效能专用和共有属性，连续/整数/布尔/IP/枚举类型，10个标签、6条耦合及40条协议。基线会生成原生`price_native_bundle.pkl`，并调用原效能`ProjectApp`模拟专家偏好与可行性证据，保存Workbook+State正式运行包。

```bat
RUN_VIRTUAL_FORMAL_PRODUCT_E2E_WIN7.bat
```

该测试在隔离目录内完成统一包安装、双模型HTTP服务、草稿激活、推荐生成、显式计算和回滚，不会替换当前项目的运行模型与数据库。当前为32项PASS，详细说明见`docs/VIRTUAL_FORMAL_PRODUCT_BASELINE.md`。

面向现场操作人员的启动、安装、草稿激活、回滚以及正式新成品配置流程，见`docs/操作人员手册_测试数据运行与成品更换.md`。

## DataMaster

项目内置：

```text
data_master/DataMaster_Current.xlsx
data_master/DataMaster_Template.xlsx
```

V19.6工作簿包含10张表：

```text
填写说明
字典_下拉项
成品信息
指标定义
标签字典
标签规则
耦合关系
约束规则
历史协议
模型字段绑定
```

所有固定类型字段提供Excel下拉；标签编号和指标编号等引用字段使用动态下拉。布尔字段的定义与取值明确分开：

```text
指标定义：取值类型=布尔，搜索类型=布尔开关
历史协议/规则条件：实际值填写有或无
数据库内部：系统自动转换成1或0
```

模板保留当前模型必需的指标定义和字段绑定，可以直接填写业务主数据并回导。

## 价格Notebook原生导出

使用：

```text
规范版价格预测_V19_6原生服务导出补丁.ipynb
```

在原Notebook全部模型和集成权重计算完成后运行最后一个单元格，即可生成：

```text
services/price_service/model/price_native_bundle.pkl
```

正式使用前必须核对价格单位和字段编号，并执行原Notebook预测与服务预测的一致性测试。

## 效能原工程接入

设置：

```bat
set EFFECT_SOURCE_ROOT=D:\effectiveness_project
set EFFECT_WORKBOOK=D:\effectiveness_project\data\product.xlsx
set EFFECT_STATE=D:\effectiveness_project\interactive_project\state_xxx.json
```

再运行`START_EFFECTIVENESS_SERVICE_WIN7.bat`。没有State时为Workbook基线，不应声称包含专家学习结果。

## 智能推荐与生成

V19.6保留此前功能：非阻塞生成、稳定批次、需求锚定、反向轮廓补偿、价格目标搜索、混合属性邻域、标签规则分支、探索方案、动态重评估，以及共享／效能专用／价格专用属性编辑。

两个模型服务已经提供批量接口。V19.6.2在输出目标搜索的同一轮独立属性扫描中使用批量评价；依赖前一步结果的累计坐标下降和属性组合搜索仍保持顺序评价，以避免改变自适应搜索语义。批量接口缺少候选结果时会明确报错，不会把候选和结果错配。

方案详情中的属性修改不会自动调用模型。界面会将当前结果标为“已过期”，只有点击“重新计算价格与效能”后才请求模型服务。保存专家方案时，后端会核对本次显式计算的参数哈希，禁止把旧结果绑定到已经修改的参数。

## Python 3.8 离线模型与价格训练环境

原价格 Notebook 的 Lasso、Ridge、SVR、GBDT、ExtraTrees、RandomForest、
XGBoost 训练流程未被重写；当前改动集中在训练后原生 bundle 导出、严格加载和
离线部署。

断网运行机：

```bat
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
```

价格训练开发机：

```bat
CREATE_PRICE_TRAINING_ENV_PY38.bat
RUN_PRICE_TRAINING_ENV_TEST.bat
RUN_PRICE_TRAINING_NOTEBOOK_PY38.bat
```

随包提供 Python 3.8/Win64 离线 wheelhouse、固定依赖清单和 SHA-256 Manifest。
完整说明见 `docs/PRICE_TRAINING_AND_OFFLINE_ENVIRONMENT.md`。

## 验证

```bat
RUN_FULL_PIPELINE_TEST.bat
```

专项测试：

```bat
python tests\v19_6_service_governance_test.py
python tests\product_release_workspace_test.py
python tests\product_delivery_test.py
runtime\venvs\price_training38\Scripts\python.exe tests\price_training_environment_test.py
```

详细结果见：

- `docs/V19_6_VALIDATION_REPORT.md`
- `logs/full_pipeline_test_report.json`
- `logs/v19_6_service_governance_report.json`
