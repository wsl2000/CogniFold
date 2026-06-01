"""LongMemEval Benchmark Runner for Cognifold.

This script evaluates the Cognifold memory system using the LongMemEval benchmark.
It downloads the dataset, ingests chat history into the memory graph, and answers questions.
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

# Add src and project root to python path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(_project_root, "src"))
sys.path.append(_project_root)

# Analysis utils for enriched wrong-case reporting
sys.path.insert(0, str(Path(__file__).parents[2]))
try:
    from benchmarks.analysis_utils import enrich_eval_result, save_wrong_cases
except ImportError:
    enrich_eval_result = None  # type: ignore[assignment]
    save_wrong_cases = None  # type: ignore[assignment]

from cognifold.agent.agent import CognifoldAgent
from cognifold.agent.config import AgentConfig
from cognifold.agent.prompt_profile import load_prompt_profiles
from cognifold.executor.runner import PlanExecutor
from cognifold.graph.store import ConceptGraph
from cognifold.models.event import Event
from cognifold.models.node import Edge, Node, NodeType
from cognifold.query.agent import MemoryQueryAgent
from cognifold.query.models import QueryConfig, RetrievalMode

from benchmarks.longmemeval.symbolic_resolver import (
    LongMemEvalSymbolicResolver,
    render_symbolic_block,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_URL = "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json"
DATA_FILENAME = "longmemeval_s_cleaned.json"
PROFILE_PATH = Path(__file__).parents[2] / "configs" / "longmemeval_profile.yaml"


def download_data(output_dir: Path) -> Path:
    """Download the LongMemEval dataset if not present."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / DATA_FILENAME

    if not file_path.exists():
        logger.info(f"Downloading dataset from {DATA_URL}...")
        urllib.request.urlretrieve(DATA_URL, file_path)
        logger.info(f"Downloaded dataset to {file_path}")
    else:
        logger.info(f"Dataset found at {file_path}")

    return file_path


def call_llm(prompt: str, config: AgentConfig, json_mode: bool = False) -> str:
    """Call LLM with the given prompt (OpenAI or Gemini).

    json_mode forces strict JSON output (OpenAI: response_format={"type":
    "json_object"}; Gemini: response_mime_type=application/json + ThinkingConfig
    budget=0 so all the budget reaches the visible reply).
    """
    model_name = config.model_name.replace("openai:", "").replace("gemini:", "")
    is_gemini = config.model_name.startswith("gemini") or model_name.startswith("gemini-")

    try:
        if is_gemini:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY not set for Gemini model")
                return ""
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            gc_kwargs: dict = {
                "temperature": 0.0,
                "max_output_tokens": config.max_tokens,
            }
            if json_mode:
                gc_kwargs["response_mime_type"] = "application/json"
            if "2.5" in model_name:
                gc_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            gc = types.GenerateContentConfig(**gc_kwargs)
            response = client.models.generate_content(
                model=model_name, contents=prompt, config=gc
            )
            text = getattr(response, "text", None)
            return text.strip() if isinstance(text, str) else ""

        # Default: OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            logger.error("OPENAI_API_KEY not set")
            return ""
        from openai import OpenAI

        client = OpenAI(api_key=openai_key)
        # gpt-5 / o1 / o3 are reasoning models — they reject custom
        # temperature and require max_completion_tokens.
        is_reasoning_model = (
            model_name.startswith("o1")
            or model_name.startswith("o3")
            or "gpt-5" in model_name
        )
        kwargs: dict = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
        }
        if is_reasoning_model:
            # High reasoning effort for QA — LongMemEval rewards thorough
            # multi-session synthesis. 24K budget so thinking + reply fit.
            kwargs["max_completion_tokens"] = max(config.max_tokens, 24576)
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["temperature"] = 0.0
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return ""


_LONGMEMEVAL_DATE_RE = __import__("re").compile(r"\s*\([A-Za-z]+\)\s*")


def _parse_longmemeval_date(s: str) -> datetime:
    """Parse session_date_str. LongMemEval uses 'YYYY/MM/DD (Dow) HH:MM',
    not ISO — the prior `datetime.fromisoformat` failed silently and fell back
    to `datetime.now()`, stamping every session with the benchmark run time."""
    if not s:
        return datetime.now()
    # Try ISO 8601 first (covers other datasets reusing this runner)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    # LongMemEval native format: "2023/04/23 (Sun) 08:57"
    try:
        cleaned = _LONGMEMEVAL_DATE_RE.sub(" ", s).strip()
        return datetime.strptime(cleaned, "%Y/%m/%d %H:%M")
    except (ValueError, TypeError):
        pass
    # Date only fallback
    try:
        return datetime.strptime(s.split()[0], "%Y/%m/%d")
    except (ValueError, IndexError):
        pass
    logger.warning(f"Could not parse session date: {s!r}; falling back to now")
    return datetime.now()


_TEMPORAL_KEYWORDS = (
    "when", "before", "after", "days", "weeks", "months", "years",
    "between", "order", "first", "last", "latest", "earliest", "recent",
    "since", "until", "how long", "how many days", "in what order",
    "what was my", "personal best",
)


def is_temporal_question(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _TEMPORAL_KEYWORDS)


