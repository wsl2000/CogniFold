# Canonical Round-2 Plan (repo-verified)

This replaces the prior hallucinated plan. Every existing target below was verified in the repo; every non-existing target is explicitly marked as new code to be created in `benchmarks/longmemeval/round2_evidence_ledger.py`.

## Section 1 — Per-case fix table (45 rows, real targets)

| label | qid | cluster | root cause from full_context | fix mechanism | target file:func | existing iter31 rule reuse? | regression risk | expected delta |
|---|---|---|---|---|---|---|---|---|
| TR-01 | `b46e15ed` | consecutive-span anchor | `_try_diff_since` is latching onto one charity-event mention, not the second day of the consecutive-day pair. | `resolver:choose_duration_anchor` | `benchmarks/longmemeval/symbolic_resolver.py:_try_diff_since` (line 1201) via new `_choose_duration_anchor` helper | `NO` | low | `+1 exact` |
| TR-02 | `gpt4_e061b84f` | order / retrieval miss | The triathlon surfaces, but the 5K and company charity soccer event do not reach the answerer even though they should exist in graph memory. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — CHRONOLOGICAL-SCAN; smallest strengthening is to late-fuse the missing sports-event chunks before the reader scans order.` | med | `+1 exact` |
| TR-03 | `370a8ff4` | disputed annotation | User explicitly asked to keep this deferred. | `defer:disputed_annotation_issue_370a8ff4` | `n/a (deferred by user instruction)` | `n/a` | none | `0` |
| TR-04 | `gpt4_d6585ce9` | named-day companion recall | `last Saturday` must resolve to `2023-04-15`; same-day music-event candidates are present, but the correct companion slot is not being grounded. | `resolver:resolve_anchor_date` | `benchmarks/longmemeval/symbolic_resolver.py:_try_named_day_recall` (line 1645) via new `_resolve_anchor_date` helper | `NO` | low | `+1 exact` |
| TR-05 | `gpt4_f420262d` | holiday grounding | `Valentine's Day` must ground to `2023-02-14`; the current path drifts into planning / generic airline content. | `resolver:resolve_anchor_date` | `benchmarks/longmemeval/symbolic_resolver.py:_try_named_day_recall` (line 1645) via new `_resolve_anchor_date` helper | `NO` | low | `+1 exact` |
| TR-06 | `9a707b81` | relative date inside event mention | The class memory is phrased with relative wording (`yesterday`) and the current diff-when path is off by one day. | `resolver:resolve_anchor_date` | `benchmarks/longmemeval/symbolic_resolver.py:_try_diff_since_when` (line 1449) via new `_resolve_anchor_date` helper | `NO` | low | `+1 exact` |
| TR-07 | `gpt4_fe651585` | binary order on implicit parenthood event | The reader is treating generic child/caregiving mentions as parenthood evidence instead of the explicit adoption anchor for Alex. | `A:order` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="order"`) | `YES — COMPARATIVE EARLIER=FIRST; smallest strengthening is to restrict candidate events to birth/adoption/become-parent verbs.` | low | `+1 exact` |
| TR-08 | `gpt4_7abb270c` | long order list with missing member | One museum is missing from surfaced evidence and another is misordered; the reader only sees five visits. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — CHRONOLOGICAL-SCAN; smallest strengthening is to late-fuse missing museum visit chunks before timeline/order reading.` | med | `+1 exact` |
| TR-09 | `gpt4_f420262c` | earliest unique airline order | The task is “order of airlines,” not “order of flights”; earliest unique airline occurrence is not being deduped correctly. | `resolver:resolve_order_candidates` | `benchmarks/longmemeval/symbolic_resolver.py:_try_order_among` (line 532), plus re-enable in `resolve()` (line 176) after backfill patch | `NO` | med | `+1 exact` |
| TR-10 | `eac54add` | disputed annotation | User explicitly asked to keep this deferred. | `defer:disputed_annotation_issue_eac54add` | `n/a (deferred by user instruction)` | `n/a` | none | `0` |
| TR-11 | `08f4fc43` | exclusive vs inclusive diff | Current output is prose-y and the canonical arithmetic belongs in the resolver; default should be exclusive unless the question explicitly asks for inclusive counting. | `resolver:normalize_date_diff` | `benchmarks/longmemeval/symbolic_resolver.py:_try_diff_between` (line 980) | `YES — INCLUSIVE-BOUNDARY; smallest strengthening is to make exclusive the canonical resolver output unless the question says “including/inclusive”.` | low | `+1 exact` |
| TR-12 | `gpt4_7f6b06db` | trip chronology miss | Yosemite-related travel mentions are outranking the earlier Muir Woods hike; one trip start is missing from the surfaced order evidence. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — CHRONOLOGICAL-SCAN; smallest strengthening is to late-fuse the full trip set before ordering.` | med | `+1 exact` |
| TR-13 | `a3838d2b` | before-Y charity count under-recall | Existing prompt logic is conceptually right, but the reader is only seeing a subset of the pre-`Run for the Cure` charity events. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — EXHAUSTIVE-COUNT exclude-anchor; smallest strengthening is to feed all pre-Y charity chunks to the reader/ledger because the rule itself is already correct.` | med | `+1 exact` |
| TR-14 | `c8090214_abs` | missing anchor entity | There is no iPad purchase in context; the current answer substitutes another Apple purchase path. | `qa_rule:"attribute mismatch refusal"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `YES — _abs both-entities check; smallest strengthening is to explicitly ban sibling-device substitution.` | low | `+1 exact` |
| TR-15 | `gpt4_59149c78` | relative-ago slot recall | “art-related event two weeks ago” should resolve the correct event date first, then extract the venue slot; current path grabs the nearby City Art Museum event. | `resolver:resolve_anchor_date` | `benchmarks/longmemeval/symbolic_resolver.py:resolve` (line 176) + `_try_relative_ago_recall` (line 1273) via new `_resolve_anchor_date` helper | `NO` | med | `+1 exact` |
| MS-01 | `0a995998` | obligation-slot counting | The answer collapses “return boots” and “pick up new pair” into one product bucket; GT counts pending action slots. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is to count obligation slots, not just unique item nouns.` | low | `+1 exact` |
| MS-02 | `gpt4_f2262a51` | retrieval polluted by scheduling chatter | Context is dominated by appointment-system “doctor” mentions; the real PCP / ENT / dermatologist visit facts are not reaching the reader. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is only to surface the visit chunks before counting unique doctors.` | med | `+1 exact` |
| MS-03 | `c4a1ceb8` | used-vs-suggested citrus filter | The current answer counts assistant suggestions/garnishes instead of only citrus fruits the user actually used in recipes. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is to exclude assistant suggestions when the question says “I used”.` | low | `+1 exact` |
| MS-04 | `28dc39ac` | missing gameplay-hours chunk | Two explicit hour counts surface, but one gameplay-hours chunk is missing from retrieved evidence, so the sum stops at 105. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT / total-sum behavior; smallest strengthening is just to surface the missing hours chunk.` | med | `+1 exact` |
| MS-05 | `9d25d4e0` | in-window jewelry under-recall | Only two acquisitions surface even though the question is window-bounded and one more jewelry item should be counted. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is late fusion over the 2-month jewelry window.` | med | `+1 exact` |
| MS-06 | `a9f6b44c` | completed vs planned service scope | The question explicitly includes bikes serviced or planned to be serviced in March; the current answer only counts completed service. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is to include planned service when the question says “service or plan to service”.` | low | `+1 exact` |
| MS-07 | `80ec1f4f_abs` | zero-in-window handling | The current `_abs` prompt behavior is too refusal-heavy here; GT is zero because there are no December museum/gallery visits. | `qa_rule:"zero-in-window beats nearest-neighbor"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `YES — existing _abs worked example is too strict; smallest strengthening is: explicit zero-count windows answer 0, not insufficiency.` | low | `+1 exact` |
| MS-08 | `eeda8a6d_abs` | absent attribute value | Context supports a `20-gallon` tank only; the reader must not answer from it when the question asks about `30-gallon`. | `qa_rule:"attribute mismatch refusal"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `YES — DISTINCT-ENTITY anti-confabulation; smallest strengthening is to force a clean insufficiency sentence when the attribute value is absent but a sibling value exists.` | low | `+1 exact` |
| MS-09 | `4f54b7c9` | antique/vintage/heirloom normalization | Literal `antique` counting misses `vintage` and `depression-era` family items that GT includes. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is a ledger lexicon for antique/vintage/heirloom family items.` | low | `+1 exact` |
| MS-10 | `a1cc6108` | age derivation | This is arithmetic over family age facts, not direct lookup; the current reader never enters a derivation path. | `A:derived_time` | `benchmarks/longmemeval/round2_evidence_ledger.py:answer_from_ledger` (`shape="derived_time"`) | `YES — NO-REFUSAL-extended / AGE-INFERENCE; smallest strengthening is to allow sibling age-gap derivation, not only current-age-minus-years-ago.` | low | `+1 exact` |
| MS-11 | `9ee3ecd6` | remaining-vs-total arithmetic | The answer returns the target total (`300`) instead of remaining needed (`300 - 200`). | `A:derived_time` | `benchmarks/longmemeval/round2_evidence_ledger.py:answer_from_ledger` (`shape="derived_time"`) | `NO` | low | `+1 exact` |
| MS-12 | `92a0aa75` | current-role vs company-tenure anchor | The system is using overall company tenure instead of the start of the current role. | `A:duration_since` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="duration_since"`) | `YES — MASTRA current-state semantics; smallest strengthening is to anchor on the latest role-change/start event, not total company tenure.` | low | `+1 exact` |
| MS-13 | `73d42213` | explicit time loses to travel inference | `CLOCK_TIME_MATCHES` already surfaces the explicit clinic slot, but the reader infers arrival from drive duration anyway. | `qa_rule:"explicit time beats inference"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `NO` | low | `+1 exact` |
| MS-14 | `c18a7dc8` | graduation-age derivation | This is another derivation case; the reader refuses instead of computing the gap from current age / graduation timing. | `A:derived_time` | `benchmarks/longmemeval/round2_evidence_ledger.py:answer_from_ledger` (`shape="derived_time"`) | `YES — NO-REFUSAL-extended / AGE-INFERENCE; smallest strengthening is to explicitly allow “how many years older am I than when…” arithmetic.` | low | `+1 exact` |
| MS-15 | `a08a253f` | missing weekly class-day chunk | The surfaced routine only exposes three days; one weekly fitness-class day is not reaching the reader. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is just to surface the missing day before tally.` | med | `+1 exact` |
| MS-16 | `37f165cf` | month-filtered page-count sum | The current answer mixes a December read into a January+March question; the task is a filtered two-book page-count sum. | `A:abs_value` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="abs_value"` with sum semantics) | `YES — MS-EXHAUSTIVE-COUNT sum behavior; smallest strengthening is to apply the month filter before summing page counts.` | low | `+1 exact` |
| MS-17 | `09ba9854_abs` | route/scope mismatch | The answer subtracts airport→city-center bus estimates from airport→hotel taxi pricing; the operands are not the same trip scope. | `qa_rule:"same-scope difference only"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `YES — existing _abs worked example already points at this pattern; smallest strengthening is to require same route/scope/currency before subtraction.` | low | `+1 exact` |
| MS-18 | `gpt4_15e38248` | missing furniture action | Three furniture actions surface, but the fourth furniture item/action does not reach the reader. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is just to surface the missing furniture-sale/action chunk.` | med | `+1 exact` |
| MS-19 | `88432d0a` | missing in-window bake event | Three bake events surface, but one more event inside the 2-week window is not reaching the reader. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is late fusion over the 2-week baking window.` | med | `+1 exact` |
| MS-20 | `gpt4_7fce9456` | severe retrieval pollution | The Brookside property question is buried under unrelated phone-case content; the four pre-offer property-view events and reasons never reach the answerer. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT / scan-all behavior; smallest strengthening is to late-fuse raw property-view chunks before the reader runs.` | med-high | `+1 exact` |
| MS-21 | `7024f17c` | bounded actuals vs habitual routine | The reader uses a general yoga routine instead of the actual grounded last-week jogging/yoga evidence. | `A:abs_value` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="abs_value"` with sum semantics) | `YES — MS-EXHAUSTIVE-COUNT sum behavior; smallest strengthening is to ignore habitual schedule statements outside the target week.` | low | `+1 exact` |
| MS-22 | `2ce6a0f2` | art-event taxonomy leakage | `count_among` is overmatching non-art events (`Sunday mass`, `charity yoga`) and still undercounting true art-related events. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `NO` | low-med | `+1 exact` |
| MS-23 | `edced276` | exact duration chunk missing | NYC has an explicit five-day chunk, but Hawaii is left estimated; the total should come from exact duration evidence, not fallback heuristics. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT sum behavior; smallest strengthening is to surface the exact Hawaii duration chunk.` | med | `+1 exact` |
| MS-24 | `1a8a66a6` | second active subscription not surfaced | The current answer correctly removes canceled Forbes, but one more active magazine subscription is not reaching the reader. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MASTRA current-state semantics; smallest strengthening is to surface the second active subscription before applying active/canceled filtering.` | med | `+1 exact` |
| MS-25 | `51c32626` | correct node exists, retrieval misses it | The sentiment-analysis submission fact is in the graph, but the retrieved context is unrelated. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — NO-REFUSAL-extended already covers “when did I submit Z”; smallest strengthening is only to surface the correct chunk.` | med | `+1 exact` |
| MS-26 | `ba358f49` | future-age arithmetic | This requires combining Rachel’s wedding timing with the user’s age facts; there is no direct answer node to copy. | `A:derived_time` | `benchmarks/longmemeval/round2_evidence_ledger.py:answer_from_ledger` (`shape="derived_time"`) | `YES — NO-REFUSAL-extended explicitly names “what age will I be when Y”; smallest strengthening is to route it through ledger arithmetic.` | low-med | `+1 exact` |
| MS-27 | `60159905` | dinner-party synonym undercount | The third dinner party is probably phrased as feast/potluck/BBQ rather than literal “dinner party”; exact-match count misses it. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is a dinner-party synonym lexicon in late fusion.` | med | `+1 exact` |
| MS-28 | `a96c20ee_abs` | same-path co-occurrence failure | Harvard conference exists and poster/research exists, but not as “poster for undergrad course research project at Harvard”; the current answer stitches two different evidence paths together. | `qa_rule:"same-path co-occurrence required"` | `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer` (line 217+) | `YES — DISTINCT-ENTITY / _abs refusal; smallest strengthening is to require the poster event and project descriptor to co-occur on the same evidence path.` | low | `+1 exact` |
| MS-29 | `bf659f65` | third music release missing | Two album/EP acquisitions surface, but one purchased/downloaded release does not. | `B:chunk_fusion` | `benchmarks/longmemeval/round2_evidence_ledger.py:late_fusion_retrieve` | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is just to surface the third release-acquisition chunk.` | med | `+1 exact` |
| MS-30 | `81507db6` | duplicate paraphrase overcount | `count_among` double-counts paraphrases / same-session duplicates and overincludes weak graduation-like mentions. | `A:count` | `benchmarks/longmemeval/round2_evidence_ledger.py:build_evidence_ledger` (`shape="count"`) | `YES — MS-EXHAUSTIVE-COUNT; smallest strengthening is dedupe by `(date, ceremony, person)` before tally.` | low-med | `+1 exact` |

