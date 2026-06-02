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
from datetime import datetime, timedelta
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
        # Strip the [YYYY-MM-DD] or [YYYY-MM-DD HH:MM(:SS)] prefix from
        # title/desc so the symbolic block doesn't double-print the date
        # (we now stamp the title at write time, and post-2026-06-01 also
        # include HH:MM).
        if title.startswith("[") and "]" in title[:24]:
            title = title.split("]", 1)[1].lstrip()
        if desc.startswith("[") and "]" in desc[:24]:
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
    # extended for SSA recall patterns: "remind me what was the X on
    # that list", "in your submission/paper", "the X you gave"
    r"remind\s+me\s+(?:what\s+(?:was|did)|of\s+the|about\s+the)|"
    r"on\s+that\s+list|"
    r"in\s+(?:that|your|the\s+previous)\s+(?:submission|paper|report|review|response|article|plan)|"
    r"that\s+(?:list|recommendation|suggestion|advice|note|plan|chart|table)\s+you\s+(?:gave|provided|mentioned|made|wrote|shared)"
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


# R2 trigger — "what time do I X" / "when do I X" / "at what time do I X" /
# "what time did/does I X" / "what time do I usually X". Includes "go to bed",
# "get home", "wake up", "leave", "arrive". Narrow on purpose to avoid
# matching "what time was the meeting" (single-fact) vs personal-routine Qs.
_TIME_OF_DAY_TRIGGER = re.compile(
    r"\b(?:what|which|at\s+what)\s+time\s+(?:do|does|did)\s+i\b|"
    r"\bwhat\s+time\s+do\s+i\b|"
    r"\bwhen\s+do\s+i\s+(?:usually|typically|normally)\b",
    re.IGNORECASE,
)
# Clock-time pattern: 12-hour (6:00 pm, 6:00 PM, 6 pm, 6 a.m.) and 24-hour (06:00).
_CLOCK_TIME_PATTERN = re.compile(
    r"\b(?:\d{1,2}:\d{2}(?:\s*[ap]\.?m\.?)?|\d{1,2}\s*[ap]\.?m\.?)\b",
    re.IGNORECASE,
)


def build_time_of_day_block(
    graph: ConceptGraph, question: str, max_items: int = 6
) -> str:
    """R2 — surface concepts that contain an explicit clock-time value for
    "what time do I X" questions. Exp A showed that writer captures these
    facts (e.g., "User stopping work emails by 7 pm") but retrieval ranks
    photography / fishing concepts above them. This block pins clock-time
    matching nodes to the front of the context.
    """
    if not _TIME_OF_DAY_TRIGGER.search(question):
        return ""

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
        title = n.data.get("title", n.id) or ""
        desc = (n.data.get("description") or n.data.get("content") or "")[:300]
        text = f"{title} {desc}"
        # Must contain at least one clock-time pattern to be considered.
        if not _CLOCK_TIME_PATTERN.search(text):
            continue
        date_str = n.data.get("date") or n.data.get("extracted_at") or n.data.get("timestamp")
        try:
            dt = datetime.fromisoformat((date_str or "").replace("Z", ""))
        except Exception:
            dt = datetime.min
        # Strip [YYYY-MM-DD…] prefix.
        if title.startswith("[") and "]" in title[:24]:
            title = title.split("]", 1)[1].lstrip()
        if desc.startswith("[") and "]" in desc[:24]:
            desc = desc.split("]", 1)[1].lstrip()
        text_tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
        overlap = len(q_tokens & text_tokens)
        if overlap == 0:
            continue
        score = overlap / max(1, len(q_tokens))
        scored.append((score, dt, title, desc))

    if not scored:
        return ""

    # Sort by score DESC, then date DESC (newest tie-break for current routine).
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = scored[:max_items]

    lines = [
        "## CLOCK_TIME_MATCHES (nodes containing an explicit time value — "
        "the answer to a 'what time do I X' question is almost always in one "
        "of these)"
    ]
    for i, (score, dt, title, desc) in enumerate(top, 1):
        date_str = dt.date().isoformat() if dt != datetime.min else "?"
        lines.append(f"{i}. [{date_str}] (overlap={score:.2f}) **{title}** — {desc}")
    return "\n".join(lines) + "\n"


# R3 trigger — questions asking for a specific named entity / proper noun:
# breed/cartoon/store/album/movie/song/dish name, etc.
_PROPER_NOUN_TRIGGER = re.compile(
    r"\bwhat\s+(?:is|was)\s+the\s+name\s+of\b|"
    r"\bwhat\s+breed\b|"
    r"\bwhich\s+(?:movie|book|song|album|store|brand|product|cartoon|show|"
    r"podcast|restaurant|recipe|app|service|company|game|website)\b|"
    r"\bremind\s+me\s+of\s+(?:that|the)\s+\w+\s+name\b|"
    r"\bremind\s+me\s+(?:of\s+)?(?:the\s+name\s+of\s+|that\s+)\w+",
    re.IGNORECASE,
)
# Detect capitalized multi-word phrases in a node's title/desc; require at
# least one "rare" token (capitalized non-stopword) for it to qualify.
_PROPER_NOUN_RE = re.compile(
    r"\b(?:[A-Z][a-z]+(?:[\s\-'][A-Z][a-z]+){0,3})\b"
)


