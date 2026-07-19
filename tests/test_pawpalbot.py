"""Tests for PawPalBot: indexing, retrieval, evidence guardrails, and RAG wiring.

The LLM is replaced with a FakeLLM so no network calls are made.
"""

from datetime import datetime

import pytest

from pawpal_system import Owner, Pet, Scheduler
from pawpalbot import PawPalBot


class FakeLLM:
    """Records calls and returns canned responses in place of GeminiClient."""

    def __init__(self, answer="canned answer", suggestion=None):
        self._answer = answer
        self._suggestion = suggestion
        self.answer_calls = []
        self.suggest_calls = []

    def answer_from_snippets(self, query, snippets):
        self.answer_calls.append((query, snippets))
        return self._answer

    def suggest_task(self, query, snippets):
        self.suggest_calls.append((query, snippets))
        return self._suggestion


def make_bot(llm_client=None):
    """Bot backed by one owner (Bella the dog) and a walk task, no docs folder."""
    owner = Owner(name="Alex")
    bella = Pet(name="Bella", species="dog")
    owner.add_pet(bella)

    sched = Scheduler()
    sched.create_task(
        title="Morning Walk",
        scheduled_at=datetime(2026, 3, 15, 9, 0),
        pet_ids=[bella.id],
    )

    bot = PawPalBot(
        docs_folder="__no_such_folder__",  # forces docs/ to be empty
        owners=[owner],
        scheduler=sched,
        llm_client=llm_client,
    )
    return bot


# ── Indexing & tokenization ──────────────────────────────────────────────────

def test_tokenize_lowercases_and_splits():
    bot = make_bot()
    assert bot._tokenize("Hello, World!") == ["hello", "world"]


def test_query_tokens_strips_stopwords():
    bot = make_bot()
    tokens = bot._query_tokens("what is the walk for the dog")
    assert "walk" in tokens and "dog" in tokens
    assert "the" not in tokens and "is" not in tokens


def test_index_is_built_from_live_data():
    bot = make_bot()
    # "bella" appears in the generated pet/task documents.
    assert "bella" in bot.index
    assert len(bot.paragraphs) > 0


# ── Scoring & retrieval ──────────────────────────────────────────────────────

def test_score_document_counts_matching_terms():
    bot = make_bot()
    score = bot.score_document("morning walk", "The morning walk was pleasant")
    assert score == 2


def test_retrieve_returns_relevant_snippets():
    bot = make_bot()
    results = bot.retrieve("Bella", top_k=3)
    assert results  # non-empty
    assert all(isinstance(f, str) and isinstance(t, str) for f, t in results)
    assert any("Bella" in text for _, text in results)


def test_retrieve_respects_top_k():
    bot = make_bot()
    results = bot.retrieve("Bella dog walk", top_k=1)
    assert len(results) <= 1


def test_retrieve_empty_query_returns_nothing():
    bot = make_bot()
    assert bot.retrieve("") == []


def test_retrieve_with_scores_sorted_descending():
    bot = make_bot()
    scored = bot.retrieve_with_scores("Bella dog walk", top_k=5)
    scores = [s for s, _, _ in scored]
    assert scores == sorted(scores, reverse=True)


def test_retrieve_no_match_returns_empty():
    bot = make_bot()
    assert bot.retrieve_with_scores("xyzzy_nonexistent_term") == []


# ── Evidence guardrail ───────────────────────────────────────────────────────

def test_has_meaningful_evidence_false_when_empty():
    bot = make_bot()
    assert bot.has_meaningful_evidence("Bella", []) is False


def test_has_meaningful_evidence_true_with_strong_match():
    bot = make_bot()
    scored = bot.retrieve_with_scores("Bella dog", top_k=3)
    assert bot.has_meaningful_evidence("Bella dog", scored) is True


# ── Retrieval-only answering ─────────────────────────────────────────────────

