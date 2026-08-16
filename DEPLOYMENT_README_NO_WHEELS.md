# Source deployment package without wheels

This package includes the recommendation system, model services, current model artifacts, test data, documentation and tests. It does not include wheels or a virtual environment.

1. Install 64-bit Python 3.8.
2. With Internet or an internal pip mirror, run INSTALL_SOURCE_DEPENDENCIES_WIN7.bat.
3. For an offline target, provide dependency wheels separately or copy an accepted runtime\venvs\model_runtime38. Wheels are intentionally absent here.
4. Run VERIFY_MODEL_ENVIRONMENTS.bat.
5. Run START_ALL_SERVICES_WIN7.bat. Readiness requires real numeric price/effectiveness JSON responses; Schema and product-code differences are operator warnings, not preflight blockers.
6. Open http://127.0.0.1:17891/; use /admin for data maintenance, /price for price-only prediction and /effectiveness for effectiveness-only evaluation.
7. In Product Data Workspace, ordinary historical CSV/XLSX data can be analyzed, edited and switched independently of the currently running HTTP model product.
8. A business/model mismatch pauses model calculations only; it does not block data maintenance, switching, or historical-product recommendation.
9. Open the single *V19_6*.ipynb file in the package. Set only PRODUCT_CODE in the final cell; any fitted model subset is accepted and installed directly as price_native_bundle.pkl.
10. The data center model page reads HTTP health/schema and produces example JSON. It does not load local model files in service mode.
11. Use examples/final_acceptance for the encoded English-field workbook, V10/V11 expert-state JSON, and matching virtual model artifacts.

Online effectiveness learning is external. Prefer INSTALL_FROZEN_EFFECTIVENESS_MODEL_WIN7.bat for effectiveness_model_*.zip exported by the final V11 expert software.
The legacy source + Workbook + State path remains available through PACKAGE_EFFECTIVENESS_SERVICE_MODEL_WIN7.bat.