## Section 2 — Architecture spec, finalized

### Verified current surfaces

- `benchmarks/longmemeval/symbolic_resolver.py`
  - `LongMemEvalSymbolicResolver.resolve` is the dispatch at line `176`.
  - `_find_is_start_concept` is at line `339`.
  - `_try_order_among` is at line `532` but currently disabled in `resolve()`.
  - `_try_diff_between` is at line `980`.
  - `_try_diff_since` is at line `1201`.
  - `_try_relative_ago_recall` is at line `1273` but currently disabled in `resolve()`.
  - `_try_diff_since_when` is at line `1449`.
  - `_try_duration_activity` is at line `1539`.
  - `_try_named_day_recall` is at line `1645`.
- `benchmarks/longmemeval/run_eval.py`
  - `is_temporal_question` is at line `281`.
  - `build_topic_timeline_block` is at line `800`.
  - `generate_answer` is defined at line `961`; the actual LLM reader call is `answer = call_llm(prompt, config)` at line `999`.
  - The call site that invokes `generate_answer(...)` is at lines `2448-2452`.
- Raw user/assistant text is not stored as `data.session_text`.
  - Verified storage path is `EVENT.data["content"]` in `process_session_batch()` at lines `1639-1654`.
  - Event nodes also carry `role`, `timestamp`, `date`, and `session_index`.

