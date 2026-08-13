# V11 最终冻结版效能模型生成、导出与部署

本项目以 `效能评估专家版_V11_WIN7_x64_20260812_v2` 为最终效能学习软件。职责边界如下：

```text
效能专家软件（在线学习、保存完整证据）
  └─ 点击“冻结并导出模型”
       └─ effectiveness_model_*.zip（脱敏、只读推理包）
            └─ 推荐系统效能服务 18102
                 ├─ 推荐系统调用
                 └─ 操作员效能评价工作台 /effectiveness
```

专家电脑上的原 Excel、方案行、逐条 A/B 记录、专家文字和复核历史继续留在
`userdata`，不得用推荐系统目录替代其完整归档。

## 推荐流程：冻结模型 ZIP

1. 在最终冻结版专家软件中选择实际项目 Excel。
2. 完成在线学习、可行性判断和必要复核。
3. 检查软件给出的学习完成度和验收摘要。
4. 点击“冻结并导出模型”。软件输出 `effectiveness_model_*.zip`。
5. 将 ZIP 拷贝到推荐系统电脑，运行：

```bat
INSTALL_FROZEN_EFFECTIVENESS_MODEL_WIN7.bat
```

也可使用命令行：

```bat
runtime\venvs\model_runtime38\Scripts\python.exe ^
  -m services.effectiveness_service.install_frozen_effectiveness_model ^
  --model-package "D:\模型\effectiveness_model_xxx.zip" ^
  --expected-product-code "成品代号"
```

安装器会先执行 ZIP 路径安全检查、清单格式检查、所有运行文件 SHA-256
校验、冻结模型内容摘要与隐私声明检查，并真正加载模型完成一次效能冒烟评价。
全部通过后才原子替换 `services/effectiveness_service/model/current`；旧目录自动
改名为带时间的 `current.backup_*`，失败时原模型不变。

冻结包必须声明格式：

```text
effectiveness-frozen-runtime-package-1.0
```

正式包包含属性结构、需求协议、UTA/BT 参数、稳健模型、可行性参数、成熟专家
边界和耦合代理参数，不包含原 Excel 与逐条学习证据。

## 兼容流程：Workbook + State

旧方式继续完整保留，用于旧成品、迁移和问题复现：

```bat
PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat
```

它仍接受：

1. 原效能源码目录；
2. 项目 Workbook；
3. 可选 State JSON；
4. 可选期望 `product_code`；
5. 可选输出目录。

生成格式仍是 `effectiveness-original-runtime-package-1.0`。效能服务启动时会
自动识别冻结格式或旧格式；现有旧清单和现有启动参数无需修改。

## 启动与操作页面

安装后按顺序运行：

```bat
START_EFFECTIVENESS_SERVICE_WIN7.bat
START_RECOMMENDATION_SYSTEM_WIN7.bat
```

推荐系统页面：`http://127.0.0.1:17891/`

独立效能评价工作台：`http://127.0.0.1:17891/effectiveness`

工作台按当前效能服务 Schema 自动生成字段。修改参数不会自动计算，只有点击
“开始评价效能”才调用效能服务；它不调用价格服务、不写历史成品库，也不要求
当前价格模型和效能模型的成品代号一致。即使价格服务停止，效能工作台仍可用。

## 更新、回滚与注意事项

- 专家继续学习后，应重新点击“冻结并导出模型”，不要手改冻结 JSON。
- 新 ZIP 是完整模型版本，不能只复制其中某个 JSON 或某个源码文件。
- 正式启用前核对 `product_code`、模型版本、学习完成度和甲方外带授权。
- 需要回滚时，停止效能服务，将当前目录移走，再把最近的
  `current.backup_时间` 改回 `current`。
- 冻结模型由于不含原方案行，会关闭“最近原始方案距离”和“逐条记录耦合前沿
  锚点”；这是最终专家软件在隐私最小化清单中明确声明的限制。
