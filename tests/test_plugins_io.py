import json
from pathlib import Path

import pytest

from utils.plugins_io import load_plugins


def _write(tmp_path: Path, data) -> str:
    p = tmp_path / "plugins.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_load_plugins_from_list(tmp_path):
    data = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    path = _write(tmp_path, data)
    res = load_plugins(path)
    assert isinstance(res, dict)
    assert set(res.keys()) == {"a", "b"}
    assert res["a"]["name"] == "A"


def test_load_plugins_from_dict(tmp_path):
    data = {"a": {"name": "A"}, "b": {"name": "B"}}
    path = _write(tmp_path, data)
    res = load_plugins(path)
    assert res == data


def test_missing_file_returns_empty(tmp_path):
    path = tmp_path / "does_not_exist.json"
    res = load_plugins(str(path))
    assert res == {}


def test_malformed_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not: valid json }", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_plugins(str(p))


def test_missing_id_in_list_raises_valueerror(tmp_path):
    data = [{"name": "no id"}]
    path = _write(tmp_path, data)
    with pytest.raises(ValueError):
        load_plugins(path)


def test_unsupported_format_raises_valueerror(tmp_path):
    path = _write(tmp_path, 123)
    with pytest.raises(ValueError):
        load_plugins(path)
