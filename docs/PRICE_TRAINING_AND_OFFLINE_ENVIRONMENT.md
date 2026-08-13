# 价格模型训练与离线环境说明

## 1. 推荐入口：一张历史成品表直接生成价格服务模型

现在不再要求操作人员打开 Notebook，也不需要准备 `model-dir`、固定数量的模型文件
或手工集成权重。推荐直接双击：

```bat
TRAIN_PRICE_SERVICE_MODEL_WIN7.bat
```

依次填写：

1. 历史成品 CSV/XLSX 路径；
2. 成品代号（必须与效能服务包一致）；
3. 可选成品名称；
4. 可选价格列名（回车会自动识别“价格”“价格(万元)”等列）。

脚本会自动完成：缺失价格行剔除、属性类型推断、中文是/否与枚举编码、非必填
属性补全、训练/测试拆分、可用算法训练、权重计算和独立服务 bundle 导出。某一个
可选算法训练失败不会阻止其余模型打包；至少一个模型成功即可生成：

```text
services\price_service\model\price_native_bundle.pkl
services\price_service\model\price_native_bundle.pkl.manifest.json
services\price_service\model\price_native_bundle.pkl.training.json
```

命令行等价入口：

```bat
runtime\venvs\price_training38\Scripts\python.exe tools\train_price_service_model.py 历史成品.xlsx PRODUCT_CODE
```

直接运行且不带参数时只显示帮助，不再报缺少 `model-dir`、`workbook` 等旧参数。

## 2. 兼容的 Notebook 导出逻辑

原价格 Notebook 的训练算法没有被重写。当前仍保留原来的 Lasso、Ridge、SVR、
GBDT、ExtraTrees、RandomForest、XGBoost 训练和调参流程。

本轮调整的是训练完成后的工程化链路：

1. 导出器只打包本次实际训练或实际保存的模型，不再强制要求固定七模型齐全；
2. 原生 `price_native_bundle.pkl` 保留 scaler、模型对象、特征顺序、集成权重、
   输出变换、字段元数据和训练环境；
3. Manifest 记录模型来源、文件 SHA-256 和 `required_modules`；
4. 服务严格按 bundle 声明的成员计算，不会因为缺少某个旧模型而静默换算法；
5. 增加 Python 3.8 隔离训练环境、运行环境、离线 wheelhouse 和自动验收脚本。

`tools/synthetic_models.py` 只用于虚拟成品全链路验收，不是正式价格训练算法。

旧 Notebook 仍可使用。现在 Notebook 中遗留的固定七模型权重与本次实际模型数量
不一致时，会自动忽略旧权重并使用等权重；只有调用方明确传入错误长度的权重时才
报错。导出器只打包本次真正存在的模型。

## 3. 随包提供的依赖

### 3.1 正式模型运行环境

固定依赖清单：

```text
services\price_service\requirements_win7_exact.txt
services\effectiveness_service\requirements_win7.txt
```

统一创建脚本：

```bat
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
```

它会创建：

```text
runtime\venvs\model_runtime38
```

并完全使用两个随包 wheelhouse 离线安装，然后加载当前价格模型与效能模型做冒烟
验证。旧入口 `INSTALL_PRICE_EXACT_DEPS_WIN7.bat` 和
`INSTALL_EFFECTIVENESS_SERVICE_DEPS_WIN7.bat` 也会转到这个统一脚本。

### 3.2 价格训练环境

固定依赖清单：

```text
services\price_service\requirements_training_py38.txt
```

创建脚本：

```bat
CREATE_PRICE_TRAINING_ENV_PY38.bat
```

它会创建：

```text
runtime\venvs\price_training38
```

训练环境在正式模型运行依赖之外，还包含 pandas、openpyxl、matplotlib、seaborn、
Notebook 和 ipykernel。

### 3.3 离线 wheelhouse

```text
services\price_service\wheelhouse_win7
services\effectiveness_service\wheelhouse_win7
```

价格 wheelhouse 当前有 109 个 wheel，合计 199099380 字节；效能 wheelhouse
当前有 4 个 wheel，合计 57339176 字节。每个目录都有
`WHEELHOUSE_MANIFEST.json`，记录目标平台、文件大小和 SHA-256。

需要重新下载时，只能在可信的联网 Windows 电脑上执行：

```bat
DOWNLOAD_PRICE_TRAINING_WHEELS_PY38_WIN64.bat
```

下载完成后应把整个 wheelhouse 和 Manifest 一起复制到断网电脑。现场断网电脑
不应执行下载脚本。

## 4. 开发人员继续使用 Notebook（可选）

### 第一步：准备 64 位 Python 3.8

如果系统不能自动找到 Python 3.8，先设置：

```bat
set PYTHON38_EXE=D:\Python38\python.exe
```

### 第二步：创建训练环境

```bat
CREATE_PRICE_TRAINING_ENV_PY38.bat
```

### 第三步：验证训练和导出工具链

```bat
RUN_PRICE_TRAINING_ENV_TEST.bat
```

成功时会显示 `PASS`，详细报告位于：

```text
logs\price_training_environment_test_report.json
```

这个测试会实际执行：

- Ridge、SVR、GBDT、XGBoost 训练；
- pandas/openpyxl Excel 读写；
- matplotlib/seaborn 绘图；
- `price_native_bundle.pkl` 导出和重新加载；
- 训练对象集成预测与原生 bundle 预测等价性；
- 业务字段 ID 顺序和运行依赖记录校验。

### 第四步：打开正式 Notebook

```bat
RUN_PRICE_TRAINING_NOTEBOOK_PY38.bat
```

Notebook 文件：

```text
规范版价格预测_V19_6原生服务导出补丁.ipynb
```

选择 `Industrial Price Training (Python 3.8)` 内核，按原流程训练。完成全部模型和
集成权重计算后，再运行最后的原生导出单元格。

正式输出：

```text
services\price_service\model\price_native_bundle.pkl
services\price_service\model\price_native_bundle.pkl.manifest.json
```

## 5. 正式模型交付前必须检查

1. `product_code` 与效能模型、成品数据一致；
2. `feature_order` 使用稳定业务字段 ID，不是仅供展示的中文列名；
3. 字段类型、单位、枚举映射与成品属性定义一致；
4. `target_divisor_to_wan` 与训练目标单位一致；
5. Manifest 的模型成员、权重和 `required_modules` 符合预期；
6. 使用真实留出样本逐条比较 Notebook 与服务输出；
7. 使用统一成品交付包绑定价格模型、效能包和成品业务数据；
8. 在目标 Windows 7 镜像上完成安装、启动、冒烟、激活和回滚验收。

正式 bundle 反序列化依赖模型训练时使用的库。项目当前固定的
scikit-learn/XGBoost 版本已经在本机 Python 3.8 隔离环境中验证，但这不等于已在
甲方的实际 Windows 7 镜像上认证。目标机仍需确认 64 位 Python 3.8、系统补丁和
Microsoft Visual C++ 运行库能够加载这些二进制 wheel。

## 6. 常用检查命令

```bat
VERIFY_MODEL_ENVIRONMENTS.bat
runtime\venvs\price_training38\Scripts\python.exe -m pip check
runtime\venvs\model_runtime38\Scripts\python.exe -m pip check
runtime\venvs\price_training38\Scripts\python.exe tests\v19_6_service_governance_test.py
```

当前本机验收结果：

```text
训练环境专项：7项 PASS
V19.6服务与数据治理专项：24项 PASS
price_training38 pip check：PASS
model_runtime38 pip check：PASS
```
