# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from app.value_semantics import business_display_value
d={"value_type":"boolean","display_value_mapping_json":{"0":"未配置","1":"已配置"}}
assert business_display_value(0,d)=="未配置" and business_display_value(1,d)=="已配置"
print("PASS custom boolean display labels override defaults only in presentation")