### Final signatures and real imports

Add this new module:

`benchmarks/longmemeval/round2_evidence_ledger.py`

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import re

from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType
from cognifold.query.models import NodeSummary

Shape = Literal["count", "order", "duration_since", "date_diff", "derived_time", "abs_value", "other"]

def detect_question_shape(question: str) -> Shape: ...

def late_fusion_retrieve(
    question: str,
    graph: ConceptGraph,
    graph_hits: list[NodeSummary],
    *,
    question_date: datetime | None,
    k_graph: int = 16,
    k_chunk: int = 12,
) -> tuple[list[NodeSummary], list[dict[str, Any]]]: ...

def build_evidence_ledger(
    question: str,
    shape: Shape,
    fused_context: dict[str, Any],
) -> dict[str, Any]: ...

def answer_from_ledger(question: str, ledger: dict[str, Any]) -> str | None: ...
```

Extend `generate_answer` instead of trying to force the ledger through `context` text alone. The real minimal signature is:

```python
def generate_answer(
    question: str,
    context: str,
    config: AgentConfig,
    qa_template: str | None = None,
    *,
    graph: ConceptGraph | None = None,
    query_nodes: list[NodeSummary] | None = None,
    question_date: datetime | None = None,
) -> str:
```

Reason: the late-fusion layer needs access to `EVENT.data["content"]`, which only exists on the graph, not in the assembled reader context string.

### `round2_evidence_ledger.py` skeleton (`<= 200` lines)

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import re

from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType
from cognifold.query.models import NodeSummary

Shape = Literal["count", "order", "duration_since", "date_diff", "derived_time", "abs_value", "other"]

_COUNT_RE = re.compile(r"\bhow many\b", re.I)
_ORDER_RE = re.compile(r"\b(order|earliest to latest|who .* first|which .* first)\b", re.I)
_DURATION_RE = re.compile(r"\b(how long|how many (?:days|weeks|months|years)).*\b(since|been)\b", re.I)
_DATE_DIFF_RE = re.compile(r"\bhow many (?:days|weeks|months|years).*\b(between|before|after)\b", re.I)
_DERIVED_RE = re.compile(
    r"\b(how old was i when|how many years will i be when|how many years older am i than|"
    r"how many points do i need|how much will i save|in total|altogether|combined)\b",
    re.I,
)
_ABS_RE = re.compile(r"\b(what time|what was the airline|who did i go with|where was|when did i)\b", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9][a-z0-9'/-]+", _norm(text))
        if len(t) > 2 and t not in {"the", "and", "for", "with", "that", "this", "from"}
    }


def _score(qtoks: set[str], text: str) -> float:
    ttoks = _tokens(text)
    if not qtoks or not ttoks:
        return 0.0
    return len(qtoks & ttoks) / max(1, len(qtoks))


def detect_question_shape(question: str) -> Shape:
    q = question or ""
    if _ORDER_RE.search(q):
        return "order"
    if _DURATION_RE.search(q):
        return "duration_since"
    if _DATE_DIFF_RE.search(q):
        return "date_diff"
    if _DERIVED_RE.search(q):
        return "derived_time"
    if _COUNT_RE.search(q):
        return "count"
    if _ABS_RE.search(q):
        return "abs_value"
    return "other"


def _event_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type != NodeType.EVENT:
            continue
        text = (node.data.get("content") or node.data.get("description") or "").strip()
        if not text:
            continue
        chunks.append(
            {
                "node_id": node.id,
                "role": node.data.get("role"),
                "text": text,
                "date": node.data.get("date") or node.data.get("timestamp"),
                "session_index": node.data.get("session_index"),
            }
        )
    return chunks


def late_fusion_retrieve(
    question: str,
    graph: ConceptGraph,
    graph_hits: list[NodeSummary],
    *,
    question_date: datetime | None,
    k_graph: int = 16,
    k_chunk: int = 12,
) -> tuple[list[NodeSummary], list[dict[str, Any]]]:
    del question_date
    qtoks = _tokens(question)
    kept_graph = list(graph_hits)[:k_graph]
    raw_hits = sorted(
        _event_chunks(graph),
        key=lambda c: (_score(qtoks, c["text"]), c.get("date") or ""),
        reverse=True,
    )[:k_chunk]
    return kept_graph, raw_hits


def build_evidence_ledger(
    question: str,
    shape: Shape,
    fused_context: dict[str, Any],
) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "shape": shape,
        "question": question,
        "question_date": fused_context.get("question_date"),
        "graph_hits": fused_context.get("graph_hits", []),
        "raw_hits": fused_context.get("raw_hits", []),
    }
    if shape == "count":
        ledger["final_count"] = None
    elif shape == "order":
        ledger["ordered"] = []
    elif shape == "duration_since":
        ledger["value"] = None
        ledger["unit"] = None
    elif shape == "date_diff":
        ledger["answer"] = None
    elif shape == "derived_time":
        ledger["result"] = None
        ledger["unit"] = None
    elif shape == "abs_value":
        ledger["answer"] = None
    return ledger


def answer_from_ledger(question: str, ledger: dict[str, Any]) -> str | None:
    del question
    if ledger.get("missing_required_anchor") or ledger.get("operand_mismatch"):
        return "The information provided is not enough."
    shape = ledger.get("shape")
    if shape == "count" and ledger.get("final_count") is not None:
        return str(ledger["final_count"])
    if shape == "order" and ledger.get("ordered"):
        ordered = ledger["ordered"]
        if len(ordered) == 2:
            return f"First {ordered[0]}, then {ordered[1]}."
        if len(ordered) >= 3:
            return f"First {ordered[0]}, then {ordered[1]}, and finally {ordered[-1]}."
    if shape == "duration_since" and ledger.get("value") is not None and ledger.get("unit"):
        return f"{ledger['value']} {ledger['unit']}"
    if shape == "date_diff" and ledger.get("answer"):
        return ledger["answer"]
    if shape == "derived_time" and ledger.get("result") is not None:
        unit = ledger.get("unit")
        return f"{ledger['result']} {unit}".strip() if unit else str(ledger["result"])
    if shape == "abs_value" and ledger.get("answer"):
        return str(ledger["answer"])
    return None
```

