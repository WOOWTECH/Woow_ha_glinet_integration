"""Static checks of the files Home Assistant, hassfest and HACS read: translations, services.yaml, manifest, hacs.json."""

from __future__ import annotations

import ast
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import voluptuous as vol
import yaml
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.service import async_get_all_descriptions
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.woow_glinet import services
from custom_components.woow_glinet.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "woow_glinet"
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


EN = load_json(PACKAGE / "translations" / "en.json")
ZH = load_json(PACKAGE / "translations" / "zh-Hant.json")


def leaves(tree: Any, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], str]:
    """Every string in a translation tree, by its key path."""
    if isinstance(tree, dict):
        out: dict[tuple[str, ...], str] = {}
        for key, value in tree.items():
            out |= leaves(value, (*path, key))
        return out
    assert isinstance(tree, str), f"{'.'.join(path)}: translation values must be strings, got {type(tree).__name__}"
    return {path: tree}


def shape(tree: Any) -> Any:
    """The tree with the strings blanked: two trees with the same shape have identical keys at every level."""
    return {k: shape(v) for k, v in tree.items()} if isinstance(tree, dict) else None


# ===================================================================================== translations
def test_the_translation_files_exist() -> None:
    assert sorted(p.name for p in (PACKAGE / "translations").glob("*.json")) == ["en.json", "zh-Hant.json"]


def test_en_and_zh_hant_have_identical_key_trees() -> None:
    en, zh = leaves(EN), leaves(ZH)
    assert set(en) - set(zh) == set(), f"missing in zh-Hant: {sorted('.'.join(k) for k in set(en) - set(zh))}"
    assert set(zh) - set(en) == set(), f"missing in en: {sorted('.'.join(k) for k in set(zh) - set(en))}"
    assert shape(EN) == shape(ZH)


def test_en_and_zh_hant_use_the_same_placeholders_in_every_string() -> None:
    en, zh = leaves(EN), leaves(ZH)
    wrong = {".".join(k): (sorted(PLACEHOLDER.findall(en[k])), sorted(PLACEHOLDER.findall(zh[k]))) for k in en if PLACEHOLDER.findall(en[k]) != PLACEHOLDER.findall(zh[k]) and set(PLACEHOLDER.findall(en[k])) != set(PLACEHOLDER.findall(zh[k]))}
    assert wrong == {}


def test_no_translation_is_empty_or_has_stray_braces() -> None:
    for lang, tree in (("en", EN), ("zh-Hant", ZH)):
        for path, text in leaves(tree).items():
            assert text.strip(), f"{lang}: {'.'.join(path)} is empty"
            stripped = PLACEHOLDER.sub("", text)
            assert "{" not in stripped and "}" not in stripped, f"{lang}: {'.'.join(path)} has an unbalanced brace: {text!r}"


