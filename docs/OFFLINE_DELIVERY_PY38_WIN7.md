# V21.1.1 Python 3.8 断网整包交付

## 交付目标

甲方 Windows x64 机器不能访问互联网。交付 ZIP 包含完整应用、当前数据库、
价格原生模型、效能运行包、官方 CPython 3.8.10 x64 便携运行时以及全部依赖
wheels。目标机不会访问 PyPI，也不会静默切换价格模型；机器自身的 Python
版本和 PATH 不参与正式服务启动。

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

封版验证和正式交付均使用官方 CPython 3.8.10 x64 便携运行时，仅从该
wheelhouse 加载依赖；价格原生 pickle 与效能模型的真实试算均通过。

## 甲方断网机

1. 校验 ZIP 的 SHA-256 与随附 `.sha256` 一致。
2. 解压到短英文路径，例如 `D:\IPDemo`。Windows 7 的旧路径长度限制会影响
   SciPy/scikit-learn DLL，启动器会在路径过长时直接给出迁移提示。
3. 双击 `START_OFFLINE_WIN7.bat` 或原有的 `START_ALL_SERVICES_WIN7.bat`。
4. 系统直接使用包内 Python 3.8 启动三项服务并打开登录页与 Portal。

目标机不需要安装 pip 包，也不需要配置 `PYTHON38_EXE`。wheelhouse 保留在包内，
用于完整性审计和必要时离线修复；所有安装命令均使用 `--no-index`。

## 边界

- 不复制开发机 venv；交付的是官方可搬移 CPython embed runtime。
- 不重新导出价格模型；依赖版本必须服从现有 pickle 的训练环境。
- 如目标机缺少系统级 VC++ 运行库，应由甲方基础镜像统一安装已批准的离线
  VC++ Redistributable；Python wheels 本身不应通过网络补装系统组件。
