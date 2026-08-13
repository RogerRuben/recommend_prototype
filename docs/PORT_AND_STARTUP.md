# 端口与启动处理

## Windows 7现场版

- 默认监听`127.0.0.1`；
- 首选端口17891；
- 若被占用，依次尝试17892—17901；
- 实际端口写入`runtime/last_port.txt`；
- 运行状态写入`runtime/running.json`；
- 价格与效能模型在推荐系统进程内加载，不占用额外端口；
- 浏览器API使用相对路径，端口变化不影响前端。

## 远端版

- Python应用建议只监听`127.0.0.1:8080`；
- Nginx／IIS监听80或443并反向代理；
- Windows临时测试可使用`START_PUBLIC_SERVER_WINDOWS.bat`监听`0.0.0.0`；
- 公网正式部署必须配置HTTPS与认证。

启动失败查看：`logs/startup.log`。

测试失败查看：

```text
logs/full_pipeline_test_console.log
logs/full_pipeline_test_report.json
```


## Cloudflare模式

`tools/cloudflare_demo_launcher.py`先在`127.0.0.1`的17891～17901中选择本地端口，再把实际端口交给`cloudflared`。因此不需要把应用改为监听`0.0.0.0`，也不需要为演示开放入站端口。实际端口与公网地址写入`runtime/cloudflare_demo.json`。
