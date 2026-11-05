import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from app.chat import RateLimiter, BadRequest, validate_messages
from app.config import Settings, load_sites
from app.connectors import Registry, build_tools, html_to_text
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "test-token-123"
ORIGIN = "https://checker.imarlen.kz"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": "2025-06-18"}


def fake_site(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/auth/login":
        body = json.loads(request.content)
        if body == {"email": "bot@planit.kz", "password": "pw"}:
            return httpx.Response(200, json={"access_token": "jwt-1"})
        return httpx.Response(401)
    if request.headers.get("authorization") != "Bearer jwt-1" and request.url.path.startswith("/api/"):
        return httpx.Response(401, json={"detail": "no"})
    if request.url.path == "/api/assessments":
        return httpx.Response(200, json={"items": [{"id": 7, "title": "БЖБ 1"}], "q": request.url.params.get("q")})
    if request.url.path.startswith("/api/assessments/") and request.method == "POST":
        return httpx.Response(200, json={"approved": 3})
    if request.url.path == "/about":
        return httpx.Response(200, text="<html><script>x()</script><h1>Planit</h1><p>Сәлем</p></html>",
                              headers={"content-type": "text/html"})
    return httpx.Response(404, text="not found")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("PLANIT_BOT_EMAIL", "bot@planit.kz")
    monkeypatch.setenv("PLANIT_BOT_PASSWORD", "pw")


def settings() -> Settings:
    return Settings(sites=load_sites(ROOT / "sites.example.yaml"), model="claude-opus-5-5", effort="medium",
                    max_tokens=4000, fallbacks="default", mcp_tokens=[TOKEN], public_host="ai.imarlen.kz")


# ---------- config / connectors ----------

def test_example_config_loads_and_expands_env():
    sites = load_sites(ROOT / "sites.example.yaml")
    assert "planit" in sites and sites["planit"].auth["email"] == "bot@planit.kz"
    tool = next(t for t in sites["planit"].tools if t.name == "get_assessment")
    assert tool.required == ["assessment_id"]


def test_widget_gets_only_read_only_visitor_tools():
    sites = load_sites(ROOT / "sites.example.yaml")
    widget = build_tools(sites, "widget", "planit")
    assert set(widget) == {"planit__fetch_page"}
    mcp = build_tools(sites, "mcp")
    assert "planit__approve_confident" in mcp and mcp["planit__approve_confident"].spec.writes


def test_html_to_text_drops_scripts():
    assert html_to_text("<script>bad()</script><p>a</p><p>b</p>") == "a\nb"


@pytest.mark.anyio
async def test_login_query_and_path_params():
    sites = load_sites(ROOT / "sites.example.yaml")
    reg = Registry(sites, httpx.MockTransport(fake_site))
    tools = build_tools(sites, "mcp")
    text, err = await reg.run(tools["planit__list_assessments"], {"q": "алгебра"})
    assert not err and "БЖБ 1" in text and "алгебра" in text
    text, err = await reg.run(tools["planit__approve_confident"], {"assessment_id": 7})
    assert not err and "approved" in text
    await reg.aclose()


@pytest.mark.anyio
async def test_bad_inputs_are_tool_errors():
    sites = load_sites(ROOT / "sites.example.yaml")
    reg = Registry(sites, httpx.MockTransport(fake_site))
    tools = build_tools(sites, "mcp")
    _, err = await reg.run(tools["planit__get_assessment"], {})
    assert err
    _, err = await reg.run(tools["planit__list_assessments"], {"evil": 1})
    assert err
    for path in ("https://evil.com/", "//evil.com/x", "about"):
        text, err = await reg.run(tools["planit__fetch_page"], {"path": path})
        assert err, path
    text, err = await reg.run(tools["planit__fetch_page"], {"path": "/about"})
    assert not err and "Planit" in text and "x()" not in text
    await reg.aclose()


def test_path_param_is_url_encoded():
    from app.connectors import SiteClient
    sites = load_sites(ROOT / "sites.example.yaml")
    c = SiteClient(sites["planit"])
    spec = next(t for t in sites["planit"].tools if t.name == "get_assessment")
    url, _, _ = c._build(spec, {"assessment_id": "../../admin"})
    assert url == "/api/assessments/..%2F..%2Fadmin"


def test_validate_messages():
    assert validate_messages([{"role": "user", "content": "hi"}])
    for bad in ([], [{"role": "assistant", "content": "x"}], [{"role": "user", "content": "x" * 5000}],
                [{"role": "system", "content": "x"}]):
        with pytest.raises(BadRequest):
            validate_messages(bad)


def test_rate_limiter():
    rl = RateLimiter(2, 3)
    assert rl.allow("a", 0) and rl.allow("a", 1) and not rl.allow("a", 2)
    assert rl.allow("a", 100) and not rl.allow("a", 200)  # daily cap
    assert rl.allow("b", 0)


# ---------- HTTP app ----------

class FakeStream:
    def __init__(self, message):
        self.message = message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def gen():
            for b in self.message.content:
                if b.type == "text":
                    yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=b.text))
        return gen()

    async def get_final_message(self):
        return self.message


