# V19.5 模型验收清单

- [ ] 两个模型均为契约4.0纯JSON；
- [ ] `product_code`一致；
- [ ] 共享字段编号、类型、单位、来源一致；
- [ ] 价格专用必填字段存在可用缺失策略；
- [ ] 效能模型使用正确Workbook和匹配State；
- [ ] 效能导出历史全样本一致性检查通过；
- [ ] 价格训练显式指定特征，未使用价格类别、Cluster或异常标签；
- [ ] 价格单位通过`target_divisor`统一为万元；
- [ ] 训练数据指纹、测试集R²、MAPE和残差区间已记录；
- [ ] `validate_and_install_models.py --validate-only`通过；
- [ ] 安装后的完整Application启动冒烟测试通过；
- [ ] 切换成品时同时提供匹配DataMaster；
- [ ] 真实工程使用前完成专家审核和外部验证。