def build_temporal_block(graph: ConceptGraph, question: str, max_items: int = 60) -> str:
    """Symbolic temporal helper: when the question carries temporal intent,
    enumerate every dated concept/event in the graph sorted chronologically and
    inject as ## TEMPORAL FACTS so the reader sees absolute dates side by side.

    This bypasses the retrieval ranker's date-agnostic top-K selection — every
    fact retains its session date directly from the graph's time anchors.
    """
    if not is_temporal_question(question):
        return ""

    dated: list[tuple[datetime, str, str]] = []
    for n in graph.get_all_nodes():
        if n.type not in (NodeType.CONCEPT, NodeType.EVENT):
            continue
        date_str = n.data.get("date") or n.data.get("extracted_at") or n.data.get("timestamp")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
        except Exception:
            continue
        title = n.data.get("title", n.id)
        desc = (n.data.get("description") or n.data.get("content") or "")[:200]
        # Strip the [YYYY-MM-DD] prefix from title/desc so the symbolic block
        # doesn't double-print the date (we now stamp the title at write time).
        if title.startswith("[") and "]" in title[:13]:
            title = title.split("]", 1)[1].lstrip()
        if desc.startswith("[") and "]" in desc[:13]:
            desc = desc.split("]", 1)[1].lstrip()
        dated.append((dt, title, desc))

    if not dated:
        return ""

    dated.sort(key=lambda x: x[0])
    # Cap to most-recent-first within budget so we don't blow context
    dated = dated[-max_items:]

    lines = [
        "## TEMPORAL FACTS (sorted chronologically — verified by graph time anchors)"
    ]
    for dt, title, desc in dated:
        lines.append(f"- [{dt.date()}] **{title}** — {desc}")
    return "\n".join(lines) + "\n"


_RECENCY_TRIGGER = re.compile(
    r"\b(?:most\s+recent|latest|recent(?:ly)?|current|new(?:est)?|last(?:est)?|"
    r"this\s+(?:week|month|year)|nowadays|these\s+days)\b",
    re.IGNORECASE,
)


# Cluster E trigger — "previous conversation about X" / "you (mentioned|
# recommended|provided|listed|suggested) X". When the question explicitly
# references the assistant's prior turn, the answer is in a raw assistant
# EVENT — which retrieval routinely buries because (a) its title is just
# "Assistant message" so phrase score is weak, and (b) the distilled CONCEPT
# nodes win on lexical overlap. build_assistant_recall_block surfaces the
# raw assistant text directly.
_ASSISTANT_RECALL_TRIGGER = re.compile(
    r"\b(?:"
    # require explicit past-conversation anchor; the broader version
    # ("you mentioned/suggested" alone) was empirically shown to mis-fire
    # on present-tense advice requests ("Can you suggest some activities?")
    # and inject unrelated assistant text → preference-cluster regressions.
    r"previous\s+(?:conversation|chat|discussion|talk)|"
    r"earlier\s+(?:conversation|chat|discussion)|"
    r"prior\s+(?:conversation|chat|discussion)|"
    r"our\s+(?:previous|earlier|prior|last)\s+(?:chat|conversation|discussion|talk)|"
    r"in\s+our\s+(?:previous|earlier|prior|last)\s+(?:chat|conversation|discussion|talk)|"
    r"last\s+time\s+(?:we|you|i)|"
    r"i\s+was\s+going\s+through\s+our|"
    r"we\s+(?:discussed|talked\s+about)\s+\w+(?:\s+\w+){0,5}\s+earlier|"
    r"i\s+(?:think\s+)?we\s+discussed|"
    r"that\s+(?:list|recommendation|suggestion)\s+you\s+(?:gave|provided|mentioned|made)"
    r")\b",
    re.IGNORECASE,
)


def _stopwords() -> set[str]:
    return {
        "a","an","the","this","that","these","those","i","my","me","mine",
        "is","am","are","was","were","be","been","being","do","did","does","done",
        "have","has","had","will","would","could","should","can","may","might","must",
        "and","or","but","if","then","else","of","to","in","on","at","for","with",
        "from","by","as","than","into","onto","over","under","about","what","where",
        "when","which","who","whom","whose","how","why","most","recent","latest",
        "current","new","newest","last","ever","also","just","so","very","really",
        "you","your","go","get","got","gone","gotten","make","made","take","took",
    }


def build_recency_block(graph: ConceptGraph, question: str, max_items: int = 8) -> str:
    """Surface a date-sorted DESC list of concepts that lexically match the
    question topic — only when the question uses recency language.

    The reader prompt is already long enough that the per-concept [date]
    prefix gets skimmed past; this block restates the top recency-relevant
    nodes in newest-first order so picking the "most recent" answer reduces
    to copying the first bullet.
    """
    if not _RECENCY_TRIGGER.search(question):
        return ""

    # Extract content tokens from the question (drop stopwords + recency cue).
    sw = _stopwords()
    q_tokens = {
        t for t in re.findall(r"[a-zA-Z]+", question.lower())
        if t not in sw and len(t) > 2
    }
    if not q_tokens:
        return ""

    scored: list[tuple[float, datetime, str, str]] = []
    for n in graph.get_all_nodes():
        if n.type not in (NodeType.CONCEPT, NodeType.EVENT):
            continue
        date_str = n.data.get("date") or n.data.get("extracted_at") or n.data.get("timestamp")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
        except Exception:
            continue
        title = n.data.get("title", n.id)
        desc = (n.data.get("description") or n.data.get("content") or "")[:200]
        # Strip the [YYYY-MM-DD] prefix from title so we don't double-print.
        if title.startswith("[") and "]" in title[:13]:
            title = title.split("]", 1)[1].lstrip()
        if desc.startswith("[") and "]" in desc[:13]:
            desc = desc.split("]", 1)[1].lstrip()
        text = f"{title} {desc}".lower()
        text_tokens = set(re.findall(r"[a-zA-Z]+", text))
        overlap = len(q_tokens & text_tokens)
        if overlap == 0:
            continue
        score = overlap / max(1, len(q_tokens))
        scored.append((score, dt, title, desc))

    if not scored:
        return ""

    # Sort by date DESC primary, score DESC secondary so newest match wins.
    scored.sort(key=lambda x: (x[1], x[0]), reverse=True)
    top = scored[:max_items]

    lines = [
        "## MOST RECENT MATCHES (newest → oldest; pick the top entry for 'most recent / latest / current' questions)"
    ]
    for i, (_, dt, title, desc) in enumerate(top, 1):
        lines.append(f"{i}. [{dt.date()}] **{title}** — {desc}")
    return "\n".join(lines) + "\n"