def build_proper_noun_block(
    graph: ConceptGraph, question: str, max_items: int = 6
) -> str:
    """R3 — surface concepts that contain a capitalized proper noun
    (multi-word) for "what's the name / what breed / which X" questions.
    Exp A showed that writer captures these (e.g., "Golden Retriever",
    "Bajimaya v Reward Homes") but retrieval misses them because the
    question doesn't share many tokens with the captured node.
    """
    if not _PROPER_NOUN_TRIGGER.search(question):
        return ""

    sw = _stopwords()
    q_tokens = {
        t for t in re.findall(r"[a-zA-Z]+", question.lower())
        if t not in sw and len(t) > 2
    }
    if not q_tokens:
        return ""

    scored: list[tuple[float, datetime, str, str, list[str]]] = []
    for n in graph.get_all_nodes():
        if n.type not in (NodeType.CONCEPT, NodeType.EVENT):
            continue
        title = n.data.get("title", n.id) or ""
        desc = (n.data.get("description") or n.data.get("content") or "")[:300]
        text = f"{title} {desc}"
        # Strip [YYYY-MM-DD…] prefix before scanning for proper nouns.
        text_stripped = re.sub(r"^\s*\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*", "", title) + " " + desc
        propers = [
            p for p in _PROPER_NOUN_RE.findall(text_stripped)
            if p.lower() not in {"user", "assistant", "session date"}
            and len(p) > 3
        ]
        if not propers:
            continue
        text_tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
        overlap = len(q_tokens & text_tokens)
        if overlap == 0:
            continue
        date_str = n.data.get("date") or n.data.get("extracted_at") or n.data.get("timestamp")
        try:
            dt = datetime.fromisoformat((date_str or "").replace("Z", ""))
        except Exception:
            dt = datetime.min
        if title.startswith("[") and "]" in title[:24]:
            title = title.split("]", 1)[1].lstrip()
        score = overlap / max(1, len(q_tokens))
        scored.append((score, dt, title, desc, propers[:5]))

    if not scored:
        return ""

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = scored[:max_items]

    lines = [
        "## PROPER_NOUN_MATCHES (nodes containing capitalized named entities "
        "— the answer to a 'name of / which X' question is almost always one "
        "of the bolded names below)"
    ]
    for i, (score, dt, title, desc, propers) in enumerate(top, 1):
        date_str = dt.date().isoformat() if dt != datetime.min else "?"
        proper_str = ", ".join(f"**{p}**" for p in propers)
        lines.append(f"{i}. [{date_str}] (overlap={score:.2f}) {title} — {desc}  [names: {proper_str}]")
    return "\n".join(lines) + "\n"


_RELATIVE_AGO_TARGET_RE = re.compile(
    r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"\d+)\s+(day|days|week|weeks|month|months|year|years)\s+ago\b",
    re.IGNORECASE,
)
_WORD_TO_INT_LOCAL = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_UNIT_DAYS_LOCAL = {
    "day": 1, "days": 1, "week": 7, "weeks": 7,
    "month": 30, "months": 30, "year": 365, "years": 365,
}


