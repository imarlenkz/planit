"""Loads sites.yaml: which sites Claude can reach, how to log in, which tools exist.

`${VAR}` and `${VAR:-default}` inside the YAML are replaced from the environment,
so secrets live in .env, never in the YAML file.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

_ENV = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")
TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return _ENV.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


@dataclass
class ToolSpec:
    name: str
    description: str
    method: str = "GET"
    path: str = "/"
    params: dict[str, dict] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    widget: bool = False  # may site visitors (the chat widget) use it?

    @property
    def writes(self) -> bool:
        return self.method != "GET"

    def input_schema(self) -> dict:
        props = {}
        for pname, p in self.params.items():
            prop = {"type": p.get("type", "string")}
            for key in ("description", "enum", "minimum", "maximum"):
                if key in p:
                    prop[key] = p[key]
            props[pname] = prop
        return {"type": "object", "properties": props, "required": list(self.required),
                "additionalProperties": False}


@dataclass
class WidgetSpec:
    enabled: bool = False
    origins: list[str] = field(default_factory=list)
    title: str = "Көмекші"
    greeting: str = "Сәлеметсіз бе! Сізге қалай көмектесе аламын?"
    system_prompt: str = ""
    color: str = "#2f9e6e"


@dataclass
class SiteSpec:
    key: str
    name: str
    base_url: str
    description: str = ""
    auth: dict = field(default_factory=lambda: {"type": "none"})
    tools: list[ToolSpec] = field(default_factory=list)
    widget: WidgetSpec = field(default_factory=WidgetSpec)
    fetch_pages: bool = True  # built-in read-only page reader for this site

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc


@dataclass
class Settings:
    sites: dict[str, SiteSpec]
    model: str
    effort: str
    max_tokens: int
    fallbacks: str
    mcp_tokens: list[str]
    public_host: str


def _tool(site_key: str, raw: dict) -> ToolSpec:
    name = raw["name"]
    if not TOOL_NAME.match(name):
        raise ValueError(f"{site_key}: tool name {name!r} must be lower_snake_case")
    method = raw.get("method", "GET").upper()
    if method not in METHODS:
        raise ValueError(f"{site_key}.{name}: bad method {method}")
    path = raw.get("path", "/")
    if not path.startswith("/"):
        raise ValueError(f"{site_key}.{name}: path must start with /")
    params = raw.get("params") or {}
    for placeholder in re.findall(r"\{(\w+)\}", path):
        params.setdefault(placeholder, {"type": "string"})
    required = list(raw.get("required") or [])
    for placeholder in re.findall(r"\{(\w+)\}", path):
        if placeholder not in required:
            required.append(placeholder)
    return ToolSpec(name=name, description=raw.get("description", name), method=method, path=path,
                    params=params, required=required, widget=bool(raw.get("widget", False)))


def load_sites(path: str | Path) -> dict[str, SiteSpec]:
    data = _expand(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    sites: dict[str, SiteSpec] = {}
    for key, raw in (data.get("sites") or {}).items():
        if not TOOL_NAME.match(key):
            raise ValueError(f"site key {key!r} must be lower_snake_case")
        base = raw["base_url"].rstrip("/")
        if urlparse(base).scheme not in ("http", "https"):
            raise ValueError(f"{key}: base_url must be http(s)")
        w = raw.get("widget") or {}
        sites[key] = SiteSpec(
            key=key, name=raw.get("name", key), base_url=base, description=raw.get("description", ""),
            auth=raw.get("auth") or {"type": "none"},
            tools=[_tool(key, t) for t in raw.get("tools") or []],
            widget=WidgetSpec(**{k: v for k, v in w.items() if k in WidgetSpec.__dataclass_fields__}),
            fetch_pages=raw.get("fetch_pages", True),
        )
    return sites


def load_settings() -> Settings:
    tokens = [t.strip() for t in os.environ.get("MCP_TOKENS", "").split(",") if t.strip()]
    return Settings(
        sites=load_sites(os.environ.get("SITES_FILE", "sites.yaml")),
        model=os.environ.get("CLAUDE_MODEL", "claude-opus-5-5"),
        effort=os.environ.get("CLAUDE_EFFORT", "medium"),
        max_tokens=int(os.environ.get("CLAUDE_MAX_TOKENS", "16000")),
        fallbacks=os.environ.get("CLAUDE_FALLBACKS", "default"),
        mcp_tokens=tokens,
        public_host=os.environ.get("PUBLIC_HOST", "ai.imarlen.kz"),
    )