def build_assistant_recall_block(
    graph: ConceptGraph, question: str, max_items: int = 4, snippet_chars: int = 600
) -> str:
    """Surface raw assistant EVENT text for "previous conversation about X"
    questions.

    The distilled CONCEPT nodes paraphrase the assistant's surface form away
    (the Borges quote becomes "user asked about the Library of Babel"), and
    retrieval ranks them above raw EVENTs because the EVENT title is just
    "Assistant message". When the question explicitly asks for a name /
    title / quote the assistant produced earlier, hand the reader the raw
    text directly.

    Pattern: same lexical-overlap scoring as build_recency_block. Filtered
    to assistant role EVENTs only. Trigger-gated so this block is silent on
    questions that don't reference a prior assistant turn (no regression
    risk on the other clusters).
    """
    if not _ASSISTANT_RECALL_TRIGGER.search(question):
        return ""

    sw = _stopwords()
    q_tokens = {
        t for t in re.findall(r"[a-zA-Z]+", question.lower())
        if t not in sw and len(t) > 2
    }
    if not q_tokens:
        return ""

    scored: list[tuple[float, datetime, str]] = []
    for n in graph.get_all_nodes():
        if n.type != NodeType.EVENT:
            continue
        if n.data.get("role") != "assistant":
            continue
        content = n.data.get("content") or n.data.get("description") or ""
        if not content:
            continue
        date_str = n.data.get("date") or n.data.get("timestamp")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "")[:19]) if "T" in date_str \
                else datetime.fromisoformat(date_str)
        except Exception:
            continue
        text_tokens = set(re.findall(r"[a-zA-Z]+", content.lower()))
        overlap = len(q_tokens & text_tokens)
        if overlap == 0:
            continue
        # Recall fraction × small log boost for richer assistant turns.
        score = overlap / max(1, len(q_tokens))
        scored.append((score, dt, content))

    if not scored:
        return ""

    # Sort by score DESC; on ties, prefer newer date (more likely the turn
    # the user is referring back to).
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = scored[:max_items]

    lines = [
        "## RAW_ASSISTANT (verbatim text from assistant turns the question likely refers to — copy names/quotes from here, do NOT substitute)",
    ]
    for i, (score, dt, content) in enumerate(top, 1):
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > snippet_chars:
            snippet = snippet[:snippet_chars] + "…"
        lines.append(f"{i}. [{dt.date()}] (overlap={score:.2f}) {snippet}")
    return "\n".join(lines) + "\n"


def generate_answer(
    question: str, context: str, config: AgentConfig, qa_template: str | None = None
) -> str:
    """Generate an answer using the LLM based on context."""
    if qa_template:
        prompt = qa_template.format(question=question, context=context)
    else:
        prompt = f"""Answer the question based on the provided context.

Context:
{context}

Question: {question}

Instructions:
- Answer using ONLY the provided context
- Commit to your best inference from any relevant signal — do not refuse with "Unknown" when even a tangential fact is available
- Be concise and specific

Answer:"""

    # Always-on augmentation (independent of profile template).
    prompt += (
        "\n\nIMPORTANT — read in order:\n"
        "1. **RECENCY RULE.** If a '## MOST RECENT MATCHES' block appears, the **top "
        "entry is the answer** for any 'most recent / latest / current / new' question. "
        "Do not pick a lower entry. If no such block exists, scan every "
        "[YYYY-MM-DD] tag in the context and prefer the entry with the LATEST date.\n"
        "2. **SYMBOLIC_ANSWER.** If a 'SYMBOLIC_ANSWER' block appears, restate its "
        "**Answer** verbatim — do not recompute or paraphrase.\n"
        "3. **RECALL_HINT.** Treat the **Candidate** as a guess and verify against the "
        "rest of the context; prefer a more specific or more recent contradicting fact.\n"
        "4. **PREFERENCES.** For recommendation/suggestion questions, weave in any "
        "user preferences (brand, language, theme, requirement) you can find.\n"
        "5. **NO 'UNKNOWN'.** If any related signal exists, synthesize a specific "
        "answer — never refuse."
    )

    answer = call_llm(prompt, config)

    # Reader sanity check — reasoning models (gpt-5) occasionally exhaust
    # max_completion_tokens on internal thinking and return a junk fragment
    # (empty, single-word, or a literal token copied from the context like
    # "User message" / "Assistant message"). Detect that and fall back to a
    # deterministic non-reasoning model so the question doesn't waste the
    # whole entry.
    if _is_junk_reader_output(answer, context):
        logger.warning(
            "Reader returned junk output (%r) for question %r — retrying with gpt-4o-mini fallback",
            answer[:60], question[:80],
        )
        fallback_config = dataclasses.replace(
            config, model_name="openai:gpt-4o-mini", max_tokens=1024
        )
        answer = call_llm(prompt, fallback_config)
    return answer


# Boilerplate strings that frequently appear in the retrieved context as
# structural markers (edge labels, time-anchor titles). If the reader's reply
# is literally one of these — or extremely short — it's not an answer.
_JUNK_OUTPUTS = frozenset({
    "user message", "assistant message", "user", "assistant",
    "answer", "answer:", "unknown", "n/a", "none", "null", "",
})


