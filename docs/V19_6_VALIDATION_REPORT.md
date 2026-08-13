# IndustrialProtocolDemo V19.6 验证报告

验证日期：2026-07-30

## 1. 本轮交付目标

V19.6完成：

1. 修复标签、规则等管理对象修改后无法保存的问题；
2. 建立启用、停用、归档、依赖检查和受控永久删除的数据生命周期；
3. 将DataMaster改为面向非专业人员的引导式工作簿；
4. 将价格与效能预测拆分为独立HTTP服务，并提供Schema、批量接口、OpenAPI和简易前端；
5. 价格正式模式保存原Scaler、原拟合模型、字段顺序、集成权重和变换，不再重新训练替代模型；
6. 效能正式模式直接运行原源码、Workbook和可选State；
7. 增加Windows 7 / Python 3.8启动、离线依赖和服务健康检查。

## 2. 数据管理验证

专项测试确认：

- 编辑保存按钮通过`form=adminEditForm`真实绑定表单；
- 停用标签下的规则仍可修改和保存；
- 标签、规则、耦合、约束和协议支持直接启停；
- 普通删除执行归档，不物理删除；
- 永久删除要求记录已停用、没有引用，并先创建数据库备份；
- 当前成品不能直接停用；
- 模型绑定且必填的指标不能停用；
- SQLite完整性和审计链路通过。

## 3. DataMaster验证

工作簿从8张扩展为10张，新增：

- `填写说明`；
- `字典_下拉项`。

验证结果：

- 当前工作簿回导：PASS；
- 引导式模板回导：PASS；
- 10张工作表存在：PASS；
- Excel数据验证下拉存在于8张业务表：PASS；
- 动态标签编号、指标编号和规则字段引用范围：PASS；
- 布尔字段“类型=布尔、实际值=有/无”的说明和下拉：PASS；
- 公式错误扫描：0；
- 模板保留当前模型需要的17项指标和34条字段绑定。

## 4. 独立模型服务验证

价格服务和效能服务均提供：

```text
GET  /health
GET  /api/v1/schema
POST 单方案预测/评价
POST 批量预测/评价
GET  /openapi.json
GET  /docs
```

使用当前演示模型启动两个独立HTTP服务后：

- 价格服务结果与推荐系统当前本地价格模型差值小于`1e-6`；
- 效能服务结果与推荐系统当前本地效能模型差值小于`1e-6`；
- 两个服务简易前端内置示例请求可直接执行：PASS；
- 批量双服务评价：PASS；
- 完整`Application`切换`IPDEMO_MODEL_EXECUTION_MODE=services`：PASS；
- 服务端产品代号不一致检查：已启用；
- 服务不可用本地回退：保留，可通过环境变量禁止。

## 5. 效能原运行时验证

效能服务直接加载用户提供工程中的：

```text
interactive_project_app.py
coupling_model.py
feasibility_model.py
preference_models.py
requirement_model.py
project_excel.py
项目Workbook
可选State JSON
```

对原工程同一方案比较：

- 服务最终效能分与`ProjectApp.evaluate`：绝对差小于`1e-10`；
- 服务可行概率与`ProjectApp.evaluate`：绝对差小于`1e-10`。

新增效能运行包工具会复制原源码、Workbook和State，记录SHA-256、Workbook指纹和学习指纹，并在发布前实际重建原`ProjectApp`。当前用户提供工程未包含正式专家State，因此随包原效能示例属于Workbook基线模型。

## 6. 价格原生pickle验证

新增原生价格模型包使用Python标准库pickle协议4，不要求joblib。模型包保存：

- 原Scaler；
- 原拟合Estimator对象；
- 字段顺序和稳定字段编号；
- 原集成成员和权重；
- log价格逆变换；
- 元/万元换算；
- 残差区间；
- 训练环境和依赖模块；
- 模型Manifest。

使用实际拟合的Ridge、SVR和GBDT组成测试Pipeline，比较原对象直接预测与模型服务模型包预测：

```text
最大绝对差 < 1e-6
结果：PASS
```

测试同时确认服务代码没有`import joblib`。

