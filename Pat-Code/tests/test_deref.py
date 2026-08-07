import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.base import _deref_schema
import json

schema_props = {
    "action": {"$ref": "#/$defs/Action"},
    "items": {"type": "array", "items": {"$ref": "#/$defs/Item"}},
}
defs = {
    "Action": {"type": "string", "enum": ["read", "write"]},
    "Item": {"type": "object", "properties": {"name": {"type": "string"}}},
}
result = _deref_schema(schema_props, defs)
raw = json.dumps(result)
print(json.dumps(result, indent=2))
if "$ref" in raw:
    print("FAIL: $ref still present")
    sys.exit(1)
print("OK: no $ref in output")
