# V19.5 价格／效能模型转换与安全安装工具

本工具把价格与效能工程转换为工业技术协议智能推荐系统可直接加载的**契约4.0纯JSON模型**。转换后的运行时只依赖Python标准库，不需要在现场安装scikit-learn、SciPy或XGBoost。

## 一、重要结论

### 效能模型

原效能工程没有`.pkl`。其有效模型由以下内容共同构成：

```text
项目Workbook
＋ 可选state_<learning_fingerprint>.json
＋ CouplingSystem / ExpertFeasibilityModel / OnlineBTModel / LPUTAModel重建代码
```

`effectiveness_snapshot_export.py`会导入原工程代码、重建模型、导出耦合带、可行性、BT／UTA、协议要求和历史样本，并对全部历史方案执行原程序与导出模型的一致性检查。

### 价格模型

原Notebook末尾保存的若干`.pkl`缺少完整的字段顺序、Scaler、对数变换、集成规则和残差区间，不能单独作为推荐系统模型。`price_model_export_patch.py`从原始价格训练表重新训练可部署的纯JSON岭模型集成，并显式排除价格类别、Cluster、异常标签等泄漏字段。

这意味着：转换器保证**部署契约和运行链路正确**，但价格模型精度仍取决于真实训练数据和字段选择。当前交付未包含Notebook引用的真实价格训练表，因此随包示例价格模型仅用于验证转换链路。

## 二、输出结构

推荐项目使用：

```text
models/
├─ effectiveness_bundle.json
├─ price_bundle.json
└─ model_manifest_v19_5.json

app/
├─ model_runtime.py
└─ model_contract_v4.py
```

安装器不会再复制旁路运行时，也不会覆盖项目中的`app/model_runtime.py`。目标项目必须先升级到完整V19.5。

## 三、效能模型转换

```bat
python effectiveness_snapshot_export.py ^
  --source-root D:\effectiveness\compare\demo ^
  --workbook D:\effectiveness\compare\demo\data\project.xlsx ^
  --state D:\effectiveness\interactive_project\state_xxx.json ^
  --product-code PRODUCT_CODE ^
  --model-version effectiveness-v1 ^
  --field-map effectiveness_field_map.json ^
  --output effectiveness_bundle.json
```

没有真实State时可省略`--state`，但输出只包含Workbook基线模型，不包含专家在线学习结果。正式模型应使用与Workbook学习指纹匹配的State。

转换器内置一致性门槛：对历史方案逐条比较原程序和导出模型的效能分、可行概率，超过容差会拒绝导出。

## 四、价格模型转换

```bat
python price_model_export_patch.py ^
  --data price_training.xlsx ^
  --target 价格 ^
  --features 额定载荷,重量,防护等级,采购批量 ^
  --field-map price_field_map.json ^
  --product-code PRODUCT_CODE ^
  --product-name 成品名称 ^
  --model-version price-v1 ^
  --target-divisor 10000 ^
  --output price_bundle.json
```

`--target-divisor`用于统一推荐系统的“万元”单位：

- 原始价格已经是万元：填写`1`；
- 原始价格是元：填写`10000`。

正式转换必须显式填写`--features`和`--field-map`，不能依赖自动选列。

## 五、共享字段与价格专用字段

同一个`parameter_id`可以同时出现在价格和效能模型中。共享字段必须满足：

- 字段编号一致；
- 数据类型一致；
- 单位一致；
- 字段来源一致。

价格专用必填字段必须有可部署的缺失策略，例如`training_mean`、`default`、`constant`或`zero`。否则旧协议无法评价，安装器会拒绝安装。

## 六、校验与安装

只校验：

```bat
python validate_and_install_models.py ^
  --effectiveness effectiveness_bundle.json ^
  --price price_bundle.json ^
  --project-root D:\IndustrialProtocolDemo_V19_5 ^
  --validate-only
```

同一成品安装：

```bat
python validate_and_install_models.py ^
  --effectiveness effectiveness_bundle.json ^
  --price price_bundle.json ^
  --project-root D:\IndustrialProtocolDemo_V19_5
```

切换成品时必须同时提供对应DataMaster：

```bat
python validate_and_install_models.py ^
  --effectiveness effectiveness_bundle.json ^
  --price price_bundle.json ^
  --project-root D:\IndustrialProtocolDemo_V19_5 ^
  --data-master D:\models\DataMaster_Current.xlsx ^
  --allow-product-change
```

安装流程为：

1. 校验两个模型契约；
2. 校验共享字段和价格专用字段补全策略；
3. 通过目标项目的`app/model_runtime.py`加载临时模型；
4. 完成联合推理；
5. 产品切换时校验新DataMaster；
6. 备份模型、数据库和DataMaster；
7. 原子替换；
8. 启动完整Application并进行联合评价；
9. 同步导出当前DataMaster；
10. 任一步失败自动回滚。

## 七、自检

```bat
RUN_MODEL_KIT_SELF_TEST.bat
```

自检使用本工具内置的V19.5集成运行时参考副本，验证共享字段、价格专用字段补全和联合推理。`reference_runtime/`仅用于验证，不会被安装到项目中。

## 八、依赖

- 推荐系统推理：Python 3.8标准库；
- 价格转换：NumPy、Pandas；读取XLSX还需要openpyxl；
- 效能转换：原效能工程自身依赖；
- 转换完成后的模型包不依赖pickle。

## 九、生成匹配的初始化DataMaster

切换成品但尚未建立DataMaster时，可以先从模型对生成初始化工作簿：

```bat
python build_datamaster_from_model_pair.py ^
  --effectiveness effectiveness_bundle.json ^
  --price price_bundle.json ^
  --output DataMaster_Current.xlsx
```

生成器会把价格与效能字段并集合并为一份指标定义，共享字段只出现一次，并将价格专用字段缺失值写入历史样本。生成结果不包含正式标签和显式工程约束，投产前必须由专家补充。
