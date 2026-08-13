# 模型字段映射

| 内部字段 | 页面名称 | 类型 | 单位 |
|---|---|---|---|
| stroke_mm | 行程 | 数值 | mm |
| rated_thrust_n | 额定推力 | 数值 | N |
| peak_thrust_n | 峰值推力 | 数值 | N |
| speed_mm_s | 运行速度 | 数值 | mm/s |
| accuracy_mm | 定位精度 | 数值 | mm |
| response_time_ms | 响应时间 | 数值 | ms |
| temp_low_c | 工作温度下限 | 数值 | ℃ |
| temp_high_c | 工作温度上限 | 数值 | ℃ |
| duty_cycle_pct | 连续工作制 | 数值 | % |
| mass_kg | 质量上限 | 数值 | kg |
| salt_spray_h | 盐雾试验时间 | 数值 | h |
| protection_grade | 防护等级 | IP枚举 | IP54—IP68 |
| manual_emergency | 手动应急 | 布尔 | 有/无 |
| self_lock | 自锁功能 | 布尔 | 有/无 |
| position_feedback | 位置反馈 | 布尔 | 有/无 |
| overload_protection | 过载保护 | 布尔 | 有/无 |
| self_diagnosis | 自诊断 | 布尔 | 有/无 |

页面不会再把`IP58`显示成`58`，也不会把布尔值显示成空白数字框。
