"""Tests for GeminiClient (llm_client).

The real `google.genai` package and the Gemini API are never used: a fake
`google.genai` module is injected into sys.modules before import, and the
underlying model client is replaced with a stub that returns canned text.
"""

import sys
import types

import pytest


# ── Inject a fake `google.genai` module so llm_client imports cleanly ─────────

class _FakeModels:
    """Captures the last call and returns a preset response object."""

    def __init__(self):
        self.response_text = ""
        self.raise_exc = None
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        if self.raise_exc is not None:
            raise self.raise_exc
        return types.SimpleNamespace(text=self.response_text)


class _FakeClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.models = _FakeModels()


def _install_fake_genai():
    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = _FakeClient
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.genai = fake_genai
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = fake_genai


_install_fake_genai()

# Import only after the fake module is in place.
from llm_client import GeminiClient  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return GeminiClient()


# ── Construction / configuration ─────────────────────────────────────────────

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        GeminiClient()


def test_api_key_passed_to_client(client):
    assert client.client.api_key == "test-key"


# ── answer_from_snippets ─────────────────────────────────────────────────────

def test_answer_from_snippets_refuses_when_empty(client):
    assert client.answer_from_snippets("q", []) == "I do not know based on the docs I have."


def test_answer_from_snippets_returns_model_text(client):
    client.client.models.response_text = "Bella needs a walk."
    snippets = [("pet_Bella.txt", "Pet profile: Bella")]
    assert client.answer_from_snippets("What about Bella?", snippets) == "Bella needs a walk."


def test_answer_from_snippets_prompt_includes_snippets(client):
    client.client.models.response_text = "ok"
    client.answer_from_snippets("query text", [("f.txt", "SNIPPET_CONTENT")])
    prompt = client.client.models.last_kwargs["contents"]
    assert "SNIPPET_CONTENT" in prompt
    assert "f.txt" in prompt
    assert "query text" in prompt


def test_answer_from_snippets_handles_api_error(client):
    client.client.models.raise_exc = ValueError("boom")
    result = client.answer_from_snippets("q", [("f.txt", "text")])
    assert result.startswith("API error")


# ── naive_answer_over_full_docs ──────────────────────────────────────────────

def test_naive_answer_returns_model_text(client):
    client.client.models.response_text = "  a generic answer  "
    assert client.naive_answer_over_full_docs("q", "ignored") == "a generic answer"


def test_naive_answer_handles_api_error(client):
    client.client.models.raise_exc = RuntimeError("down")
    result = client.naive_answer_over_full_docs("q", "docs")
    assert result.startswith("Unable to generate an answer")


# ── suggest_task ─────────────────────────────────────────────────────────────

def test_suggest_task_parses_json(client):
    client.client.models.response_text = (
        '{"title": "Vet", "description": "checkup", "date": "2026-04-01", '
        '"time": "14:30", "priority": 5, "recurrence": "weekly"}'
    )
    result = client.suggest_task("plan a vet visit", [])
    assert result["title"] == "Vet"
    assert result["priority"] == 5


def test_suggest_task_returns_none_on_api_error(client):
    client.client.models.raise_exc = ValueError("boom")
    assert client.suggest_task("q", []) is None


# ── _parse_json_object (static helper) ───────────────────────────────────────

def test_parse_json_plain_object():
    result = GeminiClient._parse_json_object('{"a": 1, "b": "two"}')
    assert result == {"a": 1, "b": "two"}


def test_parse_json_strips_markdown_fences():
    text = '```json\n{"title": "Walk"}\n```'
    assert GeminiClient._parse_json_object(text) == {"title": "Walk"}


def test_parse_json_extracts_object_amid_prose():
    text = 'Sure! Here is the task: {"title": "Feed"} Hope that helps.'
    assert GeminiClient._parse_json_object(text) == {"title": "Feed"}


def test_parse_json_returns_none_when_no_object():
    assert GeminiClient._parse_json_object("no json here") is None


def test_parse_json_returns_none_on_invalid_json():
    assert GeminiClient._parse_json_object('{"a": }') is None


def test_parse_json_handles_empty_string():
    assert GeminiClient._parse_json_object("") is None