重要边界：当前会话仍未提供原价格Notebook读取的正式训练Excel和已经执行完毕的Notebook内存对象，因此不能在此生成正式业务`price_native_bundle.pkl`。随包Notebook在原训练流程运行完后可一键导出完全相同的拟合对象。正式模型是否需要XGBoost取决于导出的集成成员；包含XGBoost时必须为价格服务环境安装兼容版本，系统不会静默跳过并冒充精确结果。

## 7. Windows 7 / Python 3.8

- 应用、服务和工具使用Python 3.8语法解析：PASS；
- HTTP框架仅使用Python标准库；
- 价格便携后备模式不需要NumPy、SciPy、scikit-learn、XGBoost或joblib；
- 价格精确模式需要pickle对象实际引用的模型库；
- 效能原运行时需要NumPy、SciPy和openpyxl；
- 随包提供效能Python3.8/Win64离线wheelhouse；
- 价格模型依赖版本记录在模型Manifest中，建议使用隔离环境或远端价格服务。

## 8. 回归结果

```text
V19.6.5完整推荐Pipeline：45项 PASS
虚拟正式成品全链路（Python 3.8隔离环境）：32项 PASS
待发布成品工作区：14项 PASS
统一成品交付包：17项 PASS
价格动态模型Hotfix：PASS
V19.6服务与数据治理专项：Python 3.8隔离训练环境24项 PASS，包含真实Ridge/SVR/GBDT导出对照和原效能运行时
价格训练环境专项：7项 PASS，包含Ridge/SVR/GBDT/XGBoost训练、Excel、绘图、原生导出和预测等价性
两个Python 3.8隔离环境pip check：PASS
航空舱门锁数据人员演练包：20项 PASS
航空舱门锁三个工作簿逐表渲染与公式错误扫描：PASS（0个公式错误）
离线交付包：4个独立ZIP均不超过80MiB，SHA-256、合并解压及从零创建Python 3.8运行环境PASS
V19.5共享字段兼容专项：14项 PASS
Python编译：PASS
Python 3.8语法解析：PASS
JavaScript语法：PASS
DataMaster当前文件与模板回导：PASS
最终ZIP重新解压验证：见交付包测试报告
```

统一交付包专项覆盖：演示/正式后端边界、外部SHA-256、三方字段契约、
成品代码不一致、模型文件篡改、ZIP目录穿越、安装目标重定向、安装前
备份、业务草稿导入、人工回滚、回滚前快照以及安装故障自动恢复。

本次已在Python 3.8隔离环境中使用NumPy 1.24.4与SciPy 1.10.1成功执行原效能
工程，原ABI问题不再存在。新增价格离线wheelhouse后，服务治理专项已完成真实
scikit-learn Ridge/SVR/GBDT对象的Notebook导出等价性尾项，共24项PASS。
独立训练环境还实际完成了XGBoost训练、Excel读写、绘图、原生bundle导出和
服务预测等价性，共7项PASS。虚拟正式成品的双成员原生pickle价格包也已在
32项全链路验收中执行。

新增航空客舱门锁虚拟演练包使用640条价格样本训练Ridge、SVR、GBDT和
XGBoost四成员原生集成，并用原ProjectApp构建含模拟专家证据的效能State。
专项20项验收覆盖统一契约、DataMaster整体解析与临时库提交、双模型加载和
推理、枚举/布尔/IP多类型字段、训练留出集指标及bundle预测等价性。交付包未
安装到当前服务，当前`VIRTUAL_COUPLED_ACTUATOR`基线保持不变。

## 9. 正式投产要求

正式上线前仍需要：

1. 在原价格Notebook真实训练数据上运行最后导出单元格；
2. 对原Notebook预测和价格服务预测做逐样本一致性验收；
3. 将正式效能State与对应Workbook一起打包；
4. 使用统一交付工具构建正式包，并通过独立渠道核对ZIP的SHA-256；
5. 确认两个服务和成品数据使用同一`product_code`、字段编号、类型和单位；
6. 在目标Windows 7镜像中完成依赖、验包、安装、草稿激活、冒烟和回滚测试。
