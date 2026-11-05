"""ASGI entry point.

  /mcp                 MCP endpoint for Claude apps (Bearer token, or /mcp/<token> for claude.ai)
  /v1/chat             streaming chat for the on-site widget (SSE)
  /v1/sites/{key}      public widget settings
  /widget.js           the embeddable widget
  /health              liveness
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from .chat import BadRequest, RateLimiter, run_chat, validate_messages
from .config import Settings, load_settings
from .connectors import Registry, build_tools
from .mcp_app import create_mcp_server, mcp_starlette

WIDGET_JS = Path(__file__).resolve().parent.parent / "widget" / "widget.js"


def _token_ok(given: str, tokens: list[str]) -> bool:
    return any(hmac.compare_digest(given.encode(), t.encode()) for t in tokens)


def create_app(settings: Settings | None = None, *, transport: httpx.AsyncBaseTransport | None = None,
               claude: anthropic.AsyncAnthropic | None = None):
    settings = settings or load_settings()
    registry = Registry(settings.sites, transport)
    mcp_server = create_mcp_server(registry)
    mcp_app = mcp_starlette(mcp_server, settings.public_host)
    limiter = RateLimiter(int(os.environ.get("CHAT_PER_MINUTE", "10")), int(os.environ.get("CHAT_PER_DAY", "200")))
    trust_proxy = os.environ.get("TRUST_PROXY", "true").lower() == "true"
    all_origins = {o.rstrip("/") for s in settings.sites.values() if s.widget.enabled for o in s.widget.origins}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _app.state.claude = claude or anthropic.AsyncAnthropic()
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
        await registry.aclose()

    api = FastAPI(title="iMARLEN Claude", docs_url=None, redoc_url=None, lifespan=lifespan)

    def cors(origin: str | None, resp: Response) -> Response:
        if origin and origin.rstrip("/") in all_origins:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @api.get("/health")
    async def health():
        return {"ok": True, "sites": sorted(settings.sites), "model": settings.model}

    @api.get("/widget.js")
    async def widget_js():
        return FileResponse(WIDGET_JS, media_type="application/javascript; charset=utf-8",
                            headers={"Cache-Control": "public, max-age=300"})

    @api.get("/v1/sites/{key}")
    async def site_info(key: str, request: Request):
        site = settings.sites.get(key)
        if not site or not site.widget.enabled:
            raise HTTPException(404, "Сайт табылмады")
        w = site.widget
        return cors(request.headers.get("origin"), JSONResponse(
            {"site": key, "name": site.name, "title": w.title, "greeting": w.greeting, "color": w.color}))

    @api.options("/v1/{rest:path}")
    async def preflight(rest: str, request: Request):
        return cors(request.headers.get("origin"), Response(status_code=204))

    @api.post("/v1/chat")
    async def chat(request: Request):
        origin = request.headers.get("origin")
        try:
            body = await request.json()
        except ValueError:
            return cors(origin, JSONResponse({"detail": "JSON қате"}, status_code=400))
        site = settings.sites.get(str(body.get("site", ""))) if isinstance(body, dict) else None
        if not site or not site.widget.enabled:
            return cors(origin, JSONResponse({"detail": "Сайт табылмады"}, status_code=404))
        allowed = {o.rstrip("/") for o in site.widget.origins}
        if not origin or origin.rstrip("/") not in allowed:
            return JSONResponse({"detail": "Бұл сайттан рұқсат жоқ"}, status_code=403)
        try:
            messages = validate_messages(body.get("messages"))
        except BadRequest as e:
            return cors(origin, JSONResponse({"detail": str(e)}, status_code=400))
        ip = (request.headers.get("x-real-ip") if trust_proxy else None) or (
            request.client.host if request.client else "?")
        if not limiter.allow(f"{site.key}:{ip}"):
            return cors(origin, JSONResponse({"detail": "Тым көп сұрау, сәл күтіңіз"}, status_code=429))
        stream = run_chat(request.app.state.claude, settings, registry, site, messages)
        resp = StreamingResponse(stream, media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        return cors(origin, resp)

    @api.get("/v1/tools")
    async def tools_list(request: Request):
        """Owner-only list of tools (same token as MCP) — handy for checking sites.yaml."""
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer ") or not _token_ok(auth[7:].strip(), settings.mcp_tokens):
            raise HTTPException(401, "Token қажет")
        return [{"name": tl.full_name, "writes": tl.spec.writes, "widget": tl.spec.widget}
                for tl in build_tools(settings.sites, "mcp").values()]

    async def app(scope, receive, send):
        path = scope.get("path", "") if scope["type"] in ("http", "websocket") else ""
        if path == "/mcp" or path.startswith("/mcp/"):
            token = ""
            if path.startswith("/mcp/"):
                token = path[len("/mcp/"):].strip("/")
                scope = dict(scope, path="/mcp", raw_path=b"/mcp")
            else:
                for k, v in scope.get("headers", []):
                    if k == b"authorization" and v[:7].lower() == b"bearer ":
                        token = v[7:].decode(errors="ignore").strip()
            if not settings.mcp_tokens or not _token_ok(token, settings.mcp_tokens):
                resp = JSONResponse({"detail": "MCP token қате"}, status_code=401,
                                    headers={"WWW-Authenticate": "Bearer"})
                await resp(scope, receive, send)
                return
            await mcp_app(scope, receive, send)
            return
        await api(scope, receive, send)

    app.api = api  # type: ignore[attr-defined]
    return app
# Run with: uvicorn --factory app.main:create_app
