import json
import sys
import types
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

sys.modules.setdefault("can", types.ModuleType("can"))
_yaml_mod = types.ModuleType("yaml")
_yaml_mod.safe_load = lambda *args, **kwargs: {}
sys.modules.setdefault("yaml", _yaml_mod)

from e46_can_udp import canonicalize


def build_payload(decoded: Dict[str, Any]) -> Dict[str, Any]:
    canon = canonicalize(decoded)
    # mimic the main loop's tracking dictionary
    canon["_can_id"] = 0x2A5
    canon["_ts"] = 1234.5
    last: Dict[str, Any] = {}
    last.update(canon)
    payload = {k: v for k, v in last.items() if not k.startswith("_")}
    # ensure JSON serialization behaves as expected
    json.loads(json.dumps({"payload": payload}))
    return payload


def test_sport_button_state_numeric_payload():
    payload = build_payload({"STATE_SOF_CAN": 1})
    assert "sport_button_state" in payload
    assert payload["sport_button_state"] == 1.0