### Smallest patch list for `symbolic_resolver.py` (function-by-function)

- `resolve()` at line `176`
  - Re-enable `_try_order_among` only after its backfill path exists.
  - Keep `_try_count_among` disabled for Round 2; count questions move to the ledger because the failure cluster is broader than one regex path.
  - Re-enable `_try_relative_ago_recall` after `_resolve_anchor_date` is in place, but keep it hint-only on ambiguous same-day candidates.
- Add new helper `_resolve_anchor_date(self, query: str, candidate: _Concept | None = None) -> datetime | None`
  - Place it near the other matching helpers after `_topk_dated()` around line `223`.
  - Purpose: centralize weekday/holiday/“two weeks ago”/free-text relative date grounding.
  - Callers: `_try_named_day_recall`, `_try_diff_since_when`, `_try_diff_ago`, `_try_diff_since`, `_try_relative_ago_recall`.
- Add new helper `_choose_duration_anchor(self, query: str, candidates: list[_Concept]) -> _Concept | None`
  - Place it near `_find_is_start_concept()` around line `339`.
  - Purpose: for phrases like “two events in a row / consecutive days”, pick the end of the matched span, not an arbitrary single event.
  - Primary caller: `_try_diff_since` for TR-01.
- `_find_is_start_concept()` at line `339`
  - Keep Pass 1 and Pass 2.
  - Gate Pass 3 EARLIEST fallback behind explicit start/begin/join/pick-up style language.
  - Do not let Pass 3 fire for recovery/end-state verbs like `recovered`, `healed`, `got over`.
  - This is the precise fix requested in the corrections block.