def test_answer_retrieval_only_refuses_without_evidence():
    bot = make_bot()
    answer = bot.answer_retrieval_only("xyzzy_nonexistent_term")
    assert answer == "I do not know based on these docs."


def test_answer_retrieval_only_returns_formatted_snippets():
    bot = make_bot()
    answer = bot.answer_retrieval_only("Bella dog")
    assert "Bella" in answer
    assert "[" in answer  # filename header formatting


# ── RAG answering (with fake LLM) ────────────────────────────────────────────

def test_answer_rag_requires_llm_client():
    bot = make_bot(llm_client=None)
    with pytest.raises(RuntimeError):
        bot.answer_rag("Bella")


def test_answer_rag_calls_llm_with_snippets():
    llm = FakeLLM(answer="Bella needs a walk.")
    bot = make_bot(llm_client=llm)

    answer = bot.answer_rag("Bella dog")

    assert answer == "Bella needs a walk."
    assert len(llm.answer_calls) == 1
    query, snippets = llm.answer_calls[0]
    assert query == "Bella dog"
    assert snippets  # snippets were passed through


def test_answer_rag_refuses_without_evidence_without_calling_llm():
    llm = FakeLLM()
    bot = make_bot(llm_client=llm)

    answer = bot.answer_rag("xyzzy_nonexistent_term")

    assert answer == "I do not know based on these docs."
    assert llm.answer_calls == []  # guardrail short-circuits before the LLM


# ── Task suggestion normalization ────────────────────────────────────────────

def test_suggest_task_requires_llm_client():
    bot = make_bot(llm_client=None)
    with pytest.raises(RuntimeError):
        bot.suggest_task("plan a vet visit")


def test_suggest_task_normalizes_valid_suggestion():
    raw = {
        "title": "Vet Visit",
        "description": "Annual checkup",
        "date": "2026-04-01",
        "time": "14:30",
        "priority": 5,
        "recurrence": "weekly",
    }
    bot = make_bot(llm_client=FakeLLM(suggestion=raw))

    suggestion = bot.suggest_task("schedule a vet visit")

    assert suggestion["title"] == "Vet Visit"
    assert suggestion["priority"] == 5
    assert suggestion["recurrence"] == "weekly"
    assert suggestion["date"].isoformat() == "2026-04-01"
    assert suggestion["time"].strftime("%H:%M") == "14:30"


def test_suggest_task_clamps_priority_and_defaults_recurrence():
    raw = {"title": "Play", "priority": 99, "recurrence": "yearly"}
    bot = make_bot(llm_client=FakeLLM(suggestion=raw))

    suggestion = bot.suggest_task("play time")

    assert suggestion["priority"] == 10          # clamped to max
    assert suggestion["recurrence"] == "none"    # invalid value falls back


def test_suggest_task_rejects_missing_title():
    bot = make_bot(llm_client=FakeLLM(suggestion={"description": "no title"}))
    assert bot.suggest_task("something") is None


def test_suggest_task_handles_non_dict():
    bot = make_bot(llm_client=FakeLLM(suggestion=None))
    assert bot.suggest_task("something") is None


def test_suggest_task_tolerates_bad_date_and_time():
    raw = {"title": "Walk", "date": "not-a-date", "time": "99:99"}
    bot = make_bot(llm_client=FakeLLM(suggestion=raw))

    suggestion = bot.suggest_task("walk")

    assert suggestion["title"] == "Walk"
    assert suggestion["date"] is None
    assert suggestion["time"] is None


# ── Reload / data refresh ────────────────────────────────────────────────────

def test_reload_reflects_new_pet():
    bot = make_bot()
    assert "rex" not in bot.index

    owner = Owner(name="Sam")
    owner.add_pet(Pet(name="Rex"))
    bot.set_pawpal_data(owners=[owner])

    assert "rex" in bot.index


def test_full_corpus_text_concatenates_documents():
    bot = make_bot()
    corpus = bot.full_corpus_text()
    assert "Bella" in corpus
    assert isinstance(corpus, str)