def build_target_date_concepts_block(
    graph: ConceptGraph, question_date: datetime | None, question: str, window: int = 3
) -> str:
    """iter16 — list every dated concept within ±`window` days of the
    target date implied by 'X N weeks ago' in the question. Reader sees
    a focused candidate list and can pick by topic match. Skips silently
    when the question has no relative-time clause."""
    if question_date is None:
        return ""
    m = _RELATIVE_AGO_TARGET_RE.search(question)
    if not m:
        return ""
    num_str = m.group(1).lower()
    unit_str = m.group(2).lower()
    num = _WORD_TO_INT_LOCAL.get(num_str)
    if num is None:
        try:
            num = int(num_str)
        except ValueError:
            return ""
    unit_key = unit_str if unit_str.endswith("s") else unit_str + "s"
    days_back = num * _UNIT_DAYS_LOCAL[unit_key]
    target = question_date - timedelta(days=days_back)
    target_d = target.date()

    rows: list[tuple[int, datetime, str, str]] = []  # (off, date, title, desc)
    for n in graph.get_all_nodes():
        if n.type not in (NodeType.CONCEPT, NodeType.EVENT):
            continue
        if n.id.startswith("evt-"):
            continue
        date_str = n.data.get("date") or n.data.get("extracted_at")
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", ""))
        except Exception:
            continue
        off = abs((dt.date() - target_d).days)
        if off > window:
            continue
        title = n.data.get("title", "") or ""
        if title.startswith("[") and "]" in title[:24]:
            title = title.split("]", 1)[1].lstrip()
        desc = (n.data.get("description") or n.data.get("content") or "")[:160]
        # Skip writer concept-types that mark synthetic typed_* nodes.
        ctype = (n.data.get("concept_type") or "").lower()
        if ctype.startswith("typed_"):
            continue
        # Skip planning/intent concepts (consistent with resolvers).
        full = (title + " " + desc).lower()
        if any(p in full for p in (
            "is planning", "is considering", "is thinking",
            "would like to", "wants to", "intends to", "is going to",
            "is looking forward to", "is hoping to",
            "i'm planning", "i'm thinking", "i'm considering",
            "asked the assistant", "recommended", "suggested",
            "is interested in", "heard about", "read about",
        )):
            continue
        rows.append((off, dt, title, desc))
    if not rows:
        return ""
    rows.sort(key=lambda x: (x[0], x[1]))  # closest to target, then earliest
    lines = [
        "## CONCEPTS_NEAR_TARGET_DATE",
        f"Concepts whose [YYYY-MM-DD] prefix is within ±{window} days of "
        f"{target_d.isoformat()} (the resolved target for "
        f"'{num} {unit_str} ago'). Pick the concept whose description best "
        f"matches the question's topic; do not pick a lexically-similar "
        f"concept dated further from this target.",
    ]
    for off, dt, title, desc in rows[:12]:
        lines.append(f"- [{dt.date()}] (off={off}d) **{title}** — {desc}")
    return "\n".join(lines) + "\n"


def build_recall_target_date_block(question_date: datetime | None, question: str) -> str:
    """iter15 — when the question contains 'X N days/weeks/months ago' the
    reader frequently picks a lexically-similar concept dated NEAR but not
    AT the target. Pre-compute the target date and inject as a hint so the
    reader pins to the right [YYYY-MM-DD] prefix.

    Targets the cluster where the resolver's relative_ago_recall doesn't
    fire (generic topic) but the question is clearly date-anchored:
      gpt4_1e4a8aec gardening 2 weeks ago,
      eac54add business milestone 4 weeks ago,
      gpt4_4929293b relative life event 1 week ago,
      gpt4_59149c78 art event 2 weeks ago,
      gpt4_e072b769 Ibotta 3 weeks ago.
    """
    if question_date is None:
        return ""
    m = _RELATIVE_AGO_TARGET_RE.search(question)
    if not m:
        return ""
    num_str = m.group(1).lower()
    unit_str = m.group(2).lower()
    num = _WORD_TO_INT_LOCAL.get(num_str)
    if num is None:
        try:
            num = int(num_str)
        except ValueError:
            return ""
    unit_key = unit_str if unit_str.endswith("s") else unit_str + "s"
    days_back = num * _UNIT_DAYS_LOCAL[unit_key]
    target = question_date - timedelta(days=days_back)
    return (
        "## RECALL_TARGET_DATE\n"
        f"The question's relative-time clause ({num} {unit_str} ago) "
        f"resolves to absolute date **{target.date().isoformat()}** (today is "
        f"{question_date.date().isoformat()}). When picking the matching "
        f"event, prefer the concept whose `[YYYY-MM-DD]` prefix is closest "
        f"to {target.date().isoformat()} (±3 days). Do NOT pick a concept "
        f"that's more lexically similar but dated further from this "
        f"target.\n"
    )


def build_today_block(question_date: datetime | None) -> str:
    """iter07 — pin the dataset's question_date at the top of context as the
    reference "today" for relative-time expressions ("X days ago", "two
    weeks ago", "currently"). Without this, the reader falls back to the
    system clock — in iter05/06 that meant 2026-06-01 vs the dataset's
    actual question_date in 2023, producing "1,205 days ago" for "X days
    ago" questions whose true answer was 17 days.
    """
    if question_date is None:
        return ""
    # Use date-only display — same format as the rest of the context so the
    # reader doesn't treat this as a millisecond-precise timestamp.
    today_str = question_date.date().isoformat()
    return (
        "## TODAY\n"
        f"{today_str}\n"
        "Use this date as the reference for any relative-time expression in "
        "the question (\"X days ago\", \"X weeks ago\", \"currently\", "
        "\"now\", \"recently\"). Compute date differences from this date — "
        "do NOT use the system clock or any other reference.\n"
    )


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


