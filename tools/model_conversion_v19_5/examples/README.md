# 示例模型说明

- `effectiveness_bundle_from_uploaded_workbook_baseline.json`：使用用户提供的效能工程源码和`aircraft_door_lock_demo.xlsx`重新构建并导出；上传包中没有正式State，因此属于Workbook基线快照。
- `price_bundle_synthetic_validation.json`：使用与效能字段兼容的合成价格数据生成，只用于验证价格转换、共享字段和价格专用字段链路，不代表真实价格精度。
- `runtime_test_models/`：供自检脚本加载的同一模型对。
- `synthetic_price_training_ONLY_FOR_CONVERTER_TEST.csv`：只用于转换器回归测试。

这些文件不能作为正式报价或工程结论。正式价格模型必须使用真实价格训练表重新转换。