def test_zh_hant_is_really_translated() -> None:
    en, zh = leaves(EN), leaves(ZH)
    same = [".".join(k) for k in en if en[k] == zh[k]]
    assert len(same) <= max(2, len(en) // 20), f"strings still in English in zh-Hant: {same}"
    assert any(re.search(r"[一-鿿]", zh[k]) for k in zh if k[0] == "config")


def test_the_top_level_sections() -> None:
    assert {"config", "services", "options", "entity"} <= set(EN)


# What each form field is called, step by step: the keys the flows' schemas use
FLOW_STEPS = {
    ("config", "user"): {"host", "username", "password", "scheme", "verify_ssl"},
    ("config", "reauth_confirm"): {"username", "password"},
    ("config", "reconfigure"): {"host", "username", "password", "scheme", "verify_ssl"},
    ("options", "init"): {"expose_wifi_passwords"},
}


@pytest.mark.parametrize(("section", "step"), list(FLOW_STEPS))
def test_every_form_field_is_labelled(section: str, step: str) -> None:
    for lang, tree in (("en", EN), ("zh-Hant", ZH)):
        data = tree[section]["step"][step]["data"]
        assert set(data) == FLOW_STEPS[(section, step)], f"{lang}: {section}.{step}.data"
        assert tree[section]["step"][step]["title"]


def test_the_form_fields_match_the_flows_schemas() -> None:
    from custom_components.woow_glinet.config_flow import STEP_USER_SCHEMA

    assert {str(k) for k in STEP_USER_SCHEMA.schema} == FLOW_STEPS[("config", "user")]


def test_placeholders_in_the_step_texts_are_the_ones_the_flows_provide() -> None:
    provided = {"user": set(), "reauth_confirm": {"host", "name"}, "reconfigure": {"name"}}
    for step, allowed in provided.items():
        for field in ("title", "description"):
            used = set(PLACEHOLDER.findall(EN["config"]["step"][step][field]))
            assert used <= allowed, f"config.step.{step}.{field} uses {used - allowed} which the flow does not supply"
    for field in ("title", "description"):
        assert not PLACEHOLDER.findall(EN["options"]["step"]["init"][field])


def test_every_error_and_abort_reason_the_flows_can_produce_is_translated() -> None:
    source = (PACKAGE / "config_flow.py").read_text(encoding="utf-8")
    errors = set(re.findall(r'errors\["base"\] = "(\w+)"', source))
    reasons = set(re.findall(r'reason="(\w+)"', source)) | {"already_configured", "reauth_successful", "reconfigure_successful"}
    assert errors == {"invalid_auth", "cannot_connect"}
    for lang, tree in (("en", EN), ("zh-Hant", ZH)):
        assert errors <= set(tree["config"]["error"]), lang
        assert reasons <= set(tree["config"]["abort"]), f"{lang}: {reasons - set(tree['config']['abort'])}"


def test_the_service_translations() -> None:
    for tree in (EN, ZH):
        assert set(tree["services"]) == {"add_static_ip", "remove_static_ip"}
        for service in tree["services"].values():
            assert service["name"] and service["description"]


def test_entity_translations_cover_what_the_platforms_use() -> None:
    """Every `translation_key` in the platform modules has a name in both languages (the registry-based check
    in test_platforms.py covers what is created at run time; this one catches entities not created by the mock)."""
    keys: dict[str, set[str]] = {}
    for platform in ("sensor", "switch", "button", "text", "device_tracker", "entity"):
        tree = ast.parse((PACKAGE / f"{platform}.py").read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(getattr(t, "attr", getattr(t, "id", "")) == "_attr_translation_key" for t in node.targets):
                value = node.value
                if isinstance(value, ast.Constant):
                    found.add(value.value)
                elif isinstance(value, ast.Subscript) and isinstance(value.value, ast.Dict):  # {"rx": "client_download", ...}[key]
                    found |= {v.value for v in value.value.values if isinstance(v, ast.Constant)}
        keys[platform] = found
    assert sum(len(v) for v in keys.values()) >= 10, "found too few translation keys: the test is out of date"
    for lang, tree in (("en", EN), ("zh-Hant", ZH)):
        for platform, found in keys.items():
            for key in found:
                assert tree["entity"][platform][key]["name"], f"{lang}: entity.{platform}.{key}.name"


def test_wifi_entity_names_use_the_ssid_placeholder() -> None:
    for tree in (EN, ZH):
        for platform, key in (("switch", "wifi"), ("text", "wifi_ssid"), ("text", "wifi_key")):
            assert PLACEHOLDER.findall(tree["entity"][platform][key]["name"]) == ["ssid"]


# ===================================================================================== services.yaml
SERVICES = yaml.safe_load((PACKAGE / "services.yaml").read_text(encoding="utf-8"))


def test_services_yaml_parses_and_names_the_two_services() -> None:
    assert set(SERVICES) == {"add_static_ip", "remove_static_ip"}


async def test_every_service_in_services_yaml_is_registered_and_vice_versa(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert set(SERVICES) == set(hass.services.async_services_for_domain(DOMAIN))


@pytest.mark.parametrize(
    ("service", "schema"),
    [("add_static_ip", services.ADD_STATIC_IP_SCHEMA), ("remove_static_ip", services.REMOVE_STATIC_IP_SCHEMA)],
)
def test_the_yaml_fields_are_the_schema_fields(service: str, schema: vol.Schema) -> None:
    fields = SERVICES[service]["fields"]
    assert set(fields) == {str(k) for k in schema.schema}
    required = {str(k) for k in schema.schema if isinstance(k, vol.Required)}
    assert {name for name, spec in fields.items() if spec.get("required")} == required, "'required' in the yaml differs from the schema"
    for name, spec in fields.items():
        assert spec.get("name") and spec.get("description"), f"{service}.{name} needs a name and a description"
        selector.selector(spec["selector"])  # a valid selector


def test_the_device_selector_is_limited_to_this_integration() -> None:
    for service in SERVICES.values():
        assert service["fields"]["device_id"]["selector"] == {"device": {"integration": DOMAIN}}


def test_service_names_and_descriptions_exist() -> None:
    for service in SERVICES.values():
        assert service["name"] and service["description"]


async def test_home_assistant_loads_the_service_descriptions(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    descriptions = await async_get_all_descriptions(hass)
    assert set(descriptions[DOMAIN]) == {"add_static_ip", "remove_static_ip"}
    assert set(descriptions[DOMAIN]["add_static_ip"]["fields"]) == {"device_id", "mac", "ip", "name"}


# ===================================================================================== manifest and HACS
MANIFEST = load_json(PACKAGE / "manifest.json")
REQUIRED_MANIFEST_KEYS = {
    "domain", "name", "codeowners", "config_flow", "dependencies", "documentation", "integration_type", "iot_class",
    "issue_tracker", "requirements", "version",
}  # fmt: skip


def test_manifest_has_every_required_key() -> None:
    assert REQUIRED_MANIFEST_KEYS <= set(MANIFEST), f"missing: {REQUIRED_MANIFEST_KEYS - set(MANIFEST)}"
    assert not set(MANIFEST) - REQUIRED_MANIFEST_KEYS - {"loggers", "single_config_entry", "quality_scale", "zeroconf", "ssdp", "dhcp", "bluetooth"}, "unexpected keys"


def test_manifest_identity() -> None:
    assert MANIFEST["domain"] == DOMAIN == PACKAGE.name == "woow_glinet"
    assert MANIFEST["config_flow"] is True and (PACKAGE / "config_flow.py").is_file()
    assert MANIFEST["integration_type"] == "hub" and MANIFEST["iot_class"] == "local_polling"
    assert re.fullmatch(r"\d+\.\d+\.\d+", MANIFEST["version"]), "custom integrations need a plain x.y.z version"
    assert MANIFEST["codeowners"] and all(c.startswith("@") for c in MANIFEST["codeowners"])
    assert MANIFEST["documentation"].startswith("https://") and MANIFEST["issue_tracker"].startswith("https://")


def test_manifest_keys_are_in_hassfest_order() -> None:
    """hassfest: `domain`, `name`, then alphabetical."""
    assert list(MANIFEST) == ["domain", "name", *sorted(k for k in MANIFEST if k not in ("domain", "name"))]


def test_manifest_dependencies() -> None:
    assert {"frontend", "http", "panel_custom", "websocket_api"} <= set(MANIFEST["dependencies"])
    assert len(MANIFEST["dependencies"]) == len(set(MANIFEST["dependencies"]))


def test_what_the_code_imports_is_declared() -> None:
    """Third-party imports must be in `requirements` (Home Assistant core supplies aiohttp and voluptuous)."""
    provided = {"homeassistant", "aiohttp", "voluptuous", "yarl", "custom_components"}
    third_party: set[str] = set()
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else []
            for name in names:
                top = name.split(".")[0]
                if top not in sys.stdlib_module_names and top not in provided:
                    third_party.add(top)
    declared = {re.split(r"[<>=!~\[ ]", r)[0].lower() for r in MANIFEST["requirements"]}
    assert third_party <= declared, f"imported but not in manifest requirements: {third_party - declared}"
    assert "passlib" in declared


def test_requirements_are_pinned_with_a_lower_bound() -> None:
    for requirement in MANIFEST["requirements"]:
        assert re.search(r"[<>=]=?\d", requirement), f"{requirement}: unpinned"


def test_hacs_json() -> None:
    hacs = load_json(ROOT / "hacs.json")
    assert hacs["name"] and re.fullmatch(r"\d{4}\.\d+\.\d+", hacs["homeassistant"])
    assert set(hacs) <= {"name", "homeassistant", "render_readme", "content_in_root", "zip_release", "filename", "hacs", "country", "persistent_directory"}
    year, month, _ = (int(x) for x in hacs["homeassistant"].split("."))
    import homeassistant.const as ha_const

    running = tuple(int(x) for x in ha_const.__version__.split(".")[:2])
    assert (year, month) <= running, "hacs.json asks for a Home Assistant newer than the one this suite runs on"


def test_files_hacs_and_the_brand_page_need() -> None:
    assert (ROOT / "README.md").is_file() and (ROOT / "LICENSE").is_file()
    for name in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        png = PACKAGE / "brand" / name
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"{name} is not a PNG"
    assert (PACKAGE / "services.yaml").is_file() and (PACKAGE / "frontend" / "woow-glinet-panel.js").is_file()


def test_only_one_integration_lives_in_the_repository() -> None:
    assert [p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir() and p.name != "__pycache__"] == ["woow_glinet"]


# ===================================================================================== the code itself
MODULES = sorted(p.stem for p in PACKAGE.glob("*.py"))


@pytest.mark.parametrize("module", MODULES)
def test_every_module_imports_cleanly(module: str) -> None:
    importlib.import_module(f"custom_components.woow_glinet.{module}" if module != "__init__" else "custom_components.woow_glinet")


def test_the_module_list_is_what_we_think() -> None:
    expected = {
        "__init__", "actions", "activity", "api", "button", "config_flow", "const", "coordinator", "device", "device_tracker",
        "diagnostics", "entity", "feed", "history", "panel", "sanitize", "sensor", "services", "switch", "text", "websocket_api",
    }  # fmt: skip
    assert set(MODULES) == expected, f"new/removed modules: {set(MODULES) ^ expected} (add tests for them)"


def test_no_secret_is_hard_coded() -> None:
    """A cheap guard against committing a real credential: no password-looking assignment of a string literal."""
    pattern = re.compile(r"(?i)\b(password|passwd|secret|token)\w*\s*=\s*['\"][^'\"]{4,}['\"]")
    hits = []
    for path in PACKAGE.glob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "default" not in line.lower():
                hits.append(f"{path.name}:{number}: {line.strip()}")
    assert hits == []


def test_nothing_of_the_real_lab_is_in_the_repository() -> None:
    """The real lab router / Home Assistant / Wi-Fi password must never be baked into a file of this repository.

    The strings are written in pieces so that this file does not contain them either."""
    pieces = (
        ("192.168.2.", "45"), ("192.168.2.", "34"), ("192.168.2.", "49"), (".config/glinet-", "router"),
        ("good", "life"),  # the lab router's Wi-Fi password
        ("94:83:c4:62:", "28:f2"), ("d2:98:", "85:a0:de:4b"),  # its WAN MAC and one of its BSSIDs
    )  # fmt: skip
    forbidden = tuple("".join(parts) for parts in pieces)
    skip_dirs = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv"}
    suffixes = {".py", ".js", ".mjs", ".ts", ".html", ".json", ".md", ".yml", ".yaml", ".txt", ".cfg", ".toml", ".sh"}
    here = Path(__file__).resolve()
    checked = 0
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith("venv")]
        for name in names:
            path = Path(folder) / name
            if path == here or path.suffix not in suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            assert not [f for f in forbidden if f in text], f"{path.relative_to(ROOT)} mentions the real lab"
            checked += 1
    assert checked > 50, "the walk found hardly any file: is ROOT right?"


# ===================================================================================== CI
def test_the_ci_workflow() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True))  # (YAML 1.1 reads a bare `on` as True)
    assert {"push", "pull_request"} <= set(triggers)
    jobs = workflow["jobs"]
    assert {"hassfest", "hacs", "tests"} <= set(jobs)
    assert any(step.get("uses", "").startswith("home-assistant/actions/hassfest") for step in jobs["hassfest"]["steps"])
    assert any(step.get("uses", "").startswith("hacs/action") for step in jobs["hacs"]["steps"])
    steps = jobs["tests"]["steps"]
    assert any(step.get("with", {}).get("python-version") == "3.14" for step in steps), "Home Assistant 2026.10 needs Python 3.14"
    runs = " ".join(step.get("run", "") for step in steps)
    assert "tests/requirements_test.txt" in runs and "pytest" in runs


def test_the_test_requirements_pin_what_the_suite_was_written_against() -> None:
    lines = [l.strip() for l in (ROOT / "tests" / "requirements_test.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    pins = dict(l.split("==") for l in lines)
    assert set(pins) == {"pytest-homeassistant-custom-component", "passlib"}
    import homeassistant.const as ha_const
    from importlib.metadata import version

    assert version("pytest-homeassistant-custom-component") == pins["pytest-homeassistant-custom-component"]
    assert version("passlib") == pins["passlib"]
    assert ha_const.__version__.startswith("2026.10.")