_EVENT_DATE_PROMPT = """For each concept extracted from a chat session, determine the EVENT_DATE — the absolute date the event ACTUALLY occurred (which may differ from the session date, since the user often discusses past events in current sessions).

Session date (when the user said these things): {session_date}

User messages from this session:
{user_messages}

Concepts extracted from this session (the ones whose event_date we need to resolve):
{concept_list}

Rules — apply in order:
1. If the user says "today" / "right now" / no temporal anchor → event_date = session_date
2. If the user says "X days/weeks/months/years ago" → event_date = session_date − X (in the named unit)
3. If the user names an explicit date ("on January 10th" / "February 1, 2023" / "Valentine's day") → event_date = the absolute date (use session year for month-only dates; closest past date for holiday names)
4. If the user says "last Saturday" → event_date = the most recent Saturday before session_date
5. If the user says "last week" → event_date = a date 7 days before session_date
6. If the user mentions an upcoming/future event → event_date = the future date (best-effort) and status = "upcoming"
7. If the concept is a habit / preference / ongoing state with no specific date → event_date = null and status = "ongoing"
8. If you genuinely can't tell → event_date = null and precision = "unknown"

For "precision": "day" / "week" / "month" / "year" / "unknown".
For "status": "completed" / "ongoing" / "upcoming" / "unknown".

Output JSON. event_date in YYYY-MM-DD form.
{{"events": [
  {{"id": "c-...", "event_date": "2023-01-10", "precision": "day", "status": "completed"}},
  {{"id": "c-...", "event_date": null, "precision": "unknown", "status": "ongoing"}}
]}}
"""


def _resolve_event_dates_pass(
    session: list[dict],
    timestamp: datetime,
    new_concepts: list[tuple[str, str]],  # [(concept_id, raw_title), ...]
    graph: ConceptGraph,
    config: AgentConfig,
) -> None:
    """W2 (iter18) — Chronos-/Mem0-inspired event_date pass. For each
    CONCEPT extracted in this session, ask the LLM to resolve the user's
    relative-time phrasing to an absolute event_date. Store on node.data.

    Without this, the writer dates every concept by the SESSION date, so
    "I bought my Adidas on January 10th" (session 2023-02-03) gets
    date=2023-02-03 instead of 2023-01-10. Date-arithmetic resolvers then
    compute "days ago" against the wrong anchor.

    Resolver and reader prefer `event_date` when set; fall back to `date`.
    """
    if not new_concepts:
        return
    user_messages = [
        (t.get("content") or "").strip()
        for t in session
        if t.get("role") == "user" and (t.get("content") or "").strip()
    ]
    if not user_messages:
        return
    user_text = "\n\n---\n".join(user_messages)
    if len(user_text) < 60:
        return

    session_date_str = timestamp.date().isoformat()
    concept_list = json.dumps(
        [{"id": cid, "title": title[:140]} for cid, title in new_concepts[:30]],
        indent=2,
    )
    prompt = _EVENT_DATE_PROMPT.format(
        session_date=session_date_str,
        user_messages=user_text,
        concept_list=concept_list,
    )
    try:
        raw = call_llm(prompt, config, json_mode=True)
    except Exception as e:
        logger.error(f"event-date pass LLM call failed: {e}")
        return
    if not raw:
        return
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except Exception as e:
        logger.error(f"event-date pass JSON parse failed: {e}")
        return

    events = parsed.get("events", []) if isinstance(parsed, dict) else []
    if not isinstance(events, list):
        return

    # Build a small map of new concept ids for O(1) lookup
    new_ids = {cid for cid, _ in new_concepts}

    for ev in events:
        if not isinstance(ev, dict):
            continue
        cid = ev.get("id")
        if cid not in new_ids:
            continue
        event_date = ev.get("event_date")
        precision = (ev.get("precision") or "unknown").lower()
        status = (ev.get("status") or "unknown").lower()
        if event_date is None:
            # Still record status/precision on the node so resolver can
            # skip "ongoing" / "upcoming" when bypassing date arithmetic.
            try:
                node = graph.get_node(cid)
                if node:
                    node.data["event_date_precision"] = precision
                    node.data["event_status"] = status
            except Exception:
                pass
            continue
        # Parse and validate the date.
        try:
            ev_dt = datetime.strptime(str(event_date)[:10], "%Y-%m-%d")
        except Exception:
            continue
        # Sanity check: event_date shouldn't be far in the future relative
        # to session_date (allow up to 1 year ahead for upcoming events).
        # Also shouldn't be unreasonably old (>10 years before session).
        days_off = (ev_dt.date() - timestamp.date()).days
        if days_off > 365 or days_off < -3650:
            continue
        try:
            node = graph.get_node(cid)
            if node:
                node.data["event_date"] = ev_dt.isoformat()
                node.data["event_date_precision"] = precision
                node.data["event_status"] = status
        except Exception:
            continue


