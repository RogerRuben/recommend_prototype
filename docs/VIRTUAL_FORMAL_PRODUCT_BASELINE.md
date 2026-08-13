# 虚拟正式成品全链路验收基线

## 1. 用途与边界

`VIRTUAL_COUPLED_ACTUATOR` 是确定性生成的虚拟验收成品，用于验证“成品业务数据 + 原生价格模型 + 原效能 Workbook/State + 推荐主系统”的完整离线交付流程。

它使用正式后端格式和真实运行路径，但数据、价格规律、专家偏好和效能结论均为模拟内容，不代表任何真实产品、报价或工程结论，不得作为投标或生产依据。

## 2. 覆盖的数据结构

总计 15 个业务属性：

- 6 个共有属性：额定推力、有效行程、运行速度、防护等级、过载保护、整机质量；
- 4 个价格专用属性：主体材料等级、进口件比例、质保年限、采购批量；
- 5 个效能专用属性：定位精度、响应时间、工作循环、冗余等级、控制方式。

覆盖连续数值、整数、布尔、IP 等级和无序枚举。业务数据另含 10 个标签、11 条标签规则、6 条耦合关系、2 条约束规则和 40 条历史协议。

价格训练集固定为 520 条；效能 Workbook 固定为 40 条方案。生成器使用固定随机种子 `20260730`，因此同一源码和依赖下可重复构建。

## 3. 生成物

目录 `outputs/virtual_formal_baseline` 包含：

```text
virtual_effectiveness_project.xlsx        原效能工程输入Workbook
virtual_price_training.csv                虚拟价格训练数据
price/price_native_bundle.pkl             双成员原生pickle价格模型
simulated_expert_state/state_*.json       模拟专家学习State
effectiveness_runtime/                    原效能源码+Workbook+State运行包
business/product_release.iprelease.json   七模块成品业务发布包
virtual_product_delivery.zip              三部分统一正式交付包
virtual_product_delivery.zip.sha256        外部完整性摘要
fixture_manifest.json                     数据量、角色和专家模拟统计
```

当前统一包 SHA-256：

```text
6c677a1e933f0b5fb73b57ee57c8a355a9ff83cb9f9e963d64256d22afda6d5c
```

重新生成 Workbook 或专家 State 后摘要会变化，应以同目录 `.sha256` 文件为准。

## 4. 模拟专家过程

生成器调用原 `ProjectApp` 完成效能项目构建，并保存学习 State：

- 16 次偏好交互；
- 8 条可行性证据；
- 17 条偏好证据，其中 16 条有效；
- UTA 训练 12 条、测试 4 条；
- 1 条复核项已解决，0 条未处理。

State 中带有 `fixed_virtual_expert_simulation` 标记和模拟数据声明。

## 5. Python 3.8 隔离环境

在目标 Python 3.8 上创建隔离环境：

```bat
python -m venv runtime\venvs\virtual_product38
runtime\venvs\virtual_product38\Scripts\python.exe -m pip install --no-index --find-links services\effectiveness_service\wheelhouse_win7 numpy==1.24.4 scipy==1.10.1 openpyxl==3.1.3 et-xmlfile==1.1.0
```

该环境完全使用随包 Win7/Win64 wheelhouse，不访问网络。本次验收使用：

```text
Python 3.8.19
NumPy 1.24.4
SciPy 1.10.1
openpyxl 3.1.3
```

## 6. 运行完整验收

```bat
RUN_VIRTUAL_FORMAL_PRODUCT_E2E_WIN7.bat
```

或：

```bat
runtime\venvs\virtual_product38\Scripts\python.exe tests\virtual_formal_product_e2e_test.py
```

测试不会改动当前项目的正式模型或数据库。它会在项目内短路径临时目录中完成：

1. 静态验包和跨模块契约检查；
2. 安装价格模型、效能运行包并导入业务草稿；
3. 启动两个独立 HTTP 模型服务；
4. 校验并显式激活成品；
5. 验证价格专用、效能专用和共有属性的模型隔离；
6. 运行标签、耦合、历史推荐和智能生成；
7. 验证属性修改后必须显式重新计算才能保存；
8. 重启主系统实例并调用 HTTP 推荐；
9. 回滚并核对模型文件和 SQLite 逻辑内容。

报告写入：

```text
logs/virtual_formal_product_e2e_report.json
```

当前结果为 32 项全部通过。

## 7. 源码入口

- `tools/virtual_product_fixture.py`：确定性数据、原生价格包、专家 State、效能运行包和统一包；
- `tools/virtual_product_workbook.mjs`：生成并检查六表效能 Workbook；
- `tests/virtual_formal_product_e2e_test.py`：隔离安装到回滚的端到端验收；
- `tools/product_delivery.py`：正式包构建、验包、安装与回滚。

Workbook 使用 artifact-tool 生成和渲染检查；该步骤属于开发机构建流程。甲方断网机只需接收已构建的统一包并执行验包、安装、草稿激活及验收，无需安装 Node.js 或重新生成 Workbook。