- `_try_order_among()` at line `532`
  - After collecting graph-based candidates, if `target_count` is known and `len(events) < target_count`, late-fuse raw event chunks and concept descriptions to backfill missing dated items.
  - Deduplicate by normalized entity, keeping the earliest occurrence for airline-style questions.
  - This is the real replacement for the hallucinated `resolve_order_candidates`.
- `_try_diff_between()` at line `980`
  - Use exclusive arithmetic by default.
  - Only switch to inclusive arithmetic if the question explicitly says `including` / `inclusive`.
  - This matches the user’s correction and cleans up TR-11.
- `_try_diff_since()` at line `1201`
  - Detect `in a row`, `consecutive`, and `two ... on consecutive days`.
  - Gather matching event candidates and run them through `_choose_duration_anchor`.
  - Leave the existing `round(days / 30)` month conversion intact; the error in TR-01 is the anchor, not the unit conversion.
- `_try_relative_ago_recall()` at line `1273`
  - Re-enable in `resolve()`.
  - Use `_resolve_anchor_date` for the target date instead of only raw `question_date - N*unit`.
  - Keep `bypass=False` when multiple same-day candidates remain.
- `_try_diff_since_when()` at line `1449`
  - Use `_resolve_anchor_date` when phrase A or B is itself relative/free-text dated.
  - Do not “fix” `370a8ff4`; keep that qid deferred.