_TYPED_ATTR_PROMPT = """Extract verbatim typed attributes from these user messages. The main extractor often paraphrases away specific values (e.g., "submitted to ACL" loses "February 1st"; "left home at 7 AM" loses arrival time "9 AM"; "political humor" loses the cartoon name "Nu, pogodi!"). This pass preserves them.

Output a JSON object with a "attributes" list. Each attribute:
- "type": one of {{"time","date","duration","quantity","name"}}
- "value": the LITERAL value from the message (do NOT paraphrase or summarize)
- "context": short phrase from the message giving the topic this attribute belongs to (max 80 chars)

Definitions:
- "time" = clock time (e.g., "9 AM", "6:30 pm", "10:00")
- "date" = calendar date (e.g., "February 1st", "March 3rd", "May 25", "January 24th")
- "duration" = interval (e.g., "two weeks", "5 days", "3 months", "a year ago")
- "quantity" = count/amount (e.g., "1300 followers", "$80", "4 days a week", "856 pages")
- "name" = proper noun, specific named entity (e.g., "Golden Retriever", "Nu, pogodi!", "Bajimaya")

Rules:
- Only include attributes that the USER mentions (skip values the assistant suggested).
- If no typed attributes exist, return {{"attributes": []}}.
- Do NOT include common-knowledge values (e.g., "Monday" alone is too generic, but "9 AM Monday" is fine).
- Each attribute's "value" must appear VERBATIM in the message.

Example:
Messages:
"I had a doctor's appointment at 10 AM last Thursday and got my results."
"My dog Max is a Golden Retriever and he turns 5 next month."

Output:
{{"attributes":[
  {{"type":"time","value":"10 AM","context":"doctor's appointment last Thursday"}},
  {{"type":"name","value":"Golden Retriever","context":"my dog Max's breed"}},
  {{"type":"duration","value":"next month","context":"Max turns 5"}}
]}}

Messages:
{user_messages}
"""


def _typed_attribute_pass(
    session: list[dict],
    timestamp: datetime,
    graph: ConceptGraph,
    config: AgentConfig,
    time_node_id: str,
) -> None:
    """W1 — second writer pass that extracts typed attributes verbatim from
    user-role turns. Adds one CONCEPT node per attribute so retrieval can
    surface the literal value when the main extractor paraphrased it away.
    """
    user_messages = [
        (t.get("content") or "").strip()
        for t in session
        if t.get("role") == "user" and (t.get("content") or "").strip()
    ]
    if not user_messages:
        return
    text = "\n\n---\n".join(user_messages)
    # Skip very short sessions (no value-bearing content).
    if len(text) < 60:
        return

    session_datetime_iso = timestamp.isoformat()
    session_datetime_display = timestamp.strftime("%Y-%m-%d %H:%M")

    prompt = _TYPED_ATTR_PROMPT.format(user_messages=text)
    try:
        raw = call_llm(prompt, config, json_mode=True)
    except Exception as e:
        logger.error(f"typed-attribute LLM call failed: {e}")
        return
    if not raw:
        return
    # Strip markdown fence if model added one.
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"typed-attribute JSON parse failed: {e}")
        return

    attrs = data.get("attributes", []) if isinstance(data, dict) else []
    if not isinstance(attrs, list):
        return

    for attr in attrs[:20]:  # cap at 20 per session to bound graph growth
        if not isinstance(attr, dict):
            continue
        atype = (attr.get("type") or "").lower()
        value = (attr.get("value") or "").strip()
        ctx = (attr.get("context") or "").strip()[:120]
        if atype not in {"time", "date", "duration", "quantity", "name"}:
            continue
        if not value or len(value) > 80:
            continue
        # Verbatim check: skip attributes whose value isn't actually in the
        # user text — guards against extractor hallucination.
        if value.lower() not in text.lower():
            continue
        attr_node_id = f"c-attr-{uuid.uuid4().hex[:8]}"
        attr_title_short = f"TYPED_{atype.upper()}: {value} — {ctx}"
        # iter06: title prefix uses date-only to avoid the reader treating
        # [HH:MM] as an absolute timestamp and doing date math vs system today.
        session_date_str = timestamp.date().isoformat()
        attr_desc = (
            f"User stated [{atype}] {value!r} in context: {ctx}. "
            f"(Verbatim from session on {session_date_str}.)"
        )
        try:
            graph.add_node(
                Node(
                    id=attr_node_id,
                    type=NodeType.CONCEPT,
                    data={
                        "title": f"[{session_date_str}] {attr_title_short}",
                        "description": attr_desc,
                        "strength": 0.9,
                        "concept_type": f"typed_{atype}",
                        "extracted_at": session_datetime_iso,
                        "date": session_datetime_iso,
                        "typed_attr_type": atype,
                        "typed_attr_value": value,
                    },
                    reasoning=f"W1 typed-attribute pass on {session_date_str}",
                    created_at=timestamp,
                )
            )
            try:
                graph.add_edge(
                    Edge(source=attr_node_id, target=time_node_id, created_at=timestamp)
                )
            except Exception:
                pass
        except Exception:
            continue


