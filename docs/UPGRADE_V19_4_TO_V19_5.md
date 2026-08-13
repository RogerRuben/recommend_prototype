# V19.4 升级到 V19.5

## 安全升级

升级补丁不会覆盖：

```text
data/
models/
data_master/
backups/
uploads/
runtime/
logs/
exports/
```

安装补丁后先运行：

```bat
RUN_FULL_PIPELINE_TEST.bat
```

V19.5程序仍能加载V19.4契约3.0模型。只有准备好契约4.0模型对后，才需要使用：

```text
tools/model_conversion_v19_5/validate_and_install_models.py
```

## 更换模型

同一成品替换模型时，可以直接校验安装。切换成品时必须同时提供对应DataMaster并显式启用`--allow-product-change`。安装器会备份原数据库、DataMaster和模型，失败后自动回滚。