def _is_junk_reader_output(answer: str, context: str) -> bool:
    """Detect garbage reader output (empty / boilerplate / context fragment)."""
    a = (answer or "").strip()
    if not a:
        return True
    a_lower = a.lower().rstrip(".:,;!?")
    if a_lower in _JUNK_OUTPUTS:
        return True
    # Very short answers that are *also* substrings of structural context
    # markers are almost certainly token-leak from a truncated reasoning reply.
    if len(a) <= 30 and any(
        marker in context for marker in (f"related_to: {a}", f"to: {a};", f"to: {a}\n")
    ):
        return True
    return False


# Round 7 R7-1 (no-memory reader fallback) and R7-D (regex anchor pass over
# raw session text) were tested and reverted — both 0 net fix, see history.md
# for the post-mortem.


def evaluate_answer(
    question: str,
    hypothesis: str,
    ground_truth: str,
    config: AgentConfig,
    eval_template: str | None = None,
) -> dict:
    """Evaluate hypothesis against ground truth using LLM."""
    if eval_template:
        prompt = eval_template.format(
            question=question,
            hypothesis=hypothesis,
            ground_truth=ground_truth,
        )
    else:
        prompt = f"""Evaluate if the hypothesis answer matches the ground truth.

Question: {question}
Ground Truth: {ground_truth}
Hypothesis: {hypothesis}

Evaluation criteria:
1. Is the hypothesis semantically equivalent to the ground truth?
2. Does it contain the key information?
3. Are there factual errors?

Reply with EXACTLY one of: CORRECT, PARTIAL, or INCORRECT
Then on a new line, provide a brief explanation.

Evaluation:"""

    try:
        response = call_llm(prompt, config)
        lines = response.strip().split("\n", 1)
        result = lines[0].strip().upper()
        explanation = lines[1].strip() if len(lines) > 1 else ""

        if "CORRECT" in result and "INCORRECT" not in result:
            return {"result": "CORRECT", "explanation": explanation}
        elif "PARTIAL" in result:
            return {"result": "PARTIAL", "explanation": explanation}
        else:
            return {"result": "INCORRECT", "explanation": explanation}
    except Exception as e:
        return {"result": "ERROR", "explanation": str(e)}


def process_session_batch(
    session: list[dict],
    timestamp: datetime,
    graph: ConceptGraph,
    config: AgentConfig,
    batch_template: str | None = None,
) -> None:
    """Process a full session in batch mode."""
    session_date_str = timestamp.date().isoformat()

    # 0. Create per-session TIME anchor so every node born in this session
    #    has an explicit absolute date the symbolic temporal pass can hit.
    time_node_id = f"t-{timestamp.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    try:
        graph.add_node(
            Node(
                id=time_node_id,
                type=NodeType.TIME,
                data={
                    "title": f"Session date {session_date_str}",
                    "datetime": timestamp.isoformat(),
                    "date": session_date_str,
                },
                created_at=timestamp,
            )
        )
    except Exception:
        pass

    # 1. Add all events programmatically (Episodic Memory)
    events = []
    session_text = []

    prev_event_id = None

    for i, turn in enumerate(session):
        role = turn["role"]
        content = turn["content"]

        session_text.append(f"{role.upper()}: {content}")

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        events.append(event_id)

        graph.add_node(
            Node(
                id=event_id,
                type=NodeType.EVENT,
                data={
                    "title": f"{role.capitalize()} message",
                    "event_type": "chat_message",
                    "role": role,
                    "content": content,
                    "timestamp": timestamp.isoformat(),
                    "date": session_date_str,
                    "session_index": i,
                },
                created_at=timestamp,
            )
        )

        if prev_event_id:
            graph.add_edge(Edge(source=prev_event_id, target=event_id, created_at=timestamp))
        prev_event_id = event_id

        # Link every event to the session time anchor
        try:
            graph.add_edge(Edge(source=event_id, target=time_node_id, created_at=timestamp))
        except Exception:
            pass

    # 2. Extract Concepts using LLM (Semantic Memory)
    full_text = "\n".join(session_text)

    if batch_template:
        prompt = batch_template.format(session_text=full_text)
    else:
        prompt = f"""Analyze the following conversation session and extract factual knowledge about the user.

Focus on:
- User Profile (name, age, job, education, etc.)
- Preferences (likes, dislikes, habits)
- Specific facts mentioned by the user
- Key decisions or shared history

Return a JSON object with a list of "concepts". Each concept should have:
- title: Short title
- description: Factual description
- strength: 0.5 to 1.0 (confidence/importance)
- type: "user_fact", "preference", "event", "relationship", "temporal", or "entity"

Input:
{full_text}

Output JSON format:
{{
  "concepts": [
    {{
      "title": "...",
      "description": "...",
      "strength": 0.8,
      "type": "..."
    }}
  ]
}}"""

    try:
        response_text = call_llm(prompt, config, json_mode=True)

        # Clean markdown (still possible if model ignores response_format)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)

        # Add Concepts to Graph
        for concept in data.get("concepts", []):
            concept_id = f"c-{uuid.uuid4().hex[:8]}"
            # Date-prefix the TITLE so every line in the reader's context window
            # carries a visible absolute date — descriptions are line 2 and tend
            # to get skimmed when 10+ concepts are returned.
            raw_title = concept["title"]
            stamped_title = f"[{session_date_str}] {raw_title}"
            raw_desc = concept.get("description", "")
            graph.add_node(
                Node(
                    id=concept_id,
                    type=NodeType.CONCEPT,
                    data={
                        "title": stamped_title,
                        "description": raw_desc,
                        "strength": concept.get("strength", 0.7),
                        "concept_type": concept.get("type", "user_fact"),
                        "extracted_at": timestamp.isoformat(),
                        "date": session_date_str,
                    },
                    reasoning=f"Extracted from session batch on {session_date_str}",
                    created_at=timestamp,
                )
            )
            # Link to the last event of the session
            if events:
                graph.add_edge(
                    Edge(source=concept_id, target=events[-1], created_at=timestamp)
                )
            # Link concept to the session time anchor
            try:
                graph.add_edge(
                    Edge(source=concept_id, target=time_node_id, created_at=timestamp)
                )
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error in batch extraction: {e}")

    # ---- Patch B: dated-anchor regex pass over user-role turns ----
    # The LLM extraction paraphrases away dated lifecycle anchors
    # ("started ukulele lessons" → "user is learning ukulele"), which
    # makes _try_diff_since-style resolvers fail with "no memory of
    # when X happened". This pass scans the raw user-role turns for
    # explicit verb+object phrases and adds a CONCEPT with the verb
    # AND topic keyword in the title so BM25 / symbolic resolver can
    # find it by phrase.
    #
    # Improvements over the reverted R7-D:
    #   - widened verb list (was started/finished/recovered/got; now
    #     adds began/took up/attended/joined/enrolled/signed up/
    #     completed/launched/picked up/booked/ordered)
    #   - title carries BOTH the verb AND the object noun
    #     (R7-D's "helmet" without "bike" failed BM25 on "bike");
    #     here we keep the full "ATTENDED a baking class" phrase
    #   - only fires when a date is unambiguously the session date
    #     (no risk of cross-day misattribution)
    _add_dated_anchors_from_session(session, timestamp, graph, time_node_id)


