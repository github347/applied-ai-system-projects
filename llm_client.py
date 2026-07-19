"""
Gemini client wrapper used by PawPalBot.

Handles:
- Configuring the Gemini client from the GEMINI_API_KEY environment variable
- Naive "generation only" answers over the full docs corpus (Phase 0)
- RAG style answers that use only retrieved snippets (Phase 2)

Experiment with:
- Prompt wording
- Refusal conditions
- How strictly the model is instructed to use only the provided context
"""

import os
import json
from google import genai

# Central place to update the model name if needed.
# You can swap this for a different Gemini model in the future.
GEMINI_MODEL_NAME = "gemini-flash-lite-latest"

# "gemini-3.1-flash-lite" ✅
# gemma-3-1b-it ❌, gemini-2.5-flash ⚠️


class GeminiClient:
    """
    Simple wrapper around the Gemini model.

    Usage:
        client = GeminiClient()
        answer = client.naive_answer_over_full_docs(query, all_text)
        # or
        answer = client.answer_from_snippets(query, snippets)
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY environment variable. "
                "Set it in your shell or .env file to enable LLM features."
            )

        self.client = genai.Client(api_key=api_key)

    # -----------------------------------------------------------
    # Phase 0: naive generation over full docs
    # -----------------------------------------------------------

    def naive_answer_over_full_docs(self, query, all_text):
        # We ignore all_text and send a generic prompt instead
        prompt = f"""
    You are a documentation assistant. 
    Answer this developer question: {query}
    """
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            return (response.text or "").strip()
        except Exception as e:
            return f"Unable to generate an answer. ({type(e).__name__}: {e})"

    # -----------------------------------------------------------
    # Phase 2: RAG style generation over retrieved snippets
    # -----------------------------------------------------------

    def answer_from_snippets(self, query, snippets):
        """
        Phase 2:
        Generate an answer using only the retrieved snippets.

        snippets: list of (filename, text) tuples selected by PawPalBot.retrieve

        The prompt:
        - Shows each snippet with its filename
        - Instructs the model to rely only on these snippets
        - Requires an explicit "I do not know" refusal when needed
        """

        if not snippets:
            return "I do not know based on the docs I have."

        context_blocks = []
        for filename, text in snippets:
            block = f"File: {filename}\n{text}\n"
            context_blocks.append(block)

        context = "\n\n".join(context_blocks)

        prompt = f"""
You are PawPal, a cautious and friendly assistant that helps pet owners keep
their furry friends happy and healthy by answering questions about their pets
and care schedule.

You will receive:
- An owner's question
- A small set of snippets describing owners, pets, and care tasks

Your job:
- Answer the question using only the information in the snippets.
- If the snippets do not provide enough evidence, refuse to guess.

Snippets:
{context}

Owner question:
{query}

Rules:
- Use only the information in the snippets. Do not invent pets, tasks,
  dates, or details that are not present.
- If the snippets are not enough to answer confidently, reply exactly:
  "I do not know based on the docs I have."
- When you do answer, briefly mention which records you relied on.
"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            return (response.text or "").strip()
        except Exception as e:
            return f"API error — could not generate answer. ({type(e).__name__}: {e})"

    # -----------------------------------------------------------
    # Task suggestions: propose a structured care task
    # -----------------------------------------------------------

    def suggest_task(self, query, snippets):
        """
        Ask the model to propose ONE care task as a JSON object.

        snippets: list of (filename, text) tuples for grounding (may be empty)
        Returns a parsed dict (title/description/date/time/priority/recurrence)
        or None if the model output could not be parsed.
        """
        context_blocks = []
        for filename, text in (snippets or []):
            context_blocks.append(f"File: {filename}\n{text}")
        context = "\n\n".join(context_blocks) if context_blocks else "(no existing records)"

        prompt = f"""
You are PawPal, a pet-care planning assistant. Propose exactly ONE concrete care
task based on the owner's request and the existing records below.

Existing records:
{context}

Owner request:
{query}

Respond with ONLY a JSON object (no markdown fences, no commentary) using these keys:
- "title": short task name (string)
- "description": one short sentence of detail (string)
- "date": date in YYYY-MM-DD format (string)
- "time": 24-hour time in HH:MM format (string)
- "priority": integer from 0 (low) to 10 (high)
- "recurrence": one of "none", "daily", "weekly"
"""

        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt
            )
            return self._parse_json_object(response.text or "")
        except Exception:
            return None

    @staticmethod
    def _parse_json_object(text):
        """Extract the first JSON object from a model response, tolerating fences."""
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned[:4].lower() == "json":
                cleaned = cleaned[4:]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