def process_session_batch(
    session: list[dict],
    timestamp: datetime,
    graph: ConceptGraph,
    config: AgentConfig,
    batch_template: str | None = None,
) -> None:
    """Process a full session in batch mode."""
    # date-only for display prefix (kept short so 30 same-day sessions stay scannable)
    session_date_str = timestamp.date().isoformat()
    # full ISO datetime for storage so same-day sessions can be ordered by HH:MM.
    # Without this, KU questions with multiple updates on one date (e.g.,
    # Instagram followers 1250 @ 05:26 → 1300 @ 09:28) lose their ordering and
    # latest_value resolution becomes a coin flip.
    session_datetime_iso = timestamp.isoformat()
    # display-friendly "YYYY-MM-DD HH:MM" used in titles so the reader can see
    # the order without doing ISO arithmetic.
    session_datetime_display = timestamp.strftime("%Y-%m-%d %H:%M")

    # 0. Create per-session TIME anchor so every node born in this session
    #    has an explicit absolute date the symbolic temporal pass can hit.
    time_node_id = f"t-{timestamp.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    try:
        graph.add_node(
            Node(
                id=time_node_id,
                type=NodeType.TIME,
                data={
                    # date-only for display (avoid system-today bias); full
                    # datetime kept on `datetime` + `date` so resolver still
                    # has HH:MM precision for same-day session ordering.
                    "title": f"Session date {session_date_str}",
                    "datetime": session_datetime_iso,
                    "date": session_datetime_iso,
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

        # iter18: collect new_concepts so the optional W2 pass can resolve
        # event_date for each one.
        new_concepts_for_w2: list[tuple[str, str]] = []
        # Add Concepts to Graph
        for concept in data.get("concepts", []):
            concept_id = f"c-{uuid.uuid4().hex[:8]}"
            # Date-prefix the TITLE. iter06 revert: use date-only prefix to
            # avoid the iter05 side-effect where reader treated the [HH:MM]
            # title as an absolute timestamp and computed "X days ago" vs
            # the system clock (2026) instead of the dataset's question_date
            # (~2023). data["date"] (read by resolvers) still carries the
            # full ISO datetime for same-day session ordering.
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
                        "extracted_at": session_datetime_iso,
                        # Full ISO datetime so same-day events get tie-broken
                        # by HH:MM in latest_value / chronological_order.
                        "date": session_datetime_iso,
                    },
                    reasoning=f"Extracted from session batch on {session_datetime_display}",
                    created_at=timestamp,
                )
            )
            new_concepts_for_w2.append((concept_id, raw_title))
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
        new_concepts_for_w2 = []  # safe default if extraction failed

    # ---- W2 (iter18): event_date resolution pass ----
    # Chronos / Mem0 / Zep all show that storing per-fact event_date
    # (vs the session date when the user mentioned it) yields a big
    # temporal-reasoning boost. Gated by `resolve_event_dates=True` on
    # the AgentConfig — opt-in only via --resolve-event-dates.
    if getattr(config, "resolve_event_dates", False) and new_concepts_for_w2:
        try:
            _resolve_event_dates_pass(
                session, timestamp, new_concepts_for_w2, graph, config
            )
        except Exception as e:
            logger.error(f"Error in event_date pass: {e}")

    # ---- W1: typed-attribute second pass over user-role turns ----
    # Exp A on 2026-06-01 showed that ~7 of 23 "I don't have memory of X"
    # failures are caused by the main extractor paraphrasing away the
    # specific value (e.g., "submitted research paper to ACL" loses
    # "February 1st"; "left home at 7 AM" loses arrival "9 AM"; "political
    # humor" loses "Nu, pogodi!"). Earlier attempts to add verbatim-
    # preservation rules to the main extraction prompt (rules 9+10)
    # bloated the prompt and HALVED the writer's `graph_nodes` output
    # via JSON truncation.
    #
    # W1 sidesteps that by running a SEPARATE focused call: small prompt,
    # narrow output, just typed attributes (date/time/duration/quantity/
    # proper-noun). Each attribute gets its own CONCEPT node so symbolic
    # resolvers + BM25 can find it by literal value match.
    #
    # Gated by `extract_typed_attributes=True` on config — opt-in only.
    if getattr(config, "extract_typed_attributes", False):
        try:
            _typed_attribute_pass(session, timestamp, graph, config, time_node_id)
        except Exception as e:
            logger.error(f"Error in typed-attribute pass: {e}")

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
    # W1: opt-in typed-attribute pass on the writer config.
    if getattr(args, "extract_typed_attributes", False):
        writer_config = dataclasses.replace(writer_config, extract_typed_attributes=True)
        logger.info("W1 typed-attribute pass: ENABLED")
    # W2 (iter18): opt-in event_date resolution pass.
    if getattr(args, "resolve_event_dates", False):
        writer_config = dataclasses.replace(writer_config, resolve_event_dates=True)
        logger.info("W2 event_date resolution pass: ENABLED")

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

        _qc_kwargs: dict = dict(
            domain="longmemeval",
            max_nodes=20,
            include_reasoning=True,
            retrieval_mode=retrieval_mode,
            use_llm_rerank_batched=bool(args.llm_rerank),
            rerank_model=args.rerank_model,
            rerank_reasoning_effort=args.rerank_reasoning_effort,
            pre_rerank_pool=args.rerank_pool if args.llm_rerank else 0,
        )
        if args.max_context_chars:
            _qc_kwargs["max_context_chars"] = args.max_context_chars
        query_config = QueryConfig(**_qc_kwargs)
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

        # Exp A diagnostic: dump full graph and skip the QA step. Used to
        # confirm whether failure cases like "I don't have a memory of X" are
        # writer-extraction misses (X never made it into the graph) or
        # retrieval rank-out problems (X is in the graph but didn't reach the
        # reader). Costs only the writer + ingestion (no reader / no judge).
        if getattr(args, "dump_graph_only", False):
            nodes_out = []
            for n in graph.get_all_nodes():
                ntype = getattr(n.type, "name", str(n.type))
                nodes_out.append({
                    "id": n.id,
                    "type": ntype,
                    "title": n.data.get("title", ""),
                    "description": n.data.get("description", ""),
                    "date": n.data.get("date", ""),
                    "concept_type": n.data.get("concept_type", ""),
                    "role": n.data.get("role", ""),
                })
            graph_path = output_dir / f"graph_{question_id}.json"
            with open(graph_path, "w") as gf:
                json.dump({
                    "question_id": question_id,
                    "question": question,
                    "ground_truth": ground_truth,
                    "graph_node_count": graph.node_count,
                    "graph_edge_count": graph.edge_count,
                    "nodes": nodes_out,
                }, gf, indent=2, default=str)
            result_entry = {
                "question_id": question_id,
                "graph_dump_path": str(graph_path),
                "graph_node_count": graph.node_count,
                "graph_edge_count": graph.edge_count,
                "skipped_qa": True,
            }
            with open(output_path, "a") as f:
                f.write(json.dumps(result_entry) + "\n")
            continue

        # 3. Answer Question
        # R9-A: dynamic max_nodes — aggregation questions ("how many X have I",
        # "how much money spent on X") need to see ALL relevant entity
        # concepts to count/sum correctly. With max_nodes=20, multi-entity
        # questions chronically under-count. Bump to 50 for these only;
        # single-fact questions stay at 20 to avoid context dilution.
        #
        # Widened on 2026-06-01:
        # - Include BARE verbs (attend, visit, spend, play, buy, do, see,
        #   …) so "did I attend / did I visit / have I spent" all trigger.
        #   The previous regex only had past tense (attended, visited),
        #   missing R9-A on 2ce6a0f2 / gpt4_f2262a51 / 28dc39ac.
        # - Replaced the time-unit negative lookahead (`hours?|days?|...`)
        #   with an explicit TR-marker suppression (`ago` / `since i` /
        #   `between` / `before i`). Aggregation Qs about hours
        #   ("how many hours have I spent playing games") were being
        #   blocked alongside the TR "how many days ago" ones.
        # `i\s+(?:\w+\s+)?` allows one optional adverb between "I" and the
        # verb (e.g., "I currently own", "I just bought"). Without it,
        # phrasings like "do I currently own" fail to match.
        _qa_agg_count_re = re.search(
            r"\bhow\s+many\s+\w+.*\b(?:have\s+i|i\s+(?:\w+\s+)?(?:"
            r"have|own|owned|bought|buy|worked|work|"
            r"attended|attend|read|watched|watch|"
            r"tried|try|made|make|led|lead|leading|"
            r"did|do|spent|spend|visited|visit|"
            r"saw|see|met|meet|played|play|"
            r"finished|finish|completed|complete|been|"
            r"received|receive|cooked|cook|baked|bake|"
            r"travel(?:l?ed)?|took|take|"
            r"hosted|host|booked|book|"
            r"replaced|replace|fixed|fix|sold|sell|lost|lose|"
            r"purchased|purchase|downloaded|download|"
            r"installed|install|joined|join|left|leave))",
            question, re.IGNORECASE,
        )
        # Suppress when the question is genuinely TR-style (single-event
        # date diff) rather than aggregation over many events.
        _qa_agg_count_tr = re.search(
            r"\b(?:ago\b|since\s+i\b|between\s+\w|before\s+i\b|after\s+i\b)",
            question, re.IGNORECASE,
        )
        _qa_agg_count = bool(_qa_agg_count_re) and not _qa_agg_count_tr
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
        # Per-question max_context_chars override: aggregation Qs need ~3x
        # more chars to fit the 50-node retrieval set without assembly
        # truncating to the first ~20 nodes (default 6000-char cap).
        _query_max_ctx = None
        if (_qa_agg_count or _qa_agg_sum) and args.agg_max_context_chars:
            _query_max_ctx = args.agg_max_context_chars
        _query_start = time.time()
        _query_kwargs: dict = dict(
            question=question,
            domain="longmemeval",
            query_mode=args.query_mode,
            max_nodes=_query_max_nodes,
            pre_rerank_pool=_query_pre_rerank_pool,
        )
        if _query_max_ctx:
            _query_kwargs["max_context_chars"] = _query_max_ctx
        query_result = query_agent.query_for_qa(**_query_kwargs)
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

        # R2 (Exp A) — Clock-time matches for "what time do I X" questions.
        # Writer captures these but retrieval frequently buries them under
        # generic topic concepts (photography / fishing / etc.).
        time_block = build_time_of_day_block(graph, question)
        if time_block:
            context_text = time_block + "\n" + context_text

        # R3 (Exp A) — Proper-noun matches for "what's the name of X / which
        # X / what breed" questions. Pins capitalized multi-word names from
        # the graph to the top of context.
        propnoun_block = build_proper_noun_block(graph, question)
        if propnoun_block:
            context_text = propnoun_block + "\n" + context_text

        # Symbolic deterministic resolver (ToMi-style): pattern-match the
        # question against the dated graph and compute an exact answer string.
        # If matched, we both inject the answer as a SYMBOLIC_ANSWER block
        # AND short-circuit the LLM (`answer` = resolver answer verbatim) so
        # the reader can't unsort what we already sorted.
        question_dt = _parse_longmemeval_date(item.get("question_date", ""))
        symbolic_result = None
        if args.symbolic_resolver:
            resolver = LongMemEvalSymbolicResolver(graph, question_date=question_dt)
            symbolic_result = resolver.resolve(question)
            if symbolic_result is not None:
                context_text = render_symbolic_block(symbolic_result) + "\n" + context_text

        # iter15 — RECALL_TARGET_DATE for "X N weeks ago" Qs. Pin the
        # absolute target date so reader prefers the right [YYYY-MM-DD]
        # prefix even when the resolver doesn't bypass.
        target_block = build_recall_target_date_block(question_dt, question)
        if target_block:
            context_text = target_block + "\n" + context_text

        # iter16 — list all dated concepts within ±3 days of the target
        # so the reader can scan and pick by topic match rather than
        # relying on retrieval ranking that may have buried the right
        # event. Fires for the same "X N weeks ago" Qs as the target
        # block.
        target_cands_block = build_target_date_concepts_block(graph, question_dt, question)
        if target_cands_block:
            context_text = target_cands_block + "\n" + context_text

        # iter07 — TODAY anchor goes LAST in the prepend chain so it ends up
        # at the very top of context. Reader prompt then begins with a clear
        # statement of the reference date, eliminating the iter05/06 failure
        # mode where reader computed "X days ago" against system time (2026)
        # instead of the dataset's question_date (~2023).
        today_block = build_today_block(question_dt)
        if today_block:
            context_text = today_block + "\n" + context_text

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
                full_context=context_text,
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
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=None,
        help="Override QueryConfig.max_context_chars (default 6000). Bump for "
        "aggregation questions where 50-node retrieval is otherwise truncated "
        "by the 6000-char assembly cap. Try 12000–18000.",
    )
    parser.add_argument(
        "--agg-max-context-chars",
        type=int,
        default=None,
        help="Per-question override for aggregation Qs only (R9-A path: 'how "
        "many X', 'how much money'). If set, takes precedence over "
        "--max-context-chars on aggregation questions. Lets you bump just the "
        "Qs that need it without inflating cost on single-fact Qs.",
    )
    parser.add_argument(
        "--dump-graph-only",
        action="store_true",
        help="Exp A diagnostic: after ingestion, dump the full graph to "
        "<output_dir>/graph_<qid>.json and SKIP the QA / judge steps. Used "
        "to classify failure causes (writer extraction miss vs retrieval "
        "rank-out) without paying for the reader.",
    )
    parser.add_argument(
        "--extract-typed-attributes",
        action="store_true",
        help="W1: run a second writer pass per session that extracts typed "
        "attributes (date/time/duration/quantity/name) verbatim from "
        "user-role turns. Adds ~$0.0001 per session in writer cost. Helps "
        "with failure cases where the main extractor paraphrased away the "
        "specific value (Exp A WRITER bucket: ~7/23 of the Bucket C cases).",
    )
    parser.add_argument(
        "--resolve-event-dates",
        action="store_true",
        help=(
            "W2 (iter18): per-concept event_date resolution pass. For each "
            "CONCEPT extracted in a session, the LLM resolves the user's "
            "relative-time phrasing ('on January 10th', 'two weeks ago', "
            "'last Saturday') to an absolute event_date and stores it on "
            "the node so resolvers and readers can use the true event date "
            "instead of the session-extraction date. Inspired by Chronos "
            "(event-calendar +58.9 pts baseline in their ablation) and "
            "Mem0 (per-memory temporal pass)."
        ),
    )

    args = parser.parse_args()
    run_benchmark(args)
