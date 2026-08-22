# V21.1.1 Python 3.8 断网整包交付

## 交付目标

甲方 Windows x64 机器已有 64 位 Python 3.8，但不能访问互联网。交付 ZIP
包含完整应用、当前数据库、价格原生模型、效能运行包以及所有 CPython 3.8
依赖 wheels。目标机不会访问 PyPI，也不会静默切换价格模型。

## 开发机一次性准备

在可联网的 Windows 开发机运行：

```bat
PREPARE_OFFLINE_WHEELHOUSE_PY38.bat
BUILD_OFFLINE_DELIVERY_PY38.bat
```

产物位于 `deliverables\offline_py38`：

- `IndustrialProtocol_...zip`
- 同名 `.zip.sha256`

wheelhouse 明确面向 `CPython 3.8 / win_amd64`。版本以当前价格模型 manifest
为准：NumPy 1.23.5、scikit-learn 1.2.1、SciPy 1.10.1、joblib 1.1.1。

封版验证使用官方 CPython 3.8.10 x64 便携运行时，仅从该 wheelhouse 加载依赖；
价格原生 pickle 与效能模型的真实试算均通过。验证运行时只用于构建检查，不会
复制进交付包，目标机仍使用自身已安装的 64 位 Python 3.8 创建隔离环境。

## 甲方断网机

1. 校验 ZIP 的 SHA-256 与随附 `.sha256` 一致。
2. 解压到短英文路径，例如 `D:\IndustrialProtocol`。
3. 双击 `START_OFFLINE_WIN7.bat`。
4. 首次运行会自动创建隔离环境、只从包内 wheelhouse 安装依赖，并执行价格与
   效能真实试算；通过后启动三项服务并打开登录页与 Portal。
5. 后续双击同一文件直接启动。

如果 Python 3.8 不在 PATH，先在命令行指定：

```bat
set "PYTHON38_EXE=C:\Python38\python.exe"
START_OFFLINE_WIN7.bat
```

安装命令使用 `--no-index`，即使机器意外连网也不会从公网下载依赖。

## 边界

- 不预制或复制开发机 venv；Windows venv 含绝对路径，直接搬运不可靠。
- 在目标机用其 Python 3.8 创建隔离 venv，依赖全部来自交付包。
- 不重新导出价格模型；依赖版本必须服从现有 pickle 的训练环境。
- 如目标机缺少系统级 VC++ 运行库，应由甲方基础镜像统一安装已批准的离线
  VC++ Redistributable；Python wheels 本身不应通过网络补装系统组件。
