# -*- coding: utf-8 -*-
from __future__ import print_function
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.model_runtime import IntegratedModelRuntime

eff=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'models'/'effectiveness_bundle.json'
price=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'models'/'price_bundle.json'
report=IntegratedModelRuntime.validate_pair(eff,price)
clean=dict((k,v) for k,v in report.items() if k not in ('effectiveness','price'))
print(json.dumps(clean,ensure_ascii=False,indent=2))
sys.exit(0 if report['valid'] else 2)
