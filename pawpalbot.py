"""
Core PawPalBot class responsible for:
- Loading documents from the docs/ folder
- Loading live PawPal data (owners, pets, tasks) as retrievable documents
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re
from datetime import datetime

from pawpal_context import build_pawpal_documents

class PawPalBot:
    def __init__(self, docs_folder="docs", llm_client=None, owners=None, scheduler=None, pets=None):
        """
        docs_folder: directory containing project documentation files (optional)
        llm_client: optional Gemini client for LLM based answers
        owners: optional list of PawPal Owner objects whose pets/tasks become
            searchable documents so the assistant can answer about real pet data
        scheduler: optional PawPal Scheduler holding the authoritative Task objects
        pets: optional list of Pet objects not yet attached to an owner
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Keep references to the live PawPal system so we can refresh later.
        self.owners = owners or []
        self.scheduler = scheduler
        self.pets = pets or []

        # Guardrail thresholds for "meaningful evidence".
        # PawPal's live docs are short and structured, so a single distinctive
        # match (e.g. a pet or task name) is already strong evidence. We only
        # refuse when NO meaningful query term appears in the best snippet.
        self.min_evidence_matches = 1

        # Load documents (docs/ folder + live PawPal data) and build the index.
        self.reload()

    # -----------------------------------------------------------
    # (Re)building the index
    # -----------------------------------------------------------

    def reload(self):
        """
        Rebuild the document set and retrieval index from the docs/ folder and
        the current PawPal data. Call this after PawPal data changes (a pet or
        task was added/edited) so retrieval reflects the latest state.
        """
        # File-based docs plus live PawPal data, combined into one corpus.
        self.documents = self.load_documents() + build_pawpal_documents(
            owners=self.owners, scheduler=self.scheduler, pets=self.pets
        )
        self.paragraphs = self.build_paragraph_store(self.documents)
        self.index = self.build_index(self.paragraphs)
        return self

    def set_pawpal_data(self, owners=None, scheduler=None, pets=None):
        """Point PawPalBot at (new) PawPal data and rebuild the index."""
        if owners is not None:
            self.owners = owners
        if scheduler is not None:
            self.scheduler = scheduler
        if pets is not None:
            self.pets = pets
        return self.reload()

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def _tokenize(self, text):
        return re.findall(r"\b\w+\b", text.lower())

    def _split_paragraphs(self, text):
        chunks = re.split(r"\n\s*\n", text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _query_tokens(self, query):
        stopwords = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "how", "i", "in", "is", "it", "of", "on", "or", "that", "the",
            "this", "to", "what", "where", "which", "with", "you"
        }
        return [token for token in self._tokenize(query) if token not in stopwords]

    def build_paragraph_store(self, documents):
        paragraphs = []
        for filename, text in documents:
            for paragraph in self._split_paragraphs(text):
                paragraphs.append((filename, paragraph))
        return paragraphs

    def build_index(self, paragraphs):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for paragraph_id, (_, paragraph_text) in enumerate(paragraphs):
            tokens = set(self._tokenize(paragraph_text))
            for token in tokens:
                if token not in index:
                    index[token] = []
                index[token].append(paragraph_id)

        # Keep deterministic ordering for easier debugging/testing
        for token in index:
            index[token].sort()

        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        query_tokens = set(self._tokenize(query))
        text_tokens = set(self._tokenize(text))

        # Score = number of query words present in the document
        return sum(1 for token in query_tokens if token in text_tokens)

    def retrieve(self, query, top_k=3):
        """
        TODO (Phase 1):
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (filename, text) sorted by score descending.
        """
        results = []

        scored = self.retrieve_with_scores(query, top_k=top_k)
        results = [(filename, paragraph_text) for _, filename, paragraph_text in scored]

        return results

    def retrieve_with_scores(self, query, top_k=3):
        scored_results = []

        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return scored_results

        # Narrow search using inverted index
        candidate_paragraph_ids = set()
        for token in query_tokens:
            candidate_paragraph_ids.update(self.index.get(token, []))

        if not candidate_paragraph_ids:
            return scored_results

        scored = []
        for paragraph_id in candidate_paragraph_ids:
            filename, paragraph_text = self.paragraphs[paragraph_id]
            score = self.score_document(query, paragraph_text)
            if score > 0:
                scored.append((score, filename, paragraph_text))

        scored.sort(key=lambda item: (-item[0], item[1]))
        scored_results = scored[:top_k]

        return scored_results

    def has_meaningful_evidence(self, query, scored_snippets):
        if not scored_snippets:
            return False

        query_terms = set(self._query_tokens(query))
        if not query_terms:
            return False

        # Count how many *meaningful* query terms (stopwords stripped) actually
        # appear in the best-scoring snippet. Filler words like "does"/"today"
        # never show up in the structured docs, so scoring against the raw query
        # unfairly punished short, natural questions.
        top_snippet_text = scored_snippets[0][2]
        top_snippet_tokens = set(self._tokenize(top_snippet_text))
        matches = sum(1 for term in query_terms if term in top_snippet_tokens)

        return matches >= self.min_evidence_matches

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        scored_snippets = self.retrieve_with_scores(query, top_k=top_k)

        if not self.has_meaningful_evidence(query, scored_snippets):
            return "I do not know based on these docs."

        snippets = [(filename, text) for _, filename, text in scored_snippets]

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        scored_snippets = self.retrieve_with_scores(query, top_k=top_k)

        if not self.has_meaningful_evidence(query, scored_snippets):
            return "I do not know based on these docs."

        snippets = [(filename, text) for _, filename, text in scored_snippets]

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Task suggestions (LLM-assisted quick-add)
    # -----------------------------------------------------------

    def suggest_task(self, query, top_k=5):
        """
        Ask the LLM to propose ONE concrete care task from the owner's request,
        grounded in the current pets/schedule.

        Returns a dict ready to prefill an "Add Task" form:
            {title, description, date (date), time (time), priority (int),
             recurrence ("none"|"daily"|"weekly")}
        or None if no usable suggestion could be produced.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "Task suggestions require an LLM client. Provide a GeminiClient instance."
            )

        # Any relevant existing records give the model helpful grounding, but a
        # suggestion should still work when nothing matches.
        snippets = self.retrieve(query, top_k=top_k)
        raw = self.llm_client.suggest_task(query, snippets)
        return self._normalize_suggestion(raw)

    def _normalize_suggestion(self, raw):
        """Convert the LLM's raw JSON dict into typed values for the UI form."""
        if not isinstance(raw, dict):
            return None

        title = str(raw.get("title", "")).strip()
        if not title:
            return None

        suggestion = {
            "title": title,
            "description": str(raw.get("description", "")).strip(),
            "date": None,
            "time": None,
            "priority": 1,
            "recurrence": "none",
        }

        # Priority -> clamped int
        try:
            suggestion["priority"] = max(0, min(10, int(raw.get("priority", 1))))
        except (TypeError, ValueError):
            pass

        # Recurrence -> one of the allowed values
        rec = str(raw.get("recurrence", "none")).lower().strip()
        if rec in ("none", "daily", "weekly"):
            suggestion["recurrence"] = rec

        # Date "YYYY-MM-DD" -> date. Never accept a date in the past: the LLM
        # sometimes anchors to its training cutoff (e.g. 2023-10-27), so clamp
        # any past date forward to today.
        raw_date = str(raw.get("date", "")).strip()
        if raw_date:
            try:
                parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                today = datetime.today().date()
                suggestion["date"] = max(parsed_date, today)
            except ValueError:
                pass

        # Time "HH:MM" -> time
        raw_time = str(raw.get("time", "")).strip()
        if raw_time:
            try:
                suggestion["time"] = datetime.strptime(raw_time, "%H:%M").time()
            except ValueError:
                pass

        return suggestion

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
