# 给 Codex 的启动提示词

请先阅读项目根目录 `CODEX_HANDOFF_V19_6.md`，不要立即改动算法。

当前基线是 V19.6 ServiceGovernance 加上累计 PriceDynamicModels Hotfix。请先：

1. 扫描目录和现有测试；
2. 运行 `tests/price_dynamic_model_hotfix_test.py`、`tests/v19_6_service_governance_test.py`、`tests/full_pipeline_test.py`；
3. 确认当前演示模型后端与正式模型后端的区别；
4. 列出准备修改的文件、风险和回滚方案；
5. 第一阶段只做基线收口：统一配置、统一启动器、三个 Python 环境、正式模式关闭静默回退、版本与 backend 可见性；
6. 每次修改后保持全部既有测试通过，并补充针对新行为的测试；
7. 不要删除本地 IntegratedModelRuntime，除非已经把 Schema、生成空间和回退依赖全部替代并通过完整回归；
8. 不要把演示 `portable_json`/`snapshot_json` 误标成正式模型；
9. 不要加载未明确授权的任意 pickle；
10. 任何产品切换必须校验 product_code、字段 ID、类型、单位、模型版本和 DataMaster。

先给出代码审计结果和分阶段计划，不要在第一步大规模重构。
