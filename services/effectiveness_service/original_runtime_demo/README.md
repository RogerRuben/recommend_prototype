# Excel 驱动的方案对比与效能评估原型

主程序面向“物理约束只知道一部分、历史样本没有效能标签、效能函数难以直接书写”的机械产品。系统主动生成 A/B 方案，专家判断可行性和优劣，后台同时学习可行边界、偏好趋势和 UTA 效能函数。

## 直接启动

```powershell
python .\compare\demo\interactive_project_app.py
```

程序先弹出文件选择窗口。选定项目 Excel 后访问：

```text
http://127.0.0.1:8776
```

固定工作簿或自动测试：

```powershell
python .\compare\demo\interactive_project_app.py --workbook .\path\to\project.xlsx
python .\compare\demo\interactive_project_app.py --demo
```

开发机也可双击 `start_stage8_app.bat`；Win7 离线现场使用 `compare/deploy_win7/04_start_app.bat`。

## Excel 项目

演示工作簿：

```text
compare/demo/data/aircraft_door_lock_demo.xlsx
```

支持四张工作表：

- `方案数据`：必需，第一行动态定义属性和 A/B 行顺序；
- `属性配置`：单位、类型、生成范围、偏好、边际规律、三批设计顺序；
- `耦合关系`：源属性到目标属性的有向物理知识；
- `新技术协议`：可选，每行一份协议，只填写协议编号、名称和各属性要求值。

```powershell
python .\compare\demo\create_demo_workbook.py
python .\compare\demo\project_excel.py .\compare\demo\data\aircraft_door_lock_demo.xlsx
```

属性方向只从`属性配置`读取。`新技术协议`不重复填写方向，也不参与可行性、BT 或 UTA 学习；它只在未知方案评分时定义“协议方案本身=100分”的参考向量。

## 版本 10 核心能力

### 小样本可行性学习

- 历史方案只作为弱可行正例，不当作高效能样本；
- 重复“某属性偏低/偏高”反馈聚合成带证据数和置信度的专家边界；
- 耦合样本足够时拟合单调条件经验带，样本不足时使用方向先验；
- 成熟边界进入未知方案解释，并抑制普通生成继续反复触碰已确认区域；
- 自由文本留档，尚不未经确认自动转换为物理约束。

### 控制变量主动生成

数值属性自动映射到线性、对数或离散的无量纲坐标，`2.2 -> 2.0` 与 `11000 -> 10500`按设计空间相对位移比较。

全域、Maximin、局部和耦合探测都生成匹配方案对：每轮只改变 1 至 3 个上游属性，再按 Excel 的设计批次和耦合方向补全下游参数。全域搜索负责寻找新区域，但不会把所有参数独立随机后直接交给专家。

生成器记录基准方案、生成来源、探索目的、直接改变的属性、因果补全的属性和问题签名。近期有效偏好产出率和重复签名会改变调度，避免一直询问同一类低价值问题。

### BT 与 UTA 双线

- 在线特征化 Bradley-Terry 每次用全部有效偏好重训，用于胜率趋势和主动选点；
- LP-UTA 使用统一 2 至 6 段边际函数，输出 0 至 100 分和逐属性贡献；
- M1/M2/M3 分别做严格一致性、最小容忍和最少冲突定位；
- 设计第一/二/三批以 50%/30%/20% 作为小样本软先验；
- BT/UTA始终学习协议无关的通用产品效能；全部有效专家偏好统一累计；
- 设计为指定值的属性可在`属性配置`中填`区间型`，最终协议评分以该协议值为100分点，数值偏离不会获得超额奖励。

### 完成、复核和解释

- 完成面板同时检查通用有效比较数、保守验证正确率、一致性和待复核项；
- 80% 为标准完成线，90% 为高置信线；
- 每个复核项重现原 A/B 和原证据，独立处理且支持撤销；
- A/B 参数行严格对齐，并提供按各属性生成范围归一化的横向对比图；
- 未知方案报告逐项解释物理风险、相对协议100分参考的属性得分、权重贡献、耦合来源和复用建议；方向性属性可以高于100分。

## 状态与迁移

```text
compare/demo/interactive_project/state_<fingerprint>.json
```

状态按属性配置、历史方案和耦合知识形成的学习数据指纹隔离，新技术协议不参与该指纹。配置版本7/8/9可迁移到版本10，保留专家交互、可行性证据、偏好证据、复核和未知评估，并把历史偏好统一迁移为通用效能证据。生成范围写回Excel前会自动备份并迁移状态。

正式发布包不得包含开发机真人状态、日志或缓存，也不得覆盖甲方电脑已有状态。

## 测试

```powershell
python -m unittest discover -s .\compare\demo -p "test_*.py" -v
python .\compare\demo\run_stage8_acceptance.py
```

当前基线为61项单元/回归测试和19项端到端验收。`test_onsite_regression.py`只用合成数据复现现场问题，不包含甲方参数。

## 文档

```text
用户操作说明.md
Excel数据填写指南.md
研究人员与管理员说明.md
软件技术总报告与维护手册.md
最终交付文件清单.md
```

## 旧版文件

以下文件仅保留作算法演进和回滚参考，不再升级：

- `interactive_door_lock_app.py`：早期固定舱门锁页面；
- `interactive_app.py`：早期机械锁交互页；
- `door_lock_static_demo.html`：静态单文件演示；
- `run_demo.py`：隐藏专家模拟闭环。

正式测试、交付和维护均以 `interactive_project_app.py` 为准。
