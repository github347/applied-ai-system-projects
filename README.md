# 🐾 PawPal+ — AI Pet Care Assistant (Gemini RAG)

## Weekly TF Task 8

The core concept students needed to understand is how to extend and redesign a prior mini-project into a cohesive, end-to-end AI integrated system. Students are most likely to struggle with merging codes if they are taking stuff from previous projects while leaving parts . The AI was helpful in implementing most of the functions needed. However, fine tuning was required to fix some edge cases that it did not know how to handle, for example the load_dotenv import makes it so easy to load environment variables but it kept suggesting longer code that just makes the project bigger than needed currently. One way I would guide a student without giving the answer is to encourage them to keep think about what they want and guide the AI as much as possible.

## Project Source

I am using the Show: PawPal+ from Week 4 (Module 2). The original project was a smart pet care management system that helps owners keep their furry friends happy and healthy.

## Title and Summary

**PawPal+** is a smart pet care management system that helps owners keep their
furry friends happy and healthy. It lets an owner register their pets, schedule
care tasks (walks, meals, meds, vet visits), and generate a daily schedule with
automatic conflict detection.

This version extends the original Week 4 project into an **end-to-end AI system**.
On top of the scheduling engine, PawPal+ now includes an **AI Pet Assistant** that
can answer natural-language questions about *your actual pets and schedule* and
**draft new tasks for you** using a Retrieval-Augmented Generation (RAG) pipeline
built on Google Gemini.

Why it matters: pet owners juggle recurring, easy-to-forget care routines across
multiple animals. A plain scheduler stores the data; PawPal+ makes that data
*conversational* — you can ask "What does Bella need today?" or say "schedule a
vet visit for Max" and get grounded, useful answers instead of clicking through
forms.

> This project is based on **PawPal+** from Week 4 (Module 2).

---

## Architecture Overview

The full class diagram lives in [diagrams/uml_final.md](diagrams/uml_final.md).
At a high level the system has two layers:

**1. Domain layer (`pawpal_system.py`)** — the pure scheduling engine:
- `Owner` holds `Pet` objects; `Pet` stores its own info plus task IDs.
- `Task` is a single care item (title, `scheduled_at`, priority, recurrence…).
- `Scheduler` is the authoritative store of `Task` objects, indexed by id, date,
  and pet for fast lookups. It handles creating, editing, assigning, filtering,
  sorting, and **conflict detection** (same-pet and cross-pet).

**2. AI layer (RAG assistant)** — turns live data into answers:
- `pawpal_context.py` is a **bridge** that serializes the live `Owner`/`Pet`/
  `Task` objects into plain-text `(filename, text)` "documents."
- `PawPalBot` (`pawpalbot.py`) indexes those documents (a tiny inverted index +
  keyword scoring), retrieves the most relevant snippets for a query, and either
  returns them directly or passes them to the LLM.
- `GeminiClient` (`llm_client.py`) wraps Google Gemini. Given the retrieved
  snippets it produces a grounded answer (`answer_from_snippets`) or a structured
  task suggestion (`suggest_task`).

**Data flow (RAG):**
`user question → PawPalBot.retrieve() finds snippets from live pet data →
GeminiClient answers using ONLY those snippets → answer shown in the app`

The Streamlit UI (`app.py`) wires it together: owners/pets/tasks are created in
the browser, stored in session state, fed into `PawPalBot`, and re-indexed
(`reload()`) whenever the data changes.

---

## Setup Instructions

**Prerequisites:** Python 3.10+.

1. **Clone / open the project** and enter its folder.

2. **(Recommended) create a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your Gemini API key** — create a `.env` file in the project root:
   ```ini
   GEMINI_API_KEY=your_key_here
   ```
   Get a key from Google AI Studio. Without a key the app still runs, but the AI
   Assistant falls back to **retrieval-only** answers and task suggestions are
   disabled.

