"""Turns the sites in sites.yaml into tools and runs them over HTTP.

The same tool list is served two ways: to Claude apps over MCP (owner, all tools)
and to the on-site chat widget (visitors, only tools marked `widget: true`).
"""
from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from .config import SiteSpec, ToolSpec

MAX_RESULT_CHARS = 20_000
FETCH_PAGE = "fetch_page"


class ToolFailure(Exception):
    """A tool error Claude should see (bad input, 4xx/5xx from the site)."""


@dataclass
class Tool:
    full_name: str  # e.g. planit__list_assessments
    site: SiteSpec
    spec: ToolSpec

    def definition(self) -> dict:
        prefix = f"[{self.site.name}] "
        return {"name": self.full_name, "description": prefix + self.spec.description,
                "input_schema": self.spec.input_schema()}


def _fetch_spec(site: SiteSpec) -> ToolSpec:
    return ToolSpec(
        name=FETCH_PAGE,
        description=(f"Read a page of {site.base_url} as plain text. `path` is the part after the domain, "
                     "e.g. `/` or `/about`. Read-only."),
        method="GET", path="{path}",
        params={"path": {"type": "string", "description": "Page path starting with /"}},
        required=["path"], widget=True,
    )


def build_tools(sites: dict[str, SiteSpec], audience: str, site_key: str | None = None) -> dict[str, Tool]:
    """audience='mcp' → every tool; audience='widget' → only visitor-safe, read-only tools."""
    tools: dict[str, Tool] = {}
    for key, site in sites.items():
        if site_key and key != site_key:
            continue
        specs = list(site.tools) + ([_fetch_spec(site)] if site.fetch_pages else [])
        for spec in specs:
            if audience == "widget" and (not spec.widget or spec.writes):
                continue
            name = f"{key}__{spec.name}"
            tools[name] = Tool(name, site, spec)
    return tools


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article)>", "\n", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _clip(text: str) -> str:
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[:MAX_RESULT_CHARS] + f"\n…[{len(text) - MAX_RESULT_CHARS} символ қысқартылды]"


class SiteClient:
    """One HTTP client per site; handles login and token refresh."""

    def __init__(self, site: SiteSpec, transport: httpx.AsyncBaseTransport | None = None):
        self.site = site
        self._token: str | None = None
        self._lock = asyncio.Lock()
        self.http = httpx.AsyncClient(base_url=site.base_url, timeout=30, follow_redirects=False,
                                      transport=transport, headers={"User-Agent": "imarlen-claude/0.1"})

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _login(self) -> str:
        a = self.site.auth
        resp = await self.http.post(a.get("url", "/api/auth/login"),
                                    json={a.get("user_field", "email"): a.get("email", ""),
                                          a.get("password_field", "password"): a.get("password", "")})
        if resp.status_code != 200:
            raise ToolFailure(f"{self.site.name}: бот аккаунтымен кіру сәтсіз ({resp.status_code})")
        token = resp.json().get(a.get("token_field", "access_token"))
        if not token:
            raise ToolFailure(f"{self.site.name}: кіру жауабында токен жоқ")
        return token

    async def _auth_headers(self, fresh: bool = False) -> dict[str, str]:
        a = self.site.auth
        kind = a.get("type", "none")
        if kind == "bearer":
            return {"Authorization": f"Bearer {a.get('token', '')}"}
        if kind == "header":
            return {a["name"]: a.get("value", "")}
        if kind == "login":
            async with self._lock:
                if fresh or not self._token:
                    self._token = await self._login()
                return {"Authorization": f"Bearer {self._token}"}
        return {}

    def _build(self, spec: ToolSpec, args: dict[str, Any]) -> tuple[str, dict, Any]:
        args = dict(args or {})
        unknown = set(args) - set(spec.params)
        if unknown:
            raise ToolFailure(f"Белгісіз параметр: {', '.join(sorted(unknown))}")
        missing = [r for r in spec.required if args.get(r) in (None, "")]
        if missing:
            raise ToolFailure(f"Міндетті параметр жоқ: {', '.join(missing)}")

        if spec.name == FETCH_PAGE and spec.path == "{path}":
            path = str(args.pop("path"))
            if not path.startswith("/") or path.startswith("//") or "\\" in path:
                raise ToolFailure("path '/' белгісінен басталуы керек")
            url = urljoin(self.site.base_url + "/", path.lstrip("/"))
            if urlparse(url).netloc != self.site.host:
                raise ToolFailure("Тек осы сайттың беттерін оқуға болады")
            return url, {}, None

        def sub(m: re.Match) -> str:
            return quote(str(args.pop(m.group(1))), safe="")

        url = re.sub(r"\{(\w+)\}", sub, spec.path)
        clean = {k: v for k, v in args.items() if v is not None}
        if spec.method in ("GET", "DELETE"):
            return url, clean, None
        return url, {}, clean

    async def call(self, spec: ToolSpec, args: dict[str, Any]) -> str:
        url, query, body = self._build(spec, args)
        resp = None
        for attempt in (0, 1):
            headers = await self._auth_headers(fresh=attempt == 1)
            resp = await self.http.request(spec.method, url, params=query or None, json=body, headers=headers)
            if resp.status_code == 401 and self.site.auth.get("type") == "login" and attempt == 0:
                continue
            break
        assert resp is not None
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            try:
                text = json.dumps(resp.json(), ensure_ascii=False, indent=1)
            except ValueError:
                text = resp.text
        elif "html" in ctype:
            text = html_to_text(resp.text)
        elif ctype.startswith("text/") or not ctype:
            text = resp.text
        else:
            text = f"[{ctype} файл, {len(resp.content)} байт — мәтін емес]"
        if resp.status_code >= 400:
            raise ToolFailure(f"HTTP {resp.status_code}: {_clip(text)[:2000]}")
        if 300 <= resp.status_code < 400:
            return f"HTTP {resp.status_code} → {resp.headers.get('location', '')}"
        return _clip(text)


class Registry:
    """Holds one SiteClient per site and dispatches tool calls."""

    def __init__(self, sites: dict[str, SiteSpec], transport: httpx.AsyncBaseTransport | None = None):
        self.sites = sites
        self.clients = {k: SiteClient(s, transport) for k, s in sites.items()}

    async def aclose(self) -> None:
        await asyncio.gather(*(c.aclose() for c in self.clients.values()))

    async def run(self, tool: Tool, args: dict[str, Any]) -> tuple[str, bool]:
        """Returns (text, is_error). Never raises for site/input errors."""
        try:
            return await self.clients[tool.site.key].call(tool.spec, args), False
        except ToolFailure as e:
            return str(e), True
        except httpx.HTTPError as e:
            return f"{tool.site.name} қолжетімсіз: {type(e).__name__}", True
