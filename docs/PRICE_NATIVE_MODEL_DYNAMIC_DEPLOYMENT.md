# V19.6 价格原生模型动态发现与部署指南

## 1. Hotfix解决的问题

原V19.6导出器在未显式指定模型时，固定假设以下七个模型都必须存在：

- Lasso
- Ridge
- XGBoost
- Random Forest
- Extra Trees
- SVR
- GBDT

这会造成两个问题：

1. 原Notebook实际只保存了部分模型时，导出仍要求七个模型全部存在；
2. Notebook内存中存在但没有被正式保存的模型，可能被误加入部署模型包。

本Hotfix改为：

> **实际检测到并保存了多少个模型，模型包就包含多少个；价格服务预测时也只调用模型包声明的这些模型。**

模型数量不再固定，可以是1个、3个、5个或7个。

---

## 2. 默认识别的模型文件

导出器默认在指定目录中检查以下文件：

| 模型名 | 默认识别文件名 |
|---|---|
| Lasso | `lasso.pkl`、`lasso_model.pkl` |
| Ridge | `ridge.pkl`、`ridge_model.pkl` |
| XGBoost | `xgb.pkl`、`xgboost.pkl`、`xgb_model.pkl` |
| Random Forest | `rf.pkl`、`random_forest.pkl`、`rf_model.pkl` |
| Extra Trees | `et.pkl`、`extra_trees.pkl`、`et_model.pkl` |
| SVR | `svr.pkl`、`svr_model.pkl` |
| GBDT | `gbdt.pkl`、`gbdt_model.pkl` |

原价格Notebook当前保存：

```python
with open('svr.pkl', 'wb') as file:
    pickle.dump(svr_model, file)
with open('gbdt.pkl', 'wb') as file:
    pickle.dump(gbdt_model, file)
with open('et.pkl', 'wb') as file:
    pickle.dump(et_model, file)
with open('rf.pkl', 'wb') as file:
    pickle.dump(rf_model, file)
with open('xgb.pkl', 'wb') as file:
    pickle.dump(xgb_model, file)
```

因此，在这些文件都存在且Lasso/Ridge没有保存时，导出的正式模型包只会包含：

```text
xgboost
random_forest
extra_trees
svr
gbdt
```

即使Notebook内存中仍有 `lasso_model` 和 `ridge_model`，也不会在 `saved_files` 模式下自动加入。

---

## 3. 安装Hotfix

### 3.1 自动安装

解压Hotfix后，在命令行运行：

```bat
APPLY_HOTFIX_WIN7.bat "D:\你的路径\IndustrialProtocolDemo_V19_6_ServiceGovernance"
```

安装程序会：

1. 检查目标目录；
2. 备份被替换文件；
3. 安装动态模型导出器、服务运行时、Notebook和文档；
4. 安装之前的效能服务启动修复；
5. 运行动态模型自测试；
6. 测试失败时自动恢复备份。

### 3.2 手工覆盖

把Hotfix中的 `payload` 内容按原目录结构复制到系统根目录并覆盖。

---

## 4. 正确导出流程

### 第一步：在原Notebook中完成训练

必须先完成：

- 数据读取和清洗；
- 训练/测试集划分；
- Scaler拟合；
- 需要部署的模型训练；
- 集成权重计算；
- 最终模型保存。

### 第二步：只保存准备部署的模型

不准备部署的模型不要写入 `.pkl`。

例如只部署SVR、GBDT和随机森林：

```python
import pickle

with open('svr.pkl', 'wb') as file:
    pickle.dump(svr_model, file, protocol=4)
with open('gbdt.pkl', 'wb') as file:
    pickle.dump(gbdt_model, file, protocol=4)
with open('rf.pkl', 'wb') as file:
    pickle.dump(rf_model, file, protocol=4)
```

Python 3.8建议使用pickle协议4。

### 第三步：运行Hotfix Notebook最后一个单元格

使用Hotfix中的：

```text
规范版价格预测_V19_6原生服务导出补丁.ipynb
```

关键配置：

```python
MODEL_DIRECTORY = Path.cwd()
MODEL_FILE_MAP = None
```

默认会扫描当前Notebook工作目录。

### 第四步：自定义模型文件名

文件名不是默认名称时，明确配置：

```python
MODEL_FILE_MAP = {
    "svr": "final_svr_2026.pkl",
    "random_forest": "production_rf.pkl",
    "custom_model": "my_custom_model.pkl",
}
```

自定义模型对象必须具有：

```python
model.predict(X)
```

### 第五步：检查导出输出

单元格会打印：

```text
实际保存模型数量
实际保存模型
权重来源
集成配置
所需依赖模块
```

同时生成：

```text
services\price_service\model\price_native_bundle.pkl
services\price_service\model\price_native_bundle.pkl.manifest.json
```

重点检查Manifest：

```json
{
  "model_count": 5,
  "model_names": [
    "xgboost",
    "random_forest",
    "extra_trees",
    "svr",
    "gbdt"
  ]
}
```

模型数量和名称必须与实际保存文件一致。

---

## 5. 权重处理规则

### 5.1 Notebook仍保留七模型权重

例如：

```python
weights = [
    lasso_weight,
    ridge_weight,
    xgb_weight,
    rf_weight,
    et_weight,
    svr_weight,
    gbdt_weight,
]
```

但只保存了XGBoost、RF、ET、SVR、GBDT时，导出器会：