5. **Run the app**
   ```bash
   streamlit run app.py
   ```
   Then open the URL Streamlit prints (usually http://localhost:8501).

6. **(Optional) run the CLI demo** of the scheduling engine only:
   ```bash
   python main.py
   ```

**Typical flow in the app:** create an owner → add pets → add tasks →
**Generate schedule** (see conflicts, edit/reschedule, or delete tasks) → use the
**AI Pet Assistant** to ask questions or suggest tasks.

---

## Sample Interactions

> Setup for the examples below: owner **Alex**; pet **Bella** (dog, allergic to
> chicken); tasks **Morning Walk** (09:00, daily) and **Vet Checkup** (14:00,
> "Annual vaccination").

**Example 1 — Q&A about a pet (RAG)**
```text
You:    What allergies does Bella have?
PawPal: Bella is allergic to chicken. (Based on her pet profile record.)
```

**Example 2 — Q&A about the schedule (RAG)**
```text
You:    When is the vet checkup and what is it for?
PawPal: The Vet Checkup is scheduled for 14:00 and is for an annual
        vaccination for Max. (Based on the Vet Checkup task record.)
```

**Example 3 — Refusal when there's no evidence (guardrail)**
```text
You:    What medication does Bella take?
PawPal: I do not know based on the docs I have.
```

**Example 4 — Task suggestion that prefills the form**
```text
You:    schedule a vet visit for Max next week
PawPal: Suggested 'Vet Visit'. Prefilled the Add Task form above — review and
        click Add Task.
        → title: Vet Visit | date: 2026-08-01 | time: 14:30 | priority: 3
```

**Example 5 — Retrieval-only mode (no API key)**
```text
You:    What allergies does Bella have?
PawPal: [pet_Bella.txt]
        Pet profile: Bella ...
        Allergies: chicken.
```

---

## Design Decisions

- **Two clean layers.** The scheduling engine has zero knowledge of AI. The RAG
  layer reads it through a serializer (`pawpal_context`). This keeps the domain
  logic testable and lets the AI features be optional add-ons.
- **RAG over live data, not static docs.** DocuBot originally read a `docs/`
  folder. I rewrote it (now `PawPalBot`) to serialize the *actual* owners, pets,
  and tasks into documents, so answers reflect the user's real data. It still
  supports a `docs/` folder, so both sources combine.
- **Grounding + explicit refusal.** The LLM is instructed to use *only* the
  retrieved snippets and to reply "I do not know based on the docs I have."
  when evidence is thin. A `has_meaningful_evidence` guardrail (score + coverage
  thresholds) blocks weak matches *before* calling the LLM — saving tokens and
  reducing hallucination.
- **Simple keyword retrieval (inverted index).** Trade-off: it's transparent,
  fast, and dependency-free, but it matches on literal words — synonyms won't
  retrieve. I chose clarity over recall for a project of this size; embeddings
  would be the next upgrade.
- **Graceful degradation.** No `google-genai` / API key → Q&A still works in
  retrieval-only mode and suggestions are disabled with a clear message, so the
  app never hard-crashes on missing config.
- **Suggestion → form prefill.** Rather than auto-creating tasks (risky), the AI
  fills the Add Task form and asks the user to confirm — human stays in the loop.
- **Re-index only on change.** A `pawpal_dirty` flag rebuilds the index after a
  pet/task is added or edited, instead of on every rerun.

---

## Testing Summary

### Automated tests (pytest)

The `tests/` folder contains an automated suite covering every layer of the
system. The tests are **fast, deterministic, and offline** — the LLM and the
Gemini API are replaced with fakes, so no network access or API key is needed.

| File | Covers |
| --- | --- |
| [tests/test_pawpal.py](tests/test_pawpal.py) | Domain layer — `Task`/`Pet`/`Scheduler`: completion, recurrence next-occurrence, sorting, conflict detection, and task deletion (index cleanup, unknown-ID no-op, pet sync). |
| [tests/test_context.py](tests/test_context.py) | `pawpal_context` — serializing owners, pets (incl. "loose" pets), and tasks into `(filename, text)` documents. |
| [tests/test_pawpalbot.py](tests/test_pawpalbot.py) | `PawPalBot` — tokenizing, index building, scoring/retrieval, the evidence guardrail, RAG wiring (via a fake LLM), and task-suggestion normalization. |
| [tests/test_llm_client.py](tests/test_llm_client.py) | `GeminiClient` — prompt construction, refusal on empty snippets, API-error handling, and JSON parsing (`_parse_json_object`), using a stubbed `google.genai`. |

**How to run**

```bash
# from the project root (activate your virtualenv first)
pip install -r requirements.txt      # installs pytest
python -m pytest                     # run the whole suite
```

Useful variations:

```bash
python -m pytest -v                  # verbose, one line per test
python -m pytest tests/test_pawpalbot.py   # a single file
python -m pytest -k "conflict"       # only tests matching a keyword
```

All tests should pass with no external services configured.

### Manual testing

**What I tested**
- Scheduling engine via `python main.py`: create/sort/filter tasks, recurring
  task next-occurrence generation, and same-pet / cross-pet conflict detection.
- `PawPalBot` document building: verified owners, pets (including "loose" pets
  not attached to an owner), and tasks all become searchable documents.
- Retrieval-only Q&A: confirmed relevant snippets are returned and the
  evidence guardrail refuses when matches are weak.
- Task-suggestion parsing (`_normalize_suggestion`): confirmed the LLM's JSON is
  converted into typed `date`/`time`/`priority`/`recurrence` values for the form.
- Conflict resolution: confirmed rescheduling a task via `Scheduler.edit_task`
  re-indexes it and clears a same-pet conflict.
- Task deletion: the **Delete task** button under each task in the Edit tasks
  section calls `Scheduler.delete_task` and removes the task ID from its pets.
  Covered by automated tests in `test_pawpal.py`.

**What worked:** the domain layer is solid and deterministic; the RAG pipeline
returns grounded answers and refuses appropriately; graceful degradation without
an API key behaves as intended.

**What didn't / limitations:** keyword retrieval misses synonym phrasing;
the LLM path depends on network + a valid key; I validated the Streamlit UI logic
by exercising the underlying functions rather than automated UI tests.

**What I learned:** small, well-separated modules made the AI features easy to
bolt on and test. Putting a cheap guardrail *before* the LLM call was the single
biggest win for reliability and cost.

---

## Reflection

This project showed me that "adding AI" is mostly good software design: the
value came from a clean data model and a thin retrieval layer that grounds the
model in real data, plus guardrails that decide *when not to answer*. The hardest
part wasn't calling the model — it was deciding what context to give it and how to
fail safely.

> 📄 The full graded **responsible-AI reflection** — how I collaborated with AI,
> one helpful and one flawed AI suggestion, and the system's limitations — is in
> [model_card.md](model_card.md), not here.

## Preview

![AI Pet Assistan and Build Schedule preview image](<assets/AI Pet Assistan and Build Schedule.png>)
