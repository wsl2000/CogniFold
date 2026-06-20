---
name: cognifold-create-skill
description: This skill should be used when Claude identifies a repeated workflow pattern, when the user asks to "create a skill", "save this as a skill", "make a reusable command", or when a complex multi-step task has been performed 2+ times and could be automated. Enables automatic skill generation to save context across sessions.
---

# Cognifold Skill Creator

Create new Claude Code skills to save context and automate repeated workflows in the Cognifold project.

## When to Create a New Skill

Create a skill when ANY of these conditions apply:

1. **Repeated workflow** - The same multi-step task has been performed 2+ times
2. **Domain knowledge** - Complex module understanding that takes significant context to rebuild
3. **Complex debugging pattern** - A debugging workflow specific to a module or subsystem
4. **New module added** - When a new module is created, generate a skill with its API surface
5. **User request** - The user explicitly asks to save something as a skill
6. **Benchmark/evaluation** - Standardized evaluation workflows that should be consistent

## Skill Directory Structure

All project skills go in `.claude/skills/`:

```
.claude/skills/
└── skill-name/
    ├── SKILL.md              # Required. Lean core instructions (<2000 words)
    ├── references/            # Optional. Detailed docs loaded on demand
    │   └── detailed-guide.md
    └── scripts/               # Optional. Executable helpers
        └── helper.sh
```

## Creating a Skill — Step by Step

### 1. Identify the Skill Scope

Determine what the skill covers. Good skills are:
- **Focused**: One domain or workflow, not everything
- **Reusable**: Will be needed again across sessions
- **Non-obvious**: Contains knowledge that requires reading code or docs

### 2. Write the SKILL.md

```yaml
---
name: skill-name-here
description: This skill should be used when the user asks to "trigger phrase 1", "trigger phrase 2", "trigger phrase 3", or when working on [specific area]. Provides [what it provides].
---

# Skill Title

[Brief purpose — 1-2 sentences]

## Core Knowledge

[The essential information, tables, code patterns — ~1500 words max]

## Workflow Steps (if applicable)

[Numbered steps for procedural skills]

## Additional Resources

### Reference Files
- **`references/foo.md`** - [What it contains]
```

### 3. Create Reference Files (if needed)

Move detailed content (>2000 words total) to `references/`:
- API details, method signatures → `references/api.md`
- Common patterns, examples → `references/patterns.md`
- Troubleshooting guides → `references/troubleshooting.md`

### 4. Validate the Skill

Checklist:
- [ ] SKILL.md has YAML frontmatter with `name` and `description`
- [ ] Description uses third person ("This skill should be used when...")
- [ ] Description includes 3+ specific trigger phrases
- [ ] Body uses imperative form (not "you should")
- [ ] Body is under 2000 words
- [ ] All referenced files exist
- [ ] No duplication with existing skills

## Skill Templates for Common Cases

### Template: New Module Skill

For when a new source module is created and its API should be preserved:

```yaml
---
name: cognifold-{module}
description: This skill should be used when the user asks to "modify {module}", "add to {module}", "fix {module}", or works on src/cognifold/{module}/. Provides API reference and patterns for the {module} module.
---
# {Module} Module Guide
## Key Classes
| Class | File | Purpose |
## Common Patterns
## Integration Points (which modules depend on this)
## Additional Resources
- **`references/api.md`** - Full class and method reference
```

### Template: Workflow Skill

For repeated multi-step tasks:

```yaml
---
name: cognifold-{workflow}
description: This skill should be used when the user asks to "{action verb} {thing}", "{action verb 2} {thing}". Automates the {workflow} workflow.
disable-model-invocation: true
---
# {Workflow} Workflow
## Prerequisites
## Steps
1. [Step with command]
2. [Step with command]
## Verification
## Troubleshooting
```

### Template: Benchmark/Evaluation Skill

For standardized evaluation runs:

```yaml
---
name: cognifold-bench-{name}
description: This skill should be used when the user asks to "run {name} benchmark", "evaluate on {name}", "benchmark {name}". Provides standardized evaluation workflow.
disable-model-invocation: true
---
# {Name} Benchmark
## Dataset
## Runner Configuration
## Expected Metrics
## Interpreting Results
```

## Existing Skills Inventory

Check before creating to avoid duplication:

| Skill | Type | Covers |
|-------|------|--------|
| `cognifold-dev` | Auto+Manual | Quality gates, git workflow, tests |
| `cognifold-create-skill` | Auto+Manual | This skill — meta skill creation |

Also check `.claude/commands/` for existing commands:
- `cognifold-test.md` — End-to-end test workflow
- `cognifold-run.md` — Simulation runner
- `cognifold-generate.md` — Event generation
- `cognifold-query.md` — Graph querying
- `cognifold-replay.md` — Replay visualization

## Automatic Skill Generation Triggers

When performing development work, consider creating a skill when:

1. **Reading 5+ files** in a module to understand it → create a module knowledge skill
2. **Running a complex debugging session** → create a debugging skill for that area
3. **Implementing a new phase** → create a skill capturing the new module's API
4. **Setting up a benchmark** → create a benchmark workflow skill
5. **Performing repeated code review patterns** → create a review checklist skill

After creating a new skill, update the inventory table above.