1. 按名称提取第3至第7项对应权重；
2. 删除未保存Lasso和Ridge的权重；
3. 对剩余权重重新归一化；
4. 将最终权重写入Manifest。

不会把七个权重直接错配给五个模型。

### 5.2 权重数量等于已保存模型数量

权重按已保存模型的确定性顺序使用。

默认顺序是：

```text
lasso → ridge → xgboost → random_forest → extra_trees → svr → gbdt
```

只保留其中实际存在的模型。

### 5.3 推荐使用权重字典

最清楚的方式是显式传入：

```python
ensemble_weights = {
    "xgboost": 0.30,
    "random_forest": 0.20,
    "extra_trees": 0.15,
    "svr": 0.20,
    "gbdt": 0.15,
}
```

可以在 `export_from_notebook()` 调用中添加：

```python
ensemble_weights=ensemble_weights
```

字典中的每个已保存模型都必须有权重。

---

## 6. 服务预测逻辑

价格服务加载模型包后，读取：

```json
"ensemble": {
  "members": [
    {"name": "xgboost", "weight": 0.30},
    {"name": "svr", "weight": 0.25}
  ]
}
```

服务只遍历 `ensemble.members`：

```text
模型包有2个成员 → 只调用2个
模型包有5个成员 → 只调用5个
模型包有7个成员 → 调用7个
```

不会在运行时查找或补充其他模型。

正式模式下不要启用：

```text
--allow-degraded
PRICE_ALLOW_DEGRADED=1
```

否则某个模型预测失败时可能跳过该成员并重新归一化剩余权重。正式生产建议保持默认关闭：任何已声明模型失败就直接报错，避免预测逻辑静默变化。

---

## 7. 依赖处理

模型包只记录实际保存模型需要的依赖。

### 没有保存XGBoost

例如只保存SVR、GBDT、RF：

```text
required_modules通常包括：numpy、sklearn
```

不需要安装XGBoost。

### 保存了XGBoost

只要包含 `xgb.pkl`，加载pickle时就需要兼容的XGBoost版本。缺少依赖会导致原生模型加载失败；系统不会静默丢弃XGBoost后继续预测。

### joblib

本方案使用Python标准库：

```python
pickle
```

不要求安装joblib。但模型对象本身所属的NumPy、scikit-learn、XGBoost等库仍需存在。

---

## 8. 启动与验证

启动价格服务：

```bat
START_PRICE_SERVICE_WIN7.bat
```

浏览器打开：

```text
http://127.0.0.1:18101/health
```

原生模型正常加载后应看到：

```json
{
  "status": "ok",
  "backend": "native_pickle",
  "model_count": 5,
  "model_names": [
    "xgboost",
    "random_forest",
    "extra_trees",
    "svr",
    "gbdt"
  ]
}
```

如果看到：

```text
backend=portable_json
```

表示正式 `price_native_bundle.pkl` 没有加载，仍在使用兼容演示模型。

调用单方案接口后，响应中的：

```json
"debug": {
  "member_predictions": []
}
```

会列出实际执行的每个成员，可用于核对调用数量。

---

## 9. 更新模型时的标准操作

1. 停止价格服务；
2. 在原Notebook中重新训练；
3. 删除旧的单模型 `.pkl`，防止旧文件被再次扫描；
4. 只保存本次准备部署的模型；
5. 运行动态导出单元格；
6. 检查Manifest中的 `model_count` 和 `model_names`；
7. 启动价格服务；
8. 检查 `/health` 中模型数量和名称；
9. 使用固定验收样本对比Notebook结果与服务结果；
10. 验收通过后再启动推荐系统。

第三步非常重要。目录中残留的旧 `xgb.pkl` 或其他默认文件仍会被识别为准备部署的模型。

---

## 10. 模型一致性验收

服务预测应使用：

```text
相同Scaler
+ 相同已保存Estimator
+ 相同字段顺序
+ 相同已选择权重
+ 相同exp逆变换
+ 相同单位换算
```

建议准备20至50条固定样本，对比：

```text
Notebook中“已保存模型子集”的集成结果
vs.
价格服务结果
```

不要再拿原七模型集成结果与五模型服务结果比较。模型成员发生变化后，正确比较对象也必须是相同的模型子集和相同权重。

---

## 11. 常见问题

### 没有发现模型

报错：

```text
没有在...发现受支持的已保存pkl模型
```

检查：

- `MODEL_DIRECTORY`是否正确；
- 文件是否已真正保存；
- 文件名是否属于默认名称；
- 自定义文件名是否写入 `MODEL_FILE_MAP`。

### 权重数量不一致

报错会明确显示权重数与模型数。建议改用权重字典，不要猜测顺序。

### 不希望部署XGBoost

删除或移动：

```text
xgb.pkl
xgboost.pkl
xgb_model.pkl
```

再重新导出。仅仅本机没有安装XGBoost，并不会让导出器自动安全忽略已经保存的XGBoost模型。

### 服务显示模型数不正确

依次检查：

1. `price_native_bundle.pkl.manifest.json`；
2. `/health` 返回的 `model_count` 和 `model_names`；
3. 是否重启了旧的价格服务进程；
4. `services\price_service\model` 中是否替换了正确文件。

---

## 12. 安全说明

pickle文件可以执行对象反序列化逻辑。只允许加载：

- 自己训练并保存的模型；
- 经内部审核的模型；
- SHA-256已核对的发布模型。

不要让普通用户上传任意 `.pkl` 并直接加载。
