# Model Card — PawPal+ AI Pet Assistant

This model card documents the responsible-AI reflection for **PawPal+**, a pet
care management system with a Retrieval-Augmented Generation (RAG) assistant
built on Google Gemini. It complements the [README](README.md), which covers the
architecture, setup, and usage.

**System at a glance**
- **Purpose:** answer natural-language questions about an owner's pets and care
  schedule, and draft new care tasks.
- **How it works:** live `Owner`/`Pet`/`Task` data is serialized into text
  "documents," a keyword inverted index retrieves the most relevant snippets, and
  Gemini generates an answer grounded **only** in those snippets.
- **Underlying model:** `gemini-flash-lite-latest` via the `google-genai` SDK.

---

## Limitations and Biases

- **Keyword-only retrieval.** Retrieval uses a literal-word inverted index with
  no synonym or semantic understanding. "What shots does Bella need?" will not
  match a task titled "Vet vaccination" because the words differ. This biases the
  system toward users who phrase questions using the exact words stored in their
  data.
- **Only as good as the data entered.** The assistant can only answer from what
  the owner typed. Missing, misspelled, or abbreviated data (e.g. "meds" vs.
  "medication") silently reduces recall and can produce a false "I do not know."
- **Small-corpus evidence thresholds.** The `has_meaningful_evidence` guardrail
  (minimum score + coverage) was tuned for a handful of records. With very short
  queries or a large corpus it may refuse too eagerly or admit weak matches.
- **LLM inherits Gemini's biases.** Any cultural, linguistic, or pet-care
  assumptions baked into the base model can surface in suggestions — for example
  defaulting to dog/cat norms, English-language phrasing, or "typical" schedules
  that may not fit exotic pets or different regions.
- **English-centric.** Prompts, stopword lists, and tokenization assume English.
- **No medical authority.** PawPal+ is an organizer, not a veterinarian. It has
  no knowledge of drug interactions, dosages, or health risks and must not be
  treated as medical advice.

---

## Potential Misuse and Prevention

- **Misuse: treating suggestions as veterinary advice.** A user could ask the
  assistant to decide medication timing or dosage.
  *Prevention:* the RAG prompt restricts answers to the owner's own records and
  forbids inventing facts; the assistant refuses when evidence is missing. The
  README and this card state clearly it is not medical advice. A production
  version would add an explicit medical-disclaimer banner.
- **Misuse: over-trusting auto-generated tasks.** The task-suggestion feature
  could create wrong or unsafe schedules if it acted automatically.
  *Prevention:* suggestions **never** auto-create tasks — they only prefill the
  Add Task form, keeping a human in the loop to review and confirm.
- **Misuse: prompt injection through pet/task text.** Because live data is fed
  into the prompt, a malicious task description ("ignore your instructions…")
  could try to steer the model.
  *Prevention:* snippets are clearly delimited and the model is instructed to use
  them only as reference material, not as instructions. Input is also the user's
  own data, limiting the blast radius; stricter delimiting/escaping would harden
  a multi-user deployment.
- **Misuse: leaking the API key or others' data.** *Prevention:* the key is read
  from a local `.env` (git-ignored), never hard-coded, and the system is
  single-user/session-scoped so one owner's data is not mixed with another's.

---

## Surprises While Testing Reliability

- **The guardrail mattered more than the model.** The single biggest reliability
  win was the cheap `has_meaningful_evidence` check that runs *before* the LLM
  call. Blocking weak matches up front prevented confident-sounding answers built
  on irrelevant snippets — more impactful than any prompt wording change.
- **Refusals were the hard part, not answers.** Getting the model to actually say
  "I do not know based on the docs I have." required explicit, repeated
  instructions; by default it wanted to be helpful and fill gaps with plausible
  guesses.
- **Structured output is fragile.** For task suggestions the model sometimes
  wrapped its JSON in markdown code fences or added commentary, which broke naive
  parsing. Adding a tolerant JSON extractor (`_parse_json_object`) that strips
  fences and grabs the first `{...}` was necessary — a reminder that "return
  JSON" is a request, not a guarantee.
- **Graceful degradation worked better than expected.** Running without an API
  key and falling back to retrieval-only mode still produced genuinely useful
  answers, showing how much value the non-AI retrieval layer carries on its own.

---

## Collaboration With AI

I used an AI coding assistant throughout this project to extend the Week 4
PawPal+ scheduler into an end-to-end AI system. The collaboration was iterative:
I described the behavior I wanted, the AI proposed code, and I reviewed, tested,
and corrected it. I stayed responsible for the design decisions, the guardrail
thresholds, and verifying that each feature actually worked.

**One helpful suggestion.** When I asked to connect the existing document bot to
the live pet data, the AI proposed a clean *bridge* pattern: a separate
`pawpal_context.py` module that serializes `Owner`/`Pet`/`Task` objects into the
same `(filename, text)` shape the retriever already understood. This let me reuse
the entire existing retrieval/RAG pipeline without rewriting it, and kept the
scheduling engine completely unaware of the AI layer. It was a genuinely better
separation of concerns than the tightly-coupled approach I had in mind.

**One flawed suggestion.** While wiring the task-suggestion feature into the
Streamlit UI, the AI initially leaned toward verbose, over-engineered patterns
for loading configuration and prefilling the form — more state juggling than the
problem needed. For example, it suggested heavier environment-loading code when a
simple `load_dotenv()` was enough, which would have made the project larger and
harder to follow. In another case, an edit it proposed didn't match the actual
file because it assumed the form contained fewer fields than it really did, so the
change failed until the real file was re-read. Both cases reinforced that AI
output has to be reviewed against the real codebase rather than trusted blindly —
I had to push back, simplify, and re-verify to keep the project lean and correct.