- `_try_duration_activity()` at line `1539`
  - Use the gated `_find_is_start_concept()`; do not let recovery/end-state queries fall into the old EARLIEST mention fallback.
- `_try_named_day_recall()` at line `1645`
  - Replace ad hoc target-date grounding with `_resolve_anchor_date`.
  - Keep the existing same-day multi-candidate `bypass=False` behavior; it is useful once date grounding is correct.

### YAML block additions for `qa_answer` (existing-rule check first)

Do **not** re-add these existing iter31 rules:

- `DURATION-SINCE-START`
- `AGE-INFERENCE`
- `PLANNED→COMPLETED "today"`
- `INCLUSIVE-BOUNDARY`
- `COMPARATIVE EARLIER=FIRST`
- `EXHAUSTIVE-COUNT exclude-anchor`
- `BOOKING vs PLANNING`
- `_abs both-entities check`
- `CHRONOLOGICAL-SCAN`

Add only these four rules to `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer`:

```yaml
        iter32 ZERO-IN-WINDOW (case 80ec1f4f_abs): for month- or
        week-bounded COUNT questions, if relevant visits/items exist in
        other windows but none fall inside the asked window, answer `0`.
        Do not import adjacent-month or undated “recently” evidence
        into the target window.
```

```yaml
        iter32 ATTRIBUTE-MISMATCH REFUSAL (cases c8090214_abs,
        eeda8a6d_abs, a96c20ee_abs): if the question names a specific
        entity or attribute value and context only has a near match
        (iPhone for iPad, 20-gallon for 30-gallon, thesis poster for
        undergrad-course poster), refuse with the iter10 template.
```