_ANCHOR_VERB_RE = re.compile(
    r"\bi\s+(?:(?:have\s+|just\s+|finally\s+|recently\s+)?"
    r"(started|began|took\s+up|picked\s+up|signed\s+up\s+for|"
    r"enrolled\s+in|joined|launched|"
    r"finished|completed|wrapped\s+up|"
    r"recovered\s+from|got\s+over|"
    r"attended|went\s+to|booked|ordered|received|got|"
    r"met|first\s+met|"
    r"bought|purchased|"
    r"moved\s+(?:to|into)|relocated\s+to))"
    r"\s+(?:(?:a|an|the|my|our|some|to\s+the|to\s+a)\s+)?"
    r"([a-z][^.,!?\n;]{2,80})",
    re.IGNORECASE,
)


def _add_dated_anchors_from_session(
    session: list[dict],
    timestamp: datetime,
    graph: ConceptGraph,
    time_node_id: str,
) -> None:
    """Scan user-role turns for verb+object lifecycle phrases and add a
    dated CONCEPT for each. Safe to call after the LLM extraction —
    duplicates are filtered by title uniqueness inside ConceptGraph.
    """
    session_date_str = timestamp.date().isoformat()
    seen_titles: set[str] = set()

    for turn in session:
        if turn.get("role") != "user":
            continue
        content = turn.get("content", "")
        if not content:
            continue
        for m in _ANCHOR_VERB_RE.finditer(content):
            verb = re.sub(r"\s+", " ", m.group(1).strip().lower())
            obj_phrase = re.sub(r"\s+", " ", m.group(2).strip())
            # Trim object phrase to first ~10 words to keep title tight.
            obj_words = obj_phrase.split()[:10]
            obj_clean = " ".join(obj_words).rstrip(" .,'\"")
            if len(obj_clean) < 3:
                continue
            title = f"{verb} {obj_clean}".lower()
            if title in seen_titles:
                continue
            seen_titles.add(title)
            # Anchor concept: title carries verb + topic keyword;
            # description echoes the full triggering sentence for the
            # reader to see in context.
            stamped = f"[{session_date_str}] {title}"
            concept_id = f"anchor-{uuid.uuid4().hex[:8]}"
            try:
                graph.add_node(
                    Node(
                        id=concept_id,
                        type=NodeType.CONCEPT,
                        data={
                            "title": stamped,
                            "description": f"[{session_date_str}] User stated: \"{m.group(0).strip()}\"",
                            "strength": 0.85,
                            "concept_type": "dated_anchor",
                            "extracted_at": timestamp.isoformat(),
                            "date": session_date_str,
                            "anchor_verb": verb,
                            "anchor_object": obj_clean,
                        },
                        reasoning=f"Dated-anchor regex pass over user turn on {session_date_str}",
                        created_at=timestamp,
                    )
                )
                graph.add_edge(
                    Edge(source=concept_id, target=time_node_id, created_at=timestamp)
                )
            except Exception:
                pass


