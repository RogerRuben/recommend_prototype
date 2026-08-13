# R7 本地测试运行说明

## 版本定位

本包的正式推荐主线仍为 V19.6.8：历史范围内和浅层越界使用快速搜索，深度越界使用耦合感知多阶段束搜索。

GFlowNet 仅作为隔离实验代码随包提供：

- 正常点击“智能推荐”不会调用 GFlowNet；
- 不会改变主线推荐结果或运行时间；
- 不需要安装 PyTorch；
- 只有手工运行 `RUN_GFLOWNET_CANDIDATE_EXPERIMENT.bat` 才会执行实验。

## 一、第一次安装

1. 将压缩包完整解压到纯英文、路径较短的目录，例如 `D:\IndustrialProtocolDemo_R7`。
2. 确认机器安装了 64 位 Python 3.8。
3. 如果 Python 没有加入 PATH，可以先在命令提示符设置：

   ```bat
   set PYTHON38_EXE=C:\Python38\python.exe
   ```

4. 双击 `INSTALL_SOURCE_DEPENDENCIES_WIN7.bat`。

安装脚本会创建 `runtime\venvs\model_runtime38` 并安装价格服务、效能服务和表格解析所需依赖。源码包本身不含
wheels，因此首次安装需要互联网或可用的内部 pip 镜像。在已经准备好同名虚拟环境的电脑上可跳过本步骤。

## 二、启动正式系统

1. 双击 `START_ALL_SERVICES_WIN7.bat`。
2. 等待价格服务和效能服务通过健康检查。
3. 浏览器访问 `http://127.0.0.1:17891/`。
4. 数据管理中心访问 `http://127.0.0.1:17891/admin`。

启动后会出现价格服务、效能服务和主系统命令窗口。测试期间不要关闭这些窗口。若 17891 被占用，主系统会尝试
17892～17901；实际端口记录在 `runtime\last_port.txt`。

推荐页面仍执行正式主线算法。当前成品表、价格模型和效能模型已经随包提供，可以直接进行筛选、推荐和改进测试。

## 三、运行 GFlowNet 对比实验

正式系统可以先关闭；实验会自行使用临时端口启动模型服务。

双击：

```text
RUN_GFLOWNET_CANDIDATE_EXPERIMENT.bat
```

本机预计约 1 分钟，较慢的 Win7 电脑可能更久。脚本会：

1. 读取航空舱门锁历史成品表；
2. 启动当前价格模型和效能模型的临时 HTTP 服务；
3. 测试历史价格下界外 1%、2%、3%、5% 的正式算法；
4. 在 5% 越界目标下运行 3 个随机种子的 GFlowNet；
5. 输出正式深度搜索、GFlowNet和组合候选集的JSON对比结果；
6. 自动停止临时服务并删除临时数据库。

重点查看输出末尾的 `gflownet_comparison_5pct`：

- `baseline.minimum_returned_price_wan`：正式深度搜索找到的最低价格；
- `gflownet.runs`：3次GFlowNet的耗时、模型调用和最低价格；
- `hybrid_candidate_set`：保留正式最优点后，由GFlowNet补充多样性方案的结果。

该实验不会修改正式数据库，也不会把GFlowNet设置成默认算法。

## 四、命令行运行方式

在解压目录打开命令提示符：

```bat
runtime\venvs\model_runtime38\Scripts\python.exe -m unittest tests.test_gflownet_generator
runtime\venvs\model_runtime38\Scripts\python.exe tests\price_boundary_generation_benchmark.py
```

第一条是快速单元测试，第二条是完整双模型对比测试。

## 五、常见问题

- 提示找不到 Python：安装64位Python 3.8，或设置 `PYTHON38_EXE`。
- 提示缺少模块：重新运行 `INSTALL_SOURCE_DEPENDENCIES_WIN7.bat`，查看pip是否能访问镜像。
- 18101或18102端口被占用：先关闭旧的价格/效能服务窗口，再启动正式系统。
- 主页面打不开：查看 `logs\startup.log` 和 `runtime\last_port.txt`。
- 模型服务未就绪：查看 `logs\price_service.log`、`logs\effectiveness_service.log`。
- GFlowNet实验时间较长：这是3次独立复测，不影响正常推荐功能，可以直接关闭实验窗口终止。
