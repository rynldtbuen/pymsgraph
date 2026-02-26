from __future__ import annotations

import re

import pytest

from pymsgraph.utils import load_config


def test_load_config_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"tenant": "contoso", "retry": 3}', encoding="utf-8")

    cfg = load_config(str(path))

    assert cfg == {"tenant": "contoso", "retry": 3}


def test_load_config_toml(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        '[graph]\nbase_url = "https://graph.microsoft.com/v1.0"\n',
        encoding="utf-8",
    )

    cfg = load_config(str(path))

    assert cfg == {"graph": {"base_url": "https://graph.microsoft.com/v1.0"}}


@pytest.mark.parametrize("suffix", ["ini", "cfg"])
def test_load_config_ini_like(tmp_path, suffix):
    path = tmp_path / f"config.{suffix}"
    path.write_text(
        "[auth]\nclient_id = abc\ntenant = contoso\n",
        encoding="utf-8",
    )

    cfg = load_config(str(path))

    assert cfg == {"auth": {"client_id": "abc", "tenant": "contoso"}}


def test_load_config_uses_default_filename_from_ext(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text('[app]\nname = "pymsgraph"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = load_config(ext="toml")

    assert cfg == {"app": {"name": "pymsgraph"}}


def test_load_config_path_without_suffix_uses_ext(tmp_path):
    path = tmp_path / "config"
    path.write_text('[section]\nvalue = "x"\n', encoding="utf-8")

    cfg = load_config(str(path), ext="toml")

    assert cfg == {"section": {"value": "x"}}


def test_load_config_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported config extension"):
        load_config(ext="yaml")


def test_load_config_missing_file_raises(tmp_path):
    path = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError, match=re.escape(str(path))):
        load_config(str(path), ext="toml")
