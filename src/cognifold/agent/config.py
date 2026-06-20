"""Configuration for the Cognifold agent."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for the Cognifold LLM agent.

    Attributes:
        model_name: LLM model to use (prefix with 'openai:' for OpenAI models).
        temperature: Sampling temperature (0.0-1.0).
        max_tokens: Maximum response tokens.
        max_exploration_steps: Max graph traversal iterations.
        concept_guidelines: Rules for concept discovery.
        action_guidelines: Rules for intent emergence (legacy name, see intent_guidelines).
        intent_density: Controls how aggressively the agent creates intent nodes
            (0.0 = never, 0.3 = conservative/default, 0.5 = moderate,
            0.8 = aggressive, 1.0 = maximum).

    Note:
        "action_guidelines" is preserved for backward compatibility but semantically
        these configure intent node creation. Intents represent goals/desires that
        can later be converted to concrete, schedulable actions.
    """

    model_name: str = "gemini-3-flash-preview"
    temperature: float = 0.7
    max_tokens: int = 16384
    max_exploration_steps: int = 0
    domain: str = "personal-timeline"
    language: str = "auto"  # Response language: "auto", "en", "zh"
    disable_concepts: bool = False  # If True, suppresses concept formation (Episodic mode)
    intent_density: float = 0.3  # Intent generation aggressiveness (0.0=never, 1.0=maximum)
    # W1: opt-in secondary writer pass that extracts typed attributes
    # (date/time/duration/quantity/name/person) verbatim from user-role
    # turns. Adds one extra LLM call per session.
    extract_typed_attributes: bool = False
    # W2 (iter18): opt-in pass that resolves per-concept event_date from
    # the user's relative-time phrasing. Stored as node.data["event_date"]
    # so resolvers/readers can use the true event date instead of the
    # session-extraction date. Borrowed from Chronos/Mem0.
    resolve_event_dates: bool = False
    # W3 (iter30): opt-in focused per-session pass that explicitly
    # extracts ACTIVITY START events (e.g. "I started bird watching",
    # "I bought my new running shoes") and stamps the resulting concept
    # with is_start=true + activity. Lets the duration_activity resolver
    # find a reliable START anchor for "how long had I been X-ing when
    # Y happened" questions. Replaces the unreliable iter29 TR-NEW-1
    # writer-prompt rule that gpt-5.4-mini low effort often skipped.
    extract_start_events: bool = False
    # Forwarded to OpenAI Responses API when set (gpt-5-class models only).
    reasoning_effort: str | None = None
    # Per-role API key / base URL override. When set, the OpenAI client built
    # inside `call_llm` uses these instead of the global OPENAI_API_KEY /
    # OPENAI_BASE_URL — lets writer / reader / rerank / judge route to
    # different providers in one process (e.g. reader on NTU direct,
    # writer on a cheaper key).
    api_key: str | None = None
    base_url: str | None = None

    concept_guidelines: tuple[str, ...] = (
        # Basic pattern detection
        "Create a CONCEPT node when 2+ events share a clear pattern "
        "(same location, similar time, same people, same activity type)",
        "Create a CONCEPT for recurring activities like meals, commutes, workouts",
        "Create a CONCEPT for emerging interests mentioned multiple times",
        # Strength management
        "Start new concepts with strength 0.3-0.5, increase by 0.1-0.2 when reinforced",
        "Strengthen existing concepts by updating their 'strength' field (0.0-1.0)",
        "Concepts at 0.9+ are established habits; below 0.2 consider removal",
        # Hierarchy
        "Use Level 1 for specific patterns (Morning Coffee), Level 2 for categories "
        "(Caffeine Ritual), Level 3 for abstract themes (Self-Care)",
        "Link child concepts to parents using 'parent_concept' field and edges",
        "Create parent concepts when 3+ child concepts share a theme",
        # Deduplication
        "Prefer updating existing concepts over creating duplicates",
        "Use MERGE_NODES when concepts are semantically equivalent",
        # Naming
        "Use descriptive titles like 'Morning Routine' or 'Fitness Habit'",
        "Include 'evidence_count' field tracking supporting events",
    )

    action_guidelines: tuple[str, ...] = (
        # Proactive intent creation from events
        "PROACTIVELY create INTENT nodes for goals/desires implied by events",
        "Create INTENTs when an event implies upcoming work (meeting scheduled → prepare notes)",
        "Create INTENTs for follow-up tasks mentioned or implied in events",
        # Pattern-based intent creation (from habits)
        "When a CONCEPT represents a recurring habit (e.g., 'Morning Coffee'), create an INTENT "
        "for the next expected occurrence (e.g., 'Continue morning routine')",
        "Create INTENTs from strong patterns: if 'Morning Routine' concept exists and current "
        "event reinforces it, create 'Complete morning routine' intent for next day",
        "For exercise/workout concepts, create intents like 'Exercise' when pattern is detected",
        "Include 'pattern_source' field linking to the concept that triggered the intent",
        # Temporal metadata
        "Include 'suggested_time' for when the intent should be surfaced (based on pattern timing)",
        "Include 'expiry' for when the intent is no longer relevant",
        "Set 'priority' based on urgency: 'low', 'medium', 'high', or 'urgent'",
        # Linking
        "Link INTENTs to related TIME nodes for urgency tracking",
        "Link INTENTs to the CONCEPT they were derived from",
        "Link INTENTs to related EVENTs via edges",
        # Status tracking
        "Include 'status' field: 'pending', 'action_scheduled', or 'resolved'",
        "Intents start as 'pending' and become 'resolved' when fulfilled",
    )

    time_guidelines: tuple[str, ...] = (
        # When to create TIME nodes
        "Create TIME nodes for deadlines mentioned in events",
        "Create TIME nodes for scheduled future events (meetings, appointments)",
        "Create TIME nodes for recurring time anchors (weekly standups, daily routines)",
        # Required fields
        "Include 'scheduled_time' as ISO 8601 datetime for the temporal anchor",
        "Include 'recurrence' field if the time repeats: 'daily', 'weekly', 'monthly', or None",
        # Linking
        "Link concepts and intents to TIME nodes for urgency context",
        "Nodes linked to approaching TIME nodes receive urgency boosts in scoring",
    )
