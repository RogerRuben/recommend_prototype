# V19.6 独立模型服务接口文档

## 1. 服务地址

| 服务 | 默认地址 | 简易前端 | OpenAPI |
|---|---|---|---|
| 价格预测 | `http://127.0.0.1:18101` | `/docs` | `/openapi.json` |
| 效能与可行性 | `http://127.0.0.1:18102` | `/docs` | `/openapi.json` |
| 智能推荐 | `http://127.0.0.1:17891` | `/` | 业务系统接口 |

推荐系统向模型服务传递完整方案JSON。每个模型服务自行选择字段、执行缺失值处理、预处理和模型推理；推荐系统不拼装模型向量。

## 2. 通用方案信封

```json
{
  "request_id": "REQ-001",
  "product_code": "SERVO_CYLINDER_DEMO",
  "scenario": "scheme_edit",
  "parameters": {
    "rated_thrust_n": 12000,
    "mass_kg": 9.8,
    "protection_grade": "IP64",
    "self_diagnosis": true
  },
  "context": {
    "source": "industrial_recommendation_system",
    "locale": "zh-CN"
  }
}
```

未使用字段由服务忽略。服务返回`ignored_fields`、补全字段和模型边界提示。

## 3. 价格预测

### `GET /health`

返回服务状态、后端类型、模型版本、成品代号和模型哈希。`backend=native_pickle`表示直接运行原生模型对象；`portable_json`为无数据科学依赖的演示/兼容模式。

### `GET /api/v1/schema`

返回价格模型字段契约。共享属性、价格专用属性和缺失策略均以此接口为准。

### `POST /api/v1/predict`

请求使用通用方案信封。响应核心结构：

```json
{
  "success": true,
  "prediction": {
    "predicted_price_wan": 9.87,
    "price_interval_wan": [9.11, 10.64],
    "confidence": "medium"
  },
  "input_status": {
    "filled_fields": {},
    "ignored_fields": [],
    "warnings": []
  },
  "domain_status": {
    "in_domain": true,
    "warnings": []
  },
  "model": {
    "backend": "native_pickle",
    "model_version": "price-native-v1",
    "prediction_mode": "native_pickle_exact"
  }
}
```

### `POST /api/v1/predict/batch`

```json
{
  "request_id": "BATCH-001",
  "product_code": "SERVO_CYLINDER_DEMO",
  "items": [
    {"candidate_id": "C001", "parameters": {}},
    {"candidate_id": "C002", "parameters": {}}
  ]
}
```

单批最多1000条。生成器建议每批50—200条。

## 4. 效能与可行性

### `GET /health`

原运行时模式会返回Workbook哈希和State状态；快照模式返回当前快照版本。

### `GET /api/v1/schema`

返回效能字段、工程范围、生成范围、精度、偏好方向，以及V11算法版本、配置版本、state摘要、当前协议身份和评价层级。

### `POST /api/v1/evaluate`

返回：

- `capability_score`：中心效能分，协议参考为100，允许超过100；
- `conservative_capability_score`：P10保守效能分，供工程门槛、效费比和推荐排序使用；
- `protocol_score_interval`：P10-P90稳健区间；
- `support_at_80`、`support_at_100`：稳健模型达到对应阈值的比例；
- `robust_model_count`、`robust_unique_model_count`和`robust_conclusion`；
- `feasibility_probability`和独立`physical_gate`；
- Requirement/UTA/BT来源、条件经验轮廓、耦合评价和成熟专家边界；
- `capability_contributors`：逐属性贡献、协议差值和加减分原因；
- 硬约束冲突、历史经验外推提示和解释文本；
- 当前协议身份、Workbook学习指纹、state SHA-256和完整模型版本。

`physical_gate.passed=false`表示方案不得进入普通推荐结果。门控顺序为硬范围、成熟专家边界、严重耦合不匹配和默认可行概率阈值0.65。综合排序分、低价格或高中心效能均不能覆盖门控结论。

当前正式V11运行包默认协议为`VCA-REQ-001`，同时支持逐请求动态协议。动态协议只改变协议相对效能、贡献账本和相应推荐排序，不修改价格、物理可行性、BT/UTA参数、学习指纹或专家State。

请求可传内置协议编号：

```json
{
  "parameters": {"...": "完整方案参数"},
  "target_protocol": "VCA-REQ-001"
}
```

也可传完整的新协议参考值：

```json
{
  "parameters": {"...": "完整方案参数"},
  "target_protocol": {
    "profile_id": "CUSTOM-REQ-001",
    "profile_name": "某系统新任务成品要求",
    "reference_values": {
      "rated_thrust_n": 9000,
      "stroke_mm": 120,
      "speed_mm_s": 42,
      "protection_grade": 65,
      "overload_protection": 1,
      "mass_kg": 8.5,
      "accuracy_mm": 0.25,
      "response_time_ms": 180,
      "duty_cycle_pct": 70,
      "redundancy_level": 2
    }
  }
}
```

`reference_values`必须完整覆盖所有参与效能的属性。属性方向由模型Schema和Excel属性配置拥有，调用方不得在新协议中重新定义方向。目标值允许位于当前生成范围之外，因为协议可以表达尚未达到的目标；但必须是有限数值。

### `POST /api/v1/evaluate/batch`

格式与价格批量接口一致，单批最多1000条。

批量请求可在顶层统一给出`target_protocol`，也可在每个候选项中覆盖。候选生成缓存会把完整协议纳入指纹，同一参数在不同协议下不会误用旧结果。

### `POST /api/v1/improve`

按需执行V11协议锚定反事实搜索。请求包含完整方案参数和可选`target_protocol`。效能服务返回低改动参数处方；推荐网关把处方覆盖到原方案上，保留材料牌号等价格专用字段，再重新计算价格、效能、物理门控、标签和业务约束。

该接口只用于少量入选方案，不应对几百或几千个初始候选逐一调用。

## 5. 错误响应

```json
{
  "success": false,
  "error": "bad_request",
  "message": "效能模型缺少必填字段: mass_kg",
  "details": {}
}
```

常见HTTP状态：400请求或字段错误、404路径不存在、413请求过大、500模型加载或推理异常。

## 6. 版本与一致性原则

每次结果必须保留：`product_code`、`model_version`、`algorithm_version`、`state_sha256`、`backend`、协议身份和服务版本。价格原生模式的正式验收应比较原Notebook与服务预测，效能原运行时模式应比较原交互工程与服务结果。产品代号不一致、配置版本不兼容或state摘要不一致时不得用于推荐系统正式计算。

## 7. 模型发布文件

价格服务正式产物：`price_native_bundle.pkl`及同名`.manifest.json`。Manifest记录训练环境和模型对象依赖模块。

效能服务正式产物：`effectiveness_runtime_manifest.json`所在的完整目录，包含原源码、Workbook、可选State、文件SHA-256和学习指纹。不得只复制Manifest而遗漏其目录内容。
