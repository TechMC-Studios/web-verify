import json
from pathlib import Path
from typing import Dict, Any, Optional


def load_plugins(path: Optional[str] = None) -> Dict[str, Any]:
    if path is None:
        base = Path(__file__).resolve().parent.parent
        path = base / "data" / "plugins.json"
    else:
        path = Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        raise

    plugins: Dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            plugins[str(k)] = v
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            pid = item.get("id")
            if not pid:
                raise ValueError("each plugin entry must include an 'id' field")
            plugins[str(pid)] = item
    else:
        raise ValueError("unsupported plugins.json format: expected list or dict")

    return plugins


__all__ = ["load_plugins"]