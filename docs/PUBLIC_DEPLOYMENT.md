# 远端／公网部署

## 现场Windows 7

现场仍使用：

```text
START_ALL_WIN7.bat
```

默认只监听`127.0.0.1`，适合单机演示和内网受控使用。

## Windows远端测试

设置端口后运行：

```bat
set IPDEMO_PORT=8080
START_PUBLIC_SERVER_WINDOWS.bat
```

该脚本监听`0.0.0.0`。仅建议在受控内网或临时测试环境使用，并通过Windows防火墙限制来源地址。

## Linux服务器

推荐结构：

```text
Internet
→ HTTPS / 身份认证 / 访问控制
→ Nginx或其他反向代理
→ 127.0.0.1:8080
→ V19推荐系统
```

随包提供：

- `start_public_server.sh`；
- `deploy/ipdemo.service`；
- `deploy/nginx_ipdemo.conf`。

## 安全边界

当前应用自身没有账号、权限和CSRF保护，因此不能直接把Python端口暴露到公网。正式发布至少需要：

- HTTPS；
- 登录认证或企业统一身份认证；
- 数据管理路径的额外访问限制；
- 防火墙／安全组；
- 数据库和模型文件备份；
- 反向代理请求体大小、超时和访问日志；
- 公网域名和证书。


## Cloudflare Tunnel演示

V19保留Quick Tunnel与Dashboard Token Tunnel。临时演示使用`START_CLOUDFLARE_DEMO_WINDOWS.bat`，应用只监听`127.0.0.1`，由`cloudflared`产生随机公网地址。默认只读，数据管理和持久化写入被后端阻止。详见`docs/CLOUDFLARE_DEMO.md`。
