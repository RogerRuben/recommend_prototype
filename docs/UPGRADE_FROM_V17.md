# 从V17升级到V18

1. 关闭V17程序。
2. 备份原目录中的：
   - `data/protocol_demo.db`；
   - `models/effectiveness_bundle.json`；
   - `models/price_bundle.json`。
3. 将V18升级补丁复制到V17根目录并覆盖代码文件。
4. 不要删除原有`data/protocol_demo.db`。
5. 运行`VALIDATE_MODELS.bat`。
6. 运行`RUN_FULL_PIPELINE_TEST.bat`。
7. 运行`START_ALL_WIN7.bat`。

首次启动会：

- 增加`model_input_bindings`表；
- 保留原历史协议、专家方案、标签、耦合和约束；
- 只在识别到旧虚拟锁类Demo时迁移为伺服电动缸示例；
- 同步两个模型的字段绑定；
- 不覆盖用户自定义成品。