class FakeClaude:
    """Round 1 calls fetch_page, round 2 answers."""

    def __init__(self):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def stream(self, **kw):
        self.calls.append(dict(kw, messages=list(kw["messages"])))
        if len(self.calls) == 1:
            block = SimpleNamespace(type="tool_use", id="tu1", name="planit__fetch_page", input={"path": "/about"})
            return FakeStream(SimpleNamespace(stop_reason="tool_use", content=[block]))
        return FakeStream(SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Planit — тексеру")]))


@pytest.fixture
def client():
    fake = FakeClaude()
    app = create_app(settings(), transport=httpx.MockTransport(fake_site), claude=fake)
    with TestClient(app, base_url="http://ai.imarlen.kz") as c:
        c.fake = fake
        yield c


def test_health_and_widget(client):
    assert client.get("/health").json()["ok"]
    assert "imarlen-claude" in client.get("/widget.js").text
    r = client.get("/v1/sites/planit", headers={"Origin": ORIGIN})
    assert r.json()["title"] == "Planit көмекшісі"
    assert r.headers["access-control-allow-origin"] == ORIGIN
    assert client.get("/v1/sites/iid").status_code == 404  # widget disabled


def test_chat_streams_and_runs_tool(client):
    r = client.post("/v1/chat", headers={"Origin": ORIGIN},
                    json={"site": "planit", "messages": [{"role": "user", "content": "Planit деген не?"}]})
    assert r.status_code == 200, r.text
    assert "event: tool" in r.text and "Planit — тексеру" in r.text and "event: done" in r.text
    first, second = client.fake.calls
    assert first["model"] == "claude-opus-5-5" and first["fallbacks"] == "default"
    assert [t["name"] for t in first["tools"]] == ["planit__fetch_page"]
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "tu1" and "Сәлем" in tool_result["content"]


def test_chat_rejects_foreign_origin(client):
    body = {"site": "planit", "messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/v1/chat", json=body, headers={"Origin": "https://evil.com"}).status_code == 403
    assert client.post("/v1/chat", json=body).status_code == 403


def test_mcp_requires_token(client):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    assert client.post("/mcp", json=msg, headers=MCP_HEADERS).status_code == 401
    bad = dict(MCP_HEADERS, Authorization="Bearer nope")
    assert client.post("/mcp", json=msg, headers=bad).status_code == 401
    assert client.post("/mcp/nope", json=msg, headers=MCP_HEADERS).status_code == 401


def _rpc(client, path, method, params, headers):
    init = {"jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}}}
    client.post(path, json=init, headers=headers)
    r = client.post(path, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["result"]


@pytest.mark.parametrize("path,extra", [("/mcp", {"Authorization": f"Bearer {TOKEN}"}), (f"/mcp/{TOKEN}", {})])
def test_mcp_lists_and_calls_tools(client, path, extra):
    h = dict(MCP_HEADERS, **extra)
    tools = _rpc(client, path, "tools/list", {}, h)["tools"]
    names = {t["name"] for t in tools}
    assert {"planit__list_assessments", "planit__fetch_page", "ustaz__fetch_page"} <= names
    approve = next(t for t in tools if t["name"] == "planit__approve_confident")
    assert approve["annotations"]["destructiveHint"] is True
    res = _rpc(client, path, "tools/call", {"name": "planit__list_assessments", "arguments": {"q": "x"}}, h)
    assert not res.get("isError") and "БЖБ 1" in res["content"][0]["text"]


@pytest.fixture
def anyio_backend():
    return "asyncio"
