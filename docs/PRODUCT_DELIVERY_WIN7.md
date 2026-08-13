# 成品统一离线交付包

本工具把价格模型、效能模型和管理页导出的成品数据发布包绑定为一个 ZIP。它解决的是“把已经制作好的三类交付物安全送到断网电脑”这一段，不替代价格模型训练或效能模型学习。

统一包的格式版本为 `industrial-product-delivery-1.0`。包内保存每个文件的大小和 SHA-256，并保存价格、效能、业务字段的统一契约报告。

## 一、正式交付物要求

正式交付必须同时满足：

- 价格模型后端为 `native_pickle`，输入通常是 `services\price_service\model\price_native_bundle.pkl`；
- 效能模型推荐使用 `frozen_effectiveness_runtime`，输入是最终 V11 专家软件导出的冻结模型 ZIP 经安装后形成的完整运行目录；旧 `original_effectiveness_runtime`（源码、Workbook 和可选 State）继续作为正式兼容后端；
- 成品数据是管理页“成品发布工作区”导出的 `industrial-product-release-1.0` JSON；
- 三者的 `product_code` 相同；
- 两个模型的共享字段 ID、类型和单位兼容；
- 成品指标覆盖两个模型需要的全部产品参数。

价格原生 bundle 是 pickle。构建阶段会用正式价格服务加载它，所以只能在可信的模型制作环境中对可信文件执行构建命令。目标电脑安装时只做静态摘要和契约校验，不会在安装器中执行 pickle 或效能源码。

## 二、在模型制作电脑构建

先从管理页导出已经维护好的成品数据发布包，然后执行：

```bat
BUILD_PRODUCT_DELIVERY_WIN7.bat ^
  --price-model services\price_service\model\price_native_bundle.pkl ^
  --effectiveness-package services\effectiveness_service\model\current ^
  --business-release exports\PRODUCT_A.iprelease.json ^
  --output exports\PRODUCT_A_delivery.zip ^
  --delivery-version PRODUCT_A-2026.07
```

成功后会生成：

- `PRODUCT_A_delivery.zip`
- `PRODUCT_A_delivery.zip.sha256`

如果现场只有原始历史成品表和两个模型，不必先进入管理页制作发布 JSON，可直接执行：

```bat
BUILD_DELIVERY_FROM_HISTORY_WIN7.bat ^
  incoming\历史成品.xlsx ^
  incoming\price_native_bundle.pkl ^
  incoming\effectiveness_runtime\effectiveness_runtime_manifest.json ^
  exports\PRODUCT_A_delivery.zip ^
  PRODUCT_A ^
  产品A
```

系统会先按数据中心相同规则自动推断业务字段，再执行三方模型契约校验。详细步骤见 `docs\甲方部署与成品更换流程_无Wheels.md`。

JSON 演示模型不是正式模型。只有测试时才允许：

```bat
BUILD_PRODUCT_DELIVERY_WIN7.bat ^
  --price-model models\price_bundle.json ^
  --effectiveness-package models\effectiveness_bundle.json ^
  --business-release exports\DEMO.iprelease.json ^
  --output exports\DEMO_delivery.zip ^
  --allow-demo-models
```

## 三、复制到 Win7 断网电脑并验包

建议通过两个独立渠道记录 ZIP 的 SHA-256。验收人员拿到确认过的摘要后执行：

```bat
VERIFY_PRODUCT_DELIVERY_WIN7.bat exports\PRODUCT_A_delivery.zip --expected-sha256 已确认的64位摘要
```

仅把 ZIP 和同目录 `.sha256` 一起复制，可以发现传输损坏，但不能替代独立渠道确认摘要。

## 四、安装

先关闭推荐主系统、价格服务和效能服务。安装器发现 `17891`、`18101` 或 `18102` 仍在监听时会拒绝继续。

```bat
INSTALL_PRODUCT_DELIVERY_WIN7.bat exports\PRODUCT_A_delivery.zip --expected-sha256 已确认的64位摘要
```

安装器会：

1. 重新校验 ZIP、文件摘要和跨模型契约；
2. 在 `backups\deliveries\<备份ID>` 备份旧模型和 SQLite；
3. 把正式价格模型安装到 `services\price_service\model\price_native_bundle.pkl`；
4. 把正式效能运行包安装到 `services\effectiveness_service\model\current`；
5. 把成品数据导入 `product_releases` 为草稿；
6. 返回备份 ID 和草稿发布 ID。

安装不会自动激活成品数据。这样可以先启动两个模型服务，检查 `/health` 和 `/api/v1/schema`，再启动推荐主系统，到管理页执行草稿校验并由用户明确点击激活。

演示包安装仍需显式授权：

```bat
INSTALL_PRODUCT_DELIVERY_WIN7.bat exports\DEMO_delivery.zip --allow-demo-models
```

## 五、回滚

先停止三个服务，再使用安装时返回的备份 ID：

```bat
ROLLBACK_PRODUCT_DELIVERY_WIN7.bat 20260730_153000_DLV-20260730_152900-XXXXXXXX
```

回滚会恢复安装前的模型和 SQLite。在覆盖当前状态前，还会保存一份 `rb_时间` 快照，避免人工回滚本身成为不可恢复操作。安装备份编号采用“时间 + 交付编号摘要”的短格式，以兼容 Windows 7 的传统路径长度限制；完整交付编号仍保存在安装记录中。

## 六、推荐验收顺序

1. 验包；
2. 停止三个服务；
3. 安装；
4. 启动价格服务，确认正式后端为 `native_pickle`；
5. 启动效能服务，确认正式后端为 `frozen_effectiveness_runtime`；旧成品兼容部署可为 `original_effectiveness_runtime`；
6. 启动推荐主系统；
7. 在成品发布工作区校验导入的草稿；
8. 用户确认后激活；
9. 做一组价格预测、效能评估和推荐生成冒烟测试。

如果第 4～8 步失败，停止服务并按备份 ID 回滚。
