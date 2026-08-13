# Windows 7 / Python 3.8 模型服务部署

## 推荐结构

推荐系统与模型服务分开；价格和效能模型使用已经共同验收的 Python 3.8
运行环境：

```text
推荐系统解释器                         推荐系统主进程
runtime\venvs\model_runtime38         价格服务 + 效能服务
runtime\venvs\price_training38        只供开发人员运行价格Notebook，不用于现场服务
```

断网运行机先执行：

```bat
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
```

## 一键演示启动

`START_ALL_SERVICES_WIN7.bat`会启动价格服务、效能服务并在健康检查通过后启动推荐系统。默认价格和效能使用项目自带兼容模型，能够在没有XGBoost/joblib时运行。

## 价格正式精确模式

正式模式将完整的`price_native_bundle.pkl`放到：

```text
services/price_service/model/price_native_bundle.pkl
```

该文件由原价格Notebook最后一个导出单元格生成，包含Scaler、同一批拟合模型、字段顺序、集成权重、log逆变换和残差校准。使用Python标准库`pickle`协议4，因此不要求安装joblib。

加载pickle时仍然必须安装模型类型对应的库。若集成包含XGBoost，就必须安装与训练环境兼容的XGBoost；若正式环境没有XGBoost，应在训练阶段明确导出不含XGBoost的经重新验收模型组合，而不能在生产中静默跳过。

## 效能正式运行模式

新成品优先使用最终 V11 专家软件的冻结导出：

```bat
INSTALL_FROZEN_EFFECTIVENESS_MODEL_WIN7.bat
```

选择专家软件导出的 `effectiveness_model_*.zip`。安装器验包、试算并备份后，
`START_EFFECTIVENESS_SERVICE_WIN7.bat` 会自动识别
`frozen_effectiveness_runtime`。旧成品继续兼容下述源码＋Workbook＋State方式。

### 旧 Workbook＋State 兼容方式

设置：

```bat
set EFFECT_SOURCE_ROOT=D:\effectiveness_project
set EFFECT_WORKBOOK=D:\effectiveness_project\data\product.xlsx
set EFFECT_STATE=D:\effectiveness_project\interactive_project\state_xxx.json
```

再运行`START_EFFECTIVENESS_SERVICE_WIN7.bat`。未设置State时启动Workbook基线模型，服务状态会明确标记`baseline`。

项目附带价格和效能 Win64/Python 3.8 离线 wheelhouse，可运行：

```bat
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
```

## 依赖缺失策略

- 推荐系统与两个服务的HTTP框架仅使用Python标准库。
- 价格便携兼容模式不需要NumPy、scikit-learn、XGBoost或joblib。
- 价格精确模式必须拥有被pickle对象实际引用的库，缺少时启动失败并显示具体错误；不伪造预测。
- 效能原运行时需要NumPy、SciPy和openpyxl；离线wheelhouse已随包提供。
- 服务不可用时，推荐系统默认回退当前本地模型并记录`service_error`。正式验收环境可设置`IPDEMO_MODEL_SERVICE_FALLBACK=0`禁止回退。

训练环境、固定版本、wheelhouse Manifest 和目标 Win7 镜像验收要求见
`docs/PRICE_TRAINING_AND_OFFLINE_ENVIRONMENT.md`。

## 效能运行包一键固化

无需手工维护多个路径，可以运行：

```bat
PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat
```

它将原效能源码、Workbook和可选State复制为一个自包含运行包，写入文件哈希和学习指纹，并在发布前实际重建`ProjectApp`验证。之后启动脚本自动读取`services/effectiveness_service/model/current/effectiveness_runtime_manifest.json`。

该脚本是兼容入口，不替代最终 V11 专家软件自身的“冻结并导出模型”。新成品
应优先安装冻结 ZIP；两个格式由同一效能服务自动识别。

## 防止静默换模型

当`price_native_bundle.pkl`存在但因缺少scikit-learn/XGBoost或版本不兼容而加载失败时，价格服务默认直接启动失败，不会静默改用便携模型。只有显式传入`--allow-model-fallback`才允许回退。服务`/health`会始终显示实际后端。
