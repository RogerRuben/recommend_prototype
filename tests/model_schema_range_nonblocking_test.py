# -*- coding: utf-8 -*-
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from app.range_diagnostics import build_range_diagnostics
from app.model_service_client import ServiceBackedRuntime

class Gateway:
    product_code="P"; fallback=False
    def __init__(self): self.called=[]
    def schemas(self):
        field={"field_name":"xx","field_label":"XX","dtype":"number","generation_min":1.5,"generation_max":5,"required":True,"missing_policy":"reject"}
        return {"price":{"product_code":"P","fields":[dict(field)]},"effectiveness":{"product_code":"P","fields":[dict(field)]}}
    def evaluate(self,params,target_protocol=None): self.called.append(dict(params)); return {"parameters":dict(params)}

items = build_range_diagnostics(
    {"xx": 1}, {"xx": {"label": "XX", "min_value": 0, "max_value": 2}},
    [{"key": "xx", "model_kind": "effectiveness", "min": 1.5, "max": 5}], {"xx": 1},
)
assert items[0]["model_contracts"]["effectiveness"]["inside"] is False
assert items[0]["actual"] == 1
gateway=Gateway(); runtime=ServiceBackedRuntime(gateway); result=runtime.evaluate({"xx":1})
assert gateway.called==[{"xx":1}] and result["parameters"]["xx"]==1
print("PASS schema range is diagnostic only")