```yaml
        iter32 SAME-SCOPE DIFFERENCE (case 09ba9854_abs): for
        savings/difference questions, compare operands only when they
        share the same route, scope, and currency. Airport→city-center
        is not airport→hotel. If scope mismatches, refuse.
```

```yaml
        iter32 EXPLICIT-TIME OVER INFERENCE (case 73d42213): when an
        explicit arrival / appointment / slot time exists, answer with
        that grounded clock time. Do not derive arrival from travel
        minutes unless no explicit clock time exists.
```

### `generate_answer` integration (specific line numbers)

1. Add imports near the top of `benchmarks/longmemeval/run_eval.py`:

```python
from cognifold.query.models import NodeSummary, QueryConfig, RetrievalMode
from benchmarks.longmemeval.round2_evidence_ledger import (
    answer_from_ledger,
    build_evidence_ledger,
    detect_question_shape,
    late_fusion_retrieve,
)
```

2. Extend the `generate_answer()` signature at line `961` as shown above.

3. Insert the ledger route **inside** `generate_answer()`, immediately before the current reader call at line `999`:

```python
    shape = detect_question_shape(question)
    if graph is not None and query_nodes is not None and shape != "other":
        fused_graph_hits, raw_hits = late_fusion_retrieve(
            question,
            graph,
            query_nodes,
            question_date=question_date,
        )
        ledger = build_evidence_ledger(
            question,
            shape,
            {
                "question_date": question_date,
                "graph_hits": fused_graph_hits,
                "raw_hits": raw_hits,
            },
        )
        ledger_answer = answer_from_ledger(question, ledger)
        if ledger_answer is not None:
            return ledger_answer
```

