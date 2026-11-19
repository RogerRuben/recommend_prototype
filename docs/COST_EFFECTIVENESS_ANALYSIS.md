# 效费比分析工作台

在系统门户 `/portal` 选择「效费比分析」，当前标签页会打开同一站点的 `/cost-effectiveness/`。工作台从 SQLite 数据库只读加载历史方案和专家保存方案，调用主系统配置的价格与效能 HTTP 服务，按主系统的价格单位计算效费比与 Pareto 前沿。

方案选择区支持名称/编号搜索、来源筛选、全选当前结果、反选当前结果和清空已选。搜索或切换来源不会清除其他筛选结果中已勾选的方案；所有批量操作都遵守每次最多 30 个方案的限制。

## 启动与依赖

站内工作台随推荐系统启动并沿用登录会话。开始分析前需要启动配置的价格和效能 HTTP 服务。也可在启动两个模型服务后单独运行工作台：

```text
python -m cost_effectiveness_analysis.app --port 17000
```

推荐服务 `:17891` 不需要启动。浏览器只访问 `:17000`，由后端批量调用两个模型服务，不会直连模型端口。

环境变量 `COST_EFFECTIVENESS_HOST`、`COST_EFFECTIVENESS_PORT`、`COST_EFFECTIVENESS_DATABASE`、`COST_EFFECTIVENESS_PRICE_URL`、`COST_EFFECTIVENESS_EFFECTIVENESS_URL`、`COST_EFFECTIVENESS_TIMEOUT_SECONDS`、`COST_EFFECTIVENESS_PRICE_OUTPUT_UNIT` 和 `COST_EFFECTIVENESS_PRICE_OUTPUT_SCALE` 可覆盖默认值。

## 独立运行配置

独立配置位于 `config/cost_effectiveness_analysis.json`。数据库路径、页面监听地址、两个模型 API 地址和价格输出换算都在这里维护，不使用 Portal URL 或 `model_services.json` 作为本服务配置。

价格服务的原始数值必须在 `price_output` 中声明单位和附加尺度，例如价格服务返回“元”时：

```json
"price_output": {
  "unit": "yuan",
  "scale": 1.0
}
```

允许的 `unit` 为 `yuan`、`thousand_yuan`、`wan_yuan`、`million_yuan`。换算规则与推荐系统一致：`服务返回值 × scale × 单位换算系数 = 万元价格`。但效费比工作台读取自己的配置，修改 `model_services.json` 不会隐式改变本页面。默认值 `wan_yuan / 1.0` 保持现有模型无需换算时的行为。配置非法、尺度非有限或不大于零时，服务会拒绝启动，避免产生静默错价。

SQLite 数据库始终通过 URI `mode=ro` 打开，并额外启用 `PRAGMA query_only=ON`。服务不提供保存、修改或删除接口；分析结果仅驻留在当前页面内存中，刷新后消失。

## API

- `GET /health`：数据库只读状态和两个模型服务状态。
- `GET /api/schemes?source=&search=`：读取方案概要。
- `GET /api/schemes/{scheme_id}`：读取方案及业务参数。
- `POST /api/analyze`：接收 2–30 个 `scheme_ids` 和可选 `target_protocol`，批量重新计算并返回 CE、Pareto、KPI 与模型版本。

价格先按上述独立配置统一换算成万元，再计算 `capability_score / predicted_price_wan`。价格小于等于零时效费比为 `null`。价格或效能任一计算失败的方案仍在结果中展示，但不参与效费比和 Pareto 判断。API 的 `price_output` 和每个方案的 `price_output_normalization` 会返回本次换算规则与原始值，页面“技术信息”也会显示生效单位和尺度。

模型调用首先发送一个批量请求。如果模型服务因为某个旧方案缺少必填字段而拒绝整批请求，工作台会递归拆分批次以定位异常方案；完整方案仍返回计算结果，只有真正异常的方案显示失败原因。模型服务整体不可连接时不会进行拆分重试。

## Portal 配置

`config/service_portal.json` 中的 `cost_effectiveness_analysis` 默认使用 `/cost-effectiveness/`。旧配置中保存的默认 `http://127.0.0.1:17000` 地址在读取时会转换为站内入口。管理员可在“系统设置 → 服务导航配置”修改名称、描述、URL、显示和启用状态。配置 HTTP 或 HTTPS 外部地址时，门户会在新标签页打开。

## 测试

```text
python -m pytest cost_effectiveness_analysis/tests -q
```

只读测试会实际尝试 `INSERT`、`UPDATE`、`DELETE`、`CREATE TABLE` 和 `DROP TABLE`，并断言 SQLite 拒绝全部写操作。
