"""Tests hors-ligne : faux client Claude + faux CoinGecko."""

from __future__ import annotations

import os

import httpx
import pytest
from anthropic.types.beta import BetaMessage

os.environ.setdefault("AGENT_TOKEN", "t" * 32)

from agent.config import load_settings  # noqa: E402
from agent.core import Agent  # noqa: E402
from agent.storage import JsonStore  # noqa: E402
from agent.tools import ToolContext, run_tool  # noqa: E402


def msg(content: list[dict], stop: str) -> BetaMessage:
    return BetaMessage.model_validate({
        "id": "msg_x", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    })


class FakeMessages:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.replies.pop(0)


class FakeClient:
    def __init__(self, replies):
        self.beta = type("B", (), {})()
        self.beta.messages = FakeMessages(replies)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_DATA_DIR", str(tmp_path))
    return load_settings()


def test_tool_loop_then_answer(settings):
    client = FakeClient([
        msg([{"type": "tool_use", "id": "tu1", "name": "note_ajouter", "input": {"texte": "acheter du pain"}}],
            "tool_use"),
        msg([{"type": "text", "text": "C'est noté."}], "end_turn"),
    ])
    agent = Agent(settings, client=client)
    reply = agent.ask("note: acheter du pain")

    assert reply.text == "C'est noté."
    assert agent.store.list_items("notes")[0]["texte"] == "acheter du pain"
    second = client.beta.messages.calls[1]
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "tu1" and tool_result["is_error"] is False
    assert second["fallbacks"] == "default"
    assert second["output_config"] == {"effort": "low"}

    # L'historique est conservé pour la requête suivante.
    client.beta.messages.replies.append(msg([{"type": "text", "text": "Oui."}], "end_turn"))
    agent.ask("tu as bien noté ?")
    assert len(client.beta.messages.calls[2]["messages"]) == 5


def test_iphone_action_returned(settings):
    client = FakeClient([
        msg([{"type": "tool_use", "id": "a", "name": "action_iphone",
              "input": {"type": "rappel", "texte": "Appeler maman", "date": "2026-11-06T09:00"}}], "tool_use"),
        msg([{"type": "text", "text": "Rappel créé pour demain 9 h."}], "end_turn"),
    ])
    reply = Agent(settings, client=client).ask("rappelle-moi d'appeler maman demain à 9h")
    assert reply.iphone_action == {"type": "rappel", "texte": "Appeler maman", "url": "", "date": "2026-11-06T09:00"}


def test_refusal_not_saved(settings):
    client = FakeClient([msg([], "refusal")])
    agent = Agent(settings, client=client)
    reply = agent.ask("...")
    assert reply.stop_reason == "refusal"
    assert agent.store.load_session("iphone", 6) == []


def test_unknown_tool_and_bad_args(settings):
    ctx = ToolContext(JsonStore(settings.data_dir), "Europe/Paris")
    assert run_tool(ctx, "nope", {}) == ("Outil inconnu : nope", True)
    content, err = run_tool(ctx, "action_iphone", {"type": "ouvrir_url", "url": "javascript:x"})
    assert err and "URL" in content


def test_prix_crypto(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["ids"] == "bitcoin,ethereum"
        return httpx.Response(200, json={"bitcoin": {"eur": 60000, "eur_24h_change": 1.2}})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    ctx = ToolContext(JsonStore(settings.data_dir), "Europe/Paris", http=http)
    content, err = run_tool(ctx, "prix_crypto", {"ids": ["Bitcoin", "ethereum"]})
    assert not err and "60000" in content


def test_server_auth(settings):
    from fastapi.testclient import TestClient

    from agent import server

    server._agent = Agent(settings, client=FakeClient([msg([{"type": "text", "text": "Salut !"}], "end_turn")]))
    c = TestClient(server.app)
    assert c.post("/ask", json={"text": "salut"}).status_code == 401
    r = c.post("/ask", json={"text": "salut"}, headers={"Authorization": "Bearer " + "t" * 32})
    assert r.status_code == 200
    assert r.json() == {"reply": "Salut !", "action_type": "aucune", "action_texte": "",
                        "action_url": "", "action_date": ""}
