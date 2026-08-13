# V19.6 离线交付压缩包与现场部署说明

本交付采用多个**相互独立的普通 ZIP**，不是分卷压缩。每个 ZIP 都可以单独打开和完整解压，不存在 `.z01`、`.z02`、`.part1.rar` 等分卷文件。

## 一、压缩包用途

| 压缩包 | 是否运行必需 | 内容 |
|---|---:|---|
| `01_Core_And_Price_Base.zip` | 是 | 主程序、配置、数据库、当前价格/效能模型、文档、演练成品、价格基础依赖 |
| `02_Price_XGBoost_Runtime.zip` | 是 | XGBoost 1.7.6 Windows 64 位离线 wheel |
| `03_Effectiveness_Runtime_Wheels.zip` | 是 | NumPy、SciPy、openpyxl 等效能运行依赖 |
| `04_Price_Training_Extra_Wheels.zip` | 否 | pandas、matplotlib、Notebook、Jupyter 等价格训练附加依赖 |

只部署并运行系统时需要前三个包。需要在断网电脑上重新训练价格模型时，再增加第四个包。

虚拟环境没有装入压缩包。Python venv 记录了创建电脑上的绝对路径，整体复制到另一台电脑不可靠，也会让交付体积增加约 926MB。现场应使用离线 wheel 重新创建环境。

## 二、目标机外部前置条件

以下安装程序当前项目中没有提供，需要交付人员另行准备并核对授权：

1. 64 位 CPython 3.8 安装程序；
2. 与目标 Windows 7 镜像匹配的 Microsoft Visual C++ 运行库；
3. 项目既有部署文档要求的 Windows 7 系统补丁。

不要在目标机联网执行 `pip install`。全部 Python 包应从解压后的 wheelhouse 安装。

## 三、解压方法

1. 在目标机创建一个空目录，例如 `D:\IndustrialProtocolDemo_V19_6`。
2. 分别打开所需 ZIP，把每个 ZIP 的内容完整解压到这个**同一个目录**。
3. 出现目录合并提示时允许合并。正常情况下不会覆盖不同版本文件。
4. 不要使用“合并分卷”“解压第一卷”等功能；这些文件不是分卷。
5. 使用 `SHA256SUMS.txt` 校验每个 ZIP，任何一个哈希不一致都停止部署。

前三个包解压完成后应同时存在：

```text
app\
services\price_service\wheelhouse_win7\
services\effectiveness_service\wheelhouse_win7\
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
START_ALL_SERVICES_WIN7.bat
```

## 四、创建运行环境

在项目根目录打开命令提示符。若系统不能自动找到 Python 3.8，先设置：

```bat
set PYTHON38_EXE=C:\Python38\python.exe
```

然后执行：

```bat
CREATE_MODEL_RUNTIME_ENV_WIN7.bat
VERIFY_MODEL_ENVIRONMENTS.bat
```

脚本会创建 `runtime\venvs\model_runtime38`，只从本地 wheelhouse 安装依赖，并对当前价格和效能模型执行加载冒烟测试。

需要训练价格模型时，先解压第四个包，再执行：

```bat
CREATE_PRICE_TRAINING_ENV_PY38.bat
RUN_PRICE_TRAINING_ENV_TEST.bat
```

## 五、启动与检查

```bat
START_ALL_SERVICES_WIN7.bat
CHECK_MODEL_SERVICES.bat
```

检查地址：

```text
推荐主系统：http://127.0.0.1:17891/
数据管理中心：http://127.0.0.1:17891/admin
价格服务：http://127.0.0.1:18101/docs
效能服务：http://127.0.0.1:18102/docs
```

正式运行预期：

```text
price backend = native_pickle
effectiveness backend = original_effectiveness_runtime
推荐主系统 = independent_http_services
```

## 六、航空舱门锁演练数据

航空舱门锁虚拟数据随第一个包交付，位置为：

```text
outputs\aircraft_door_lock_data_staff_20260801\
```

先阅读其中的 `数据人员试用说明.md`。只读验包使用：

```bat
VERIFY_AIRCRAFT_DOOR_LOCK_DEMO_WIN7.bat
```

安装航空舱门锁演练成品会替换当前两个模型，并把业务数据导入待发布草稿。安装前必须停止三个服务并记录安装器返回的 `backup_id`。

## 七、验收记录

现场至少记录以下信息：

```text
目标机编号：
Windows版本及补丁：
Python版本及位数：
四个ZIP的SHA-256校验结果：
运行环境验证结果：
价格服务backend/model_version：
效能服务backend/model_version：
当前product_code：
航空舱门锁演练是否安装：
安装backup_id：
业务草稿release_id：
回滚验证结果：
操作人员与日期：
```

## 八、重新构建交付包

在联网或开发电脑的项目根目录执行：

```bat
BUILD_OFFLINE_DELIVERY_ARCHIVES.bat D:\目标输出目录
```

构建器拒绝写入非空目录，防止覆盖已有交付物；还会检查所有 ZIP 是否小于等于 80MiB，并生成 `DELIVERY_MANIFEST.json` 和 `SHA256SUMS.txt`。
