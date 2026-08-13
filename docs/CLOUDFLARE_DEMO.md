# Cloudflare登录演示部署

V19提供Quick Tunnel和稳定域名Tunnel。`cloudflared`只转发同一个推荐系统端口，价格和效能模型仍在推荐系统进程中运行。

## 默认登录

```text
账号：ab123
密码：ab123
```

启动器会设置：

```text
IPDEMO_AUTH_ENABLED=1
IPDEMO_AUTH_USERNAME=ab123
IPDEMO_AUTH_PASSWORD=ab123
IPDEMO_DEMO_READ_ONLY=1
```

可以在启动前通过环境变量替换账号和密码。

## Quick Tunnel

Windows 10/11或Windows Server：

```bat
INSTALL_CLOUDFLARED_WINDOWS.bat
START_CLOUDFLARE_DEMO_WINDOWS.bat
```

启动后控制台显示随机地址：

```text
https://xxxxx.trycloudflare.com
```

访问者首先进入登录页。登录后推荐页、专家方案库和`/admin`数据管理页面均可查看。

关闭：在启动窗口按`Ctrl+C`，或运行：

```bat
STOP_CLOUDFLARE_DEMO_WINDOWS.bat
```

## 登录后的只读范围

允许：

- 历史协议推荐；
- 标签和指标筛选；
- 条件驱动实时生成；
- 方案修改与价格、效能重算；
- 专家方案库和详情只读查看；
- 成品、指标、标签、耦合、约束、协议和模型信息查看；
- 宽表CSV/XLSX内存解析预览；
- 模板、数据库和JSON读取下载。

禁止：

- 保存专家方案；
- 数据库增删改；
- 提交宽表导入；
- 备份创建与恢复；
- 数据库上传恢复；
- 模型替换。

写入限制在后端执行，不依赖前端隐藏按钮。演示模式下SQLite使用`mode=ro`连接，业务数据库不会被启动迁移或页面操作修改。运行日志、端口状态和Cloudflare状态文件仍会写入`logs/`和`runtime/`，它们不属于业务数据。

## 稳定域名Tunnel

1. 在Cloudflare Dashboard创建Tunnel；
2. Public Hostname指向`http://127.0.0.1:17891`；
3. 设置Token：

```bat
set CLOUDFLARE_TUNNEL_TOKEN=你的Token
START_CLOUDFLARE_STABLE_WINDOWS.bat
```

也可以将Token写入`deploy/cloudflare/tunnel_token.txt`。

应用登录适合演示。长期部署建议同时使用Cloudflare Access进行身份验证和访问策略控制。

## Linux

```bash
export IPDEMO_AUTH_USERNAME=ab123
export IPDEMO_AUTH_PASSWORD=ab123
./start_cloudflare_demo.sh
```

稳定Tunnel：

```bash
export CLOUDFLARE_TUNNEL_TOKEN='你的Token'
./start_cloudflare_stable.sh
```

## Windows 7

现场Win7继续使用`START_ALL_WIN7.bat`。Cloudflare演示建议运行在Windows 10/11、Windows Server或Linux机器上。