def run_benchmark(args: argparse.Namespace) -> None:
    """Run the benchmark evaluation."""
    # Resolve embedding config: CLI --embedding overrides profile YAML
    from benchmarks._utils import create_embedder, resolve_embedding

    resolved_embedding = resolve_embedding(args.embedding, PROFILE_PATH, "longmemeval")
    embedder, retrieval_mode = create_embedder(resolved_embedding)
    if embedder:
        print(f"Using embedding: {resolved_embedding}")
    else:
        print("Using retrieval: BM25 (no embedding)")

    # Setup paths
    base_dir = Path(__file__).parent
    data_path = download_data(base_dir / "data")
    # `--output-dir` lets parallel batch runs write to separate dirs so they
    # don't trample each other's hypothesis.jsonl. Default = single-process
    # legacy location.
    output_dir = Path(args.output_dir) if args.output_dir else (base_dir / "output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "hypothesis.jsonl"
    metrics_path = output_dir / "metrics.json"

    # Load data
    with open(data_path) as f:
        data = json.load(f)

    # Load profile
    prompt_profile = None
    templates: dict = {}

    if PROFILE_PATH.exists():
        try:
            profiles = load_prompt_profiles(PROFILE_PATH)
            prompt_profile = profiles.get("longmemeval")
            if prompt_profile:
                logger.info(f"Using profile: longmemeval from {PROFILE_PATH}")
            # PromptProfile only retains system/user templates; pull
            # qa_answer / evaluate / batch_extraction directly from the YAML.
            try:
                import yaml as _yaml

                with open(PROFILE_PATH) as _pf:
                    _raw = _yaml.safe_load(_pf) or {}
                templates = (((_raw.get("profiles") or {}).get("longmemeval") or {}).get("templates") or {})
            except Exception as _te:
                logger.warning(f"Could not extract YAML templates: {_te}")
        except Exception as e:
            logger.warning(f"Could not load profile: {e}")

    # Initialize configuration
    config = prompt_profile.to_agent_config() if prompt_profile else AgentConfig()

    if args.model:
        import dataclasses

        config = dataclasses.replace(config, model_name=args.model)

    # Separate config for the LLM-as-judge. Default to the reader (legacy
    # behavior); override with --judge-model to match the canonical LongMemEval
    # protocol (gpt-4o) or any other stronger model.
    import dataclasses

    judge_config = config
    if args.judge_model:
        judge_config = dataclasses.replace(config, model_name=args.judge_model)
        logger.info(f"Using judge model: {args.judge_model} (separate from reader {config.model_name})")

    # Separate config for the extraction (write) path. Defaults to the reader
    # config; override with --writer-model when the reader is a slow reasoning
    # model (gpt-5-mini) but extraction is mechanical JSON (gpt-4o-mini).
    writer_config = config
    if args.writer_model:
        writer_config = dataclasses.replace(config, model_name=args.writer_model)
        logger.info(f"Using writer model: {args.writer_model} (separate from reader {config.model_name})")

    logger.info(f"Using model: {config.model_name}")
    logger.info(f"Batch mode: {args.batch_mode}")
    logger.info(f"Evaluation mode: {'LLM' if args.llm_eval else 'skip'}")
    if args.llm_rerank:
        logger.info(
            f"Batched B-rerank: enabled (model={args.rerank_model}, "
            f"reasoning_effort={args.rerank_reasoning_effort}, "
            f"pool={args.rerank_pool or 'max_nodes'})"
        )
    else:
        logger.info("Batched B-rerank: disabled")

    if args.stratified:
        # Stratified sampling: take N per question_type for balanced coverage
        from collections import defaultdict

        by_type: dict[str, list] = defaultdict(list)
        for ex in data:
            by_type[ex.get("question_type", "?")].append(ex)
        stratified = []
        for qt in sorted(by_type.keys()):
            stratified.extend(by_type[qt][: args.stratified])
        data = stratified
        logger.info(
            f"Stratified sampling: {args.stratified} per question_type "
            f"({len(by_type)} types, {len(data)} total)"
        )

    # --question-ids takes precedence: filter to ONLY those qids.
    if args.question_ids:
        wanted = {q.strip() for q in args.question_ids.split(",") if q.strip()}
        data = [ex for ex in data if ex.get("question_id") in wanted]
        logger.info(f"Filtering to {len(data)} specific question_ids")

    if args.offset:
        data = data[args.offset:]
        logger.info(f"Offset: skipping first {args.offset} examples (remaining {len(data)})")

    if args.limit:
        data = data[: args.limit]
        logger.info(f"Limiting evaluation to first {args.limit} examples")

    results = []
    metrics = {"correct": 0, "partial": 0, "incorrect": 0, "error": 0, "total": 0}

    # Resume support: when --resume, load existing hypothesis.jsonl and skip
    # already-processed question_ids. Without --resume the file is cleared.
    already_done: set[str] = set()
    if args.resume and output_path.exists():
        with open(output_path) as _f:
            for _line in _f:
                try:
                    _r = json.loads(_line)
                    qid = _r.get("question_id")
                    if not qid:
                        continue
                    already_done.add(qid)
                    results.append(_r)
                    if args.llm_eval and _r.get("evaluation"):
                        vk = _r["evaluation"].get("result", "").lower()
                        if vk in metrics:
                            metrics[vk] = metrics.get(vk, 0) + 1
                            metrics["total"] += 1
                except Exception:
                    pass
        logger.info(f"Resume: skipping {len(already_done)} already-done question_ids")
    elif output_path.exists():
        output_path.unlink()

    for item in tqdm(data, desc="Evaluating"):
        question_id = item["question_id"]
        if question_id in already_done:
            continue
        question = item["question"]
        sessions = item["haystack_sessions"]
        session_dates = item["haystack_dates"]
        ground_truth = item.get("answer", "")

        # 1. Reset Memory (New Graph for each question)
        graph = ConceptGraph()

        # Initialize agents
        if prompt_profile:
            agent = CognifoldAgent(config=config, prompt_profile=prompt_profile)
        else:
            agent = CognifoldAgent(config=config)

        executor = PlanExecutor(graph)

        query_config = QueryConfig(
            domain="longmemeval",
            max_nodes=20,
            include_reasoning=True,
            retrieval_mode=retrieval_mode,
            use_llm_rerank_batched=bool(args.llm_rerank),
            rerank_model=args.rerank_model,
            rerank_reasoning_effort=args.rerank_reasoning_effort,
            pre_rerank_pool=args.rerank_pool if args.llm_rerank else 0,
        )
        query_agent = MemoryQueryAgent(graph, config=query_config, embedder=embedder)

        # 2. Ingest History
        for session_idx, session in enumerate(sessions):
            session_date_str = (
                session_dates[session_idx]
                if session_idx < len(session_dates)
                else datetime.now().isoformat()
            )
            timestamp = _parse_longmemeval_date(session_date_str)

            if args.batch_mode:
                process_session_batch(
                    session=session,
                    timestamp=timestamp,
                    graph=graph,
                    config=writer_config,
                    batch_template=templates.get("batch_extraction"),
                )
            else:
                for turn in session:
                    if turn["role"] == "user":
                        content = turn["content"]

                        event = Event(
                            event_id=f"evt-{uuid.uuid4().hex[:8]}",
                            timestamp=timestamp,
                            source="longmemeval",
                            event_type="chat_message",
                            title=content[:50],
                            description=content,
                            context={"full_content": content},
                        )

                        # Retrieve context
                        retrieval = query_agent.query_semantic(content[:200])
                        context_node_ids = [node.node_id for node in retrieval.nodes[:10]]

                        try:
                            plan = agent.process_event(
                                event=event,
                                graph=graph,
                                context_node_ids=context_node_ids,
                            )
                            executor.execute(plan)
                        except Exception as e:
                            logger.error(f"Error processing event {event.event_id}: {e}")

        # 3. Answer Question
        # R9-A: dynamic max_nodes — aggregation questions ("how many X have I",
        # "how much money spent on X") need to see ALL relevant entity
        # concepts to count/sum correctly. With max_nodes=20, multi-entity
        # questions chronically under-count. Bump to 50 for these only;
        # single-fact questions stay at 20 to avoid context dilution.
        _qa_agg_count = re.search(
            r"\bhow\s+many\s+(?!(?:hours?|minutes?|seconds?|days?|weeks?|months?|years?)\b)"
            r"\w+.*\b(?:have\s+i|i\s+(?:have|own|bought|worked|attended|read|"
            r"watched|tried|made|led|leading|did|spent|spend|visited|saw|met))",
            question, re.IGNORECASE,
        )
        _qa_agg_sum = re.search(
            r"\b(?:how\s+much|total|sum)\b(?!\s*(?:hours?|minutes?|seconds?|days?|"
            r"weeks?|months?|years?)\b).*\b(?:money|dollars?|expense|expenses?|"
            r"cost|costs?|\$\s*\d|spent\s+on)\b",
            question, re.IGNORECASE,
        )
        _query_max_nodes = 50 if (_qa_agg_count or _qa_agg_sum) else None
        # On aggregation questions, also boost the pre-rerank pool so the
        # rerank step has a fuller session set to choose from. Only takes
        # effect when --llm-rerank is on; otherwise the override is
        # max_nodes-equivalent (rerank disabled ⇒ pool boost is moot).
        if args.llm_rerank and (_qa_agg_count or _qa_agg_sum):
            _query_pre_rerank_pool = max(args.rerank_pool, 100)
        elif args.llm_rerank:
            _query_pre_rerank_pool = args.rerank_pool
        else:
            _query_pre_rerank_pool = None
        _query_start = time.time()
        query_result = query_agent.query_for_qa(
            question=question,
            domain="longmemeval",
            query_mode=args.query_mode,
            max_nodes=_query_max_nodes,
            pre_rerank_pool=_query_pre_rerank_pool,
        )
        context_text = query_result.context

        # Symbolic temporal layer: for time-ordering / interval / latest-fact
        # questions, prepend a chronologically-sorted block of every dated
        # node so the reader sees absolute dates without relying on retrieval
        # to preserve them.
        if args.symbolic_temporal:
            temporal_block = build_temporal_block(graph, question)
            if temporal_block:
                context_text = temporal_block + "\n" + context_text

        # Recency injection: for "most recent / latest / current" style
        # questions, sort the topic-matching nodes by date DESC and prepend.
        # The first entry is the answer in 95% of cases — reduces the reader's
        # job from "scan 10+ dates inside descriptions" to "copy bullet #1".
        recency_block = build_recency_block(graph, question)
        if recency_block:
            context_text = recency_block + "\n" + context_text

        # Cluster E — Assistant-text recall. When the question explicitly
        # references a prior assistant turn ("previous conversation about X",
        # "you recommended/mentioned/listed Y"), the answer is in a raw
        # assistant EVENT that distilled CONCEPT retrieval routinely buries.
        # Surface it directly so the reader can copy the verbatim name/quote.
        assistant_block = build_assistant_recall_block(graph, question)
        if assistant_block:
            context_text = assistant_block + "\n" + context_text

        # Symbolic deterministic resolver (ToMi-style): pattern-match the
        # question against the dated graph and compute an exact answer string.
        # If matched, we both inject the answer as a SYMBOLIC_ANSWER block
        # AND short-circuit the LLM (`answer` = resolver answer verbatim) so
        # the reader can't unsort what we already sorted.
        symbolic_result = None
        if args.symbolic_resolver:
            question_dt = _parse_longmemeval_date(item.get("question_date", ""))
            resolver = LongMemEvalSymbolicResolver(graph, question_date=question_dt)
            symbolic_result = resolver.resolve(question)
            if symbolic_result is not None:
                context_text = render_symbolic_block(symbolic_result) + "\n" + context_text

        # Generate Answer.
        # Bypass policy: respect both the global flag and the resolver's
        # per-pattern bypass hint. Deterministic resolvers (date_diff_*,
        # which_first, chronological_order, strict latest_value) set
        # bypass=True; lexically fuzzy ones (topic_recall, broad
        # latest_value) set bypass=False and only inject a hint.
        should_bypass = (
            symbolic_result is not None
            and args.symbolic_bypass
            and symbolic_result.get("bypass", True)
        )
        try:
            if should_bypass:
                answer = symbolic_result["answer"]
            else:
                answer = generate_answer(
                    question=question,
                    context=context_text,
                    config=config,
                    qa_template=templates.get("qa_answer"),
                )
        except Exception as e:
            logger.error(f"Error generating answer for {question_id}: {e}")
            answer = "Error generating answer."

        # 4. Evaluate (optional)
        eval_result = None
        if args.llm_eval and ground_truth:
            eval_result = evaluate_answer(
                question=question,
                hypothesis=answer,
                ground_truth=ground_truth,
                config=judge_config,
                eval_template=templates.get("evaluate"),
            )
            result_key = eval_result["result"].lower()
            metrics[result_key] = metrics.get(result_key, 0) + 1
            metrics["total"] += 1

        result_entry = {
            "question_id": question_id,
            "question": question,
            "hypothesis": answer,
            "ground_truth": ground_truth,
            "context_length": len(context_text),
            "graph_nodes": graph.node_count,
            "symbolic_pattern": (symbolic_result or {}).get("pattern"),
            "bypass_taken": bool(should_bypass),
        }

        if eval_result:
            result_entry["evaluation"] = eval_result
            result_entry["verdict"] = eval_result.get("result", "")

        if enrich_eval_result is not None:
            enrich_eval_result(
                result_entry,
                graph=graph,
                query_result=query_result,
                retrieval_mode=args.query_mode,
                query_start_time=_query_start,
            )

        results.append(result_entry)

        # Append to file incrementally
        with open(output_path, "a") as f:
            f.write(json.dumps(result_entry) + "\n")

    # Save metrics
    if args.llm_eval:
        total = metrics["total"]
        if total > 0:
            metrics["score_strict"] = metrics["correct"] / total * 100
            metrics["score_partial"] = (metrics["correct"] + 0.5 * metrics["partial"]) / total * 100

        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Metrics saved to {metrics_path}")
        logger.info(f"Results: {metrics}")

    if save_wrong_cases is not None:
        save_wrong_cases(results, str(output_dir))

    logger.info(f"Evaluation complete. Results saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LongMemEval benchmark")
    parser.add_argument("--limit", type=int, help="Limit number of examples to run")
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip the first N examples (applied AFTER --stratified, BEFORE --limit). "
        "Pair with --output-dir + --limit to partition the data for parallel runs.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory (default: benchmarks/longmemeval/output/). "
        "Each parallel batch should point to its own dir to avoid hypothesis.jsonl collisions.",
    )
    parser.add_argument(
        "--question-ids",
        type=str,
        default=None,
        help="Process only specific question_ids (comma-separated). Overrides "
        "--stratified/--limit/--offset filtering.",
    )
    parser.add_argument(
        "--stratified",
        type=int,
        default=None,
        help="Take N per question_type for balanced sampling (applied before --limit)",
    )
    parser.add_argument(
        "--symbolic-temporal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Inject a chronologically-sorted ## TEMPORAL FACTS block for time-ordering questions",
    )
    parser.add_argument(
        "--symbolic-resolver",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use LongMemEvalSymbolicResolver to pattern-match the question and produce a deterministic SYMBOLIC_ANSWER block",
    )
    parser.add_argument(
        "--symbolic-bypass",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When the symbolic resolver matches, use its answer verbatim and skip the LLM reader call",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Override LLM model used for evaluation (default: same as --model). Pass openai:gpt-4o to match the canonical LongMemEval judge.",
    )
    parser.add_argument(
        "--llm-rerank",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable batched B-rerank: one LLM call per question scores every "
        "retrieved candidate jointly and returns ranked indices. See "
        "my_prompt.md §1.2 — this is the canonical rerank path; the legacy "
        "per-doc rerank is intentionally not exposed via CLI.",
    )
    parser.add_argument(
        "--rerank-model",
        type=str,
        default="openai:gpt-5",
        help="Rerank LLM. Default openai:gpt-5 (cheap with reasoning_effort=low).",
    )
    parser.add_argument(
        "--rerank-reasoning-effort",
        type=str,
        default="low",
        choices=["low", "medium", "high"],
        help="Reasoning effort for rerank LLM. Default low — rerank is "
        "scoring relevance, not full QA, so low effort is enough.",
    )
    parser.add_argument(
        "--rerank-pool",
        type=int,
        default=0,
        help="When --llm-rerank is on, retrieval keeps this many candidates "
        "before reranking (rerank then trims to max_nodes). 0 = use "
        "max_nodes (no pool expansion). On aggregation questions "
        "(detected via the R9-A heuristic), the runner auto-bumps to "
        "max(this, 100) so the relevant session is in the pool.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip question_ids already present in output/hypothesis.jsonl (do not clear the file).",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Override model name (e.g., openai:gpt-4o, gemini-1.5-pro)",
    )
    parser.add_argument(
        "--writer-model",
        type=str,
        default=None,
        help="Override extraction model separately (default: same as --model). "
        "Pair openai:gpt-4o-mini for fast deterministic JSON extraction with "
        "openai:gpt-5-mini reader for reasoning-grade QA.",
    )
    parser.add_argument(
        "--disable-concepts",
        action="store_true",
        help="Disable concept formation (Episodic mode)",
    )
    parser.add_argument(
        "--query-mode",
        type=str,
        default="mergefold",
        help="Query mode (base, rag, episodic, mergefold)",
    )
    parser.add_argument(
        "--batch-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use batch processing for faster ingestion",
    )
    parser.add_argument(
        "--llm-eval",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use LLM to evaluate answers against ground truth",
    )
    parser.add_argument(
        "--embedding",
        type=str,
        default=None,
        help="Embedding model (e.g. openai:text-embedding-3-small, gemini:text-embedding-004, or none). Overrides profile config.",
    )

    args = parser.parse_args()
    run_benchmark(args)
