# Sync Skills with Codebase

Regenerate the `.claude/skills/cognifold-codebase/` skill to match current code.

## Instructions

Scan the current codebase and update the skills to reflect any changes:

### Step 1: Detect Changes

Compare current module structure against the skill:

```bash
# List all modules
ls src/cognifold/
# List all Python files per module
for dir in src/cognifold/*/; do echo "=== $dir ===" && ls "$dir"*.py 2>/dev/null; done
```

### Step 2: Update cognifold-codebase Skill

Read `.claude/skills/cognifold-codebase/SKILL.md` and `.claude/skills/cognifold-codebase/references/modules.md`.

For each module in `src/cognifold/`:
1. Check if module exists in the skill's module map table
2. For new modules: read `__init__.py` and key files, add entry to both SKILL.md table and references/modules.md
3. For removed modules: delete entry
4. For changed modules (new classes/methods): update references/modules.md

### Step 3: Update cognifold-dev Skill

Check `tests/unit/` and `tests/integration/` for new test files.
Update the test structure table in `.claude/skills/cognifold-dev/SKILL.md`.

### Step 4: Update cognifold-create-skill Inventory

Update the "Existing Skills Inventory" table in `.claude/skills/cognifold-create-skill/SKILL.md`.

### Step 5: Report

List what was changed:
- New modules added
- Removed modules deleted
- Updated API references
- New test files added