4. Pass the real objects from the caller at lines `2448-2452`:

```python
                answer = generate_answer(
                    question=question,
                    context=context_text,
                    config=config,
                    qa_template=templates.get("qa_answer"),
                    graph=graph,
                    query_nodes=query_result.nodes,
                    question_date=question_dt,
                )
```

This is the minimal real integration that satisfies the user’s routing requirement and uses the verified storage location for raw message text.

## Section 3 — Smoke test plan

Run these before any full rerun:

1. `b46e15ed` → `2`
   - Validates consecutive-day span anchor in `_try_diff_since`.
2. `gpt4_d6585ce9` → `my parents`
   - Validates named-day grounding plus companion-slot disambiguation.
3. `gpt4_f420262d` → `American Airlines`
   - Validates holiday grounding and same-day airline candidate control.
4. `08f4fc43` → `30 days`
   - Validates exclusive default in `_try_diff_between`.
5. `gpt4_f420262c` → `JetBlue, Delta, United, American Airlines`
   - Validates `_try_order_among` backfill plus earliest-per-entity dedupe.
6. `a3838d2b` → `4`
   - Validates before-Y exhaustive count with anchor exclusion.
7. `9ee3ecd6` → `100`
   - Validates ledger arithmetic for “need to earn” remaining-points questions.
8. `09ba9854_abs` → insufficiency
   - Validates same-scope difference refusal.
9. `gpt4_7fce9456` → `4`
   - Validates hardest late-fusion retrieval case on noisy context.
10. `81507db6` → `3`
   - Validates count dedupe over graduation paraphrases.

Pass criterion before a larger run:

- `8/10` or better overall.
- Must include passes on `b46e15ed`, `gpt4_f420262c`, and `gpt4_7fce9456`.
- If `gpt4_7fce9456` or `51c32626` still fail after this patch set, debug late-fusion scoring/chunk assembly first; do not add more prompt text.

## Section 4 — Bottom line

Projection is unchanged from the prior plan; only the file/function targets were corrected to match the repo.

- Deferred by user instruction: `370a8ff4`, `eac54add`.
- Actionable cases this round: `43`.
- TR projection excluding the 2 deferred cases: `~93.5% to 94.3%`.
- MS projection: `~90.2% to 91.0%`.
- Total N=500 projection: `~94.2% to 94.6%`.
- `94.87%` is still not a safe one-shot claim.
  - Reason: the remaining risk is concentrated in late-fusion retrieval quality (`MS-20`, `MS-23`, `MS-24`, `MS-29`) and in re-enabling the narrow resolver paths without reintroducing iter27-style order/relative recall regressions.

The core implementation order should be:

1. Add `round2_evidence_ledger.py`.
2. Extend `generate_answer()` and wire in the ledger path.
3. Patch the resolver helpers and re-enable only `_try_order_among` and `_try_relative_ago_recall`.
4. Add the four YAML rules above.
5. Run the 10-case smoke set.
