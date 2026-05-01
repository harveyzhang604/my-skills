---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
---

# Find Skills

Discover and install skills from the open agent skills ecosystem at https://skills.sh/

## Finding Skills

Search using the CLI:

```bash
npx skills find [query]
```

Or browse https://skills.sh/ directly.

## Installing a Skill As-Is

Use `npx skills add` to a temp directory (it handles repo cloning and path resolution internally — skill paths vary wildly across repos), then move the result to the correct OpenClaw location.

### Step 1: Ask the user

Before installing, always ask:

1. Do you want to install this?
2. Should it be available to **all agents** or a **specific agent**?

### Step 2: Install to temp dir and move

```bash
# Install to temp dir (the CLI resolves the correct path within the repo)
cd /tmp && mkdir -p skill-tmp && cd skill-tmp
npx skills add <owner/repo@skill-name> -y

# Move to the correct OpenClaw location
cp -r .agents/skills/<skill-name> <TARGET_DIR>/<skill-name>

# Clean up
rm -rf /tmp/skill-tmp
```

Target directories:

| Scope | Location |
|---|---|
| All agents (global) | `/root/.openclaw/skills/<skill-name>/` |
| Specific agent | `/root/.openclaw/workspace-<agent>/skills/<skill-name>/` |
| Main agent only | `/root/.openclaw/workspace/skills/<skill-name>/` |

### Step 3: Verify

```bash
openclaw skills info <skill-name>
```

**Note:** Skills are snapshotted at session start. The user needs a new session (`/new`) for newly installed skills to appear.

## Building Your Own Skill (Recommended)

Often the best approach is **not** to install an existing skill directly, but to use them as research to build a better one:

1. **Search** for relevant skills with `npx skills find [query]`
2. **Fetch a few** of the top results to a temp dir (see above) and read their SKILL.md files
3. **Compare** — identify what's good, what's missing, what's redundant or too generic
4. **Build your own** that combines the best parts, adds missing pieces, and is tailored to your actual workflow

This is usually better than installing someone else's skill because:
- Community skills vary wildly in quality (some are just vague guidelines, others have real code)
- Your needs are specific — a generic skill won't cover your stack/tools/patterns
- You can keep it focused and practical instead of trying to cover everything
- You own it and can iterate on it

### Workflow

```
npx skills find "chrome extension"
  → Found 6 results

Install top 3 to /tmp, read their SKILL.md files
  → mindrally: guidelines only, no code examples
  → tenequm: WXT framework focused, good modern tooling coverage  
  → dicklesworthstone: Claude browser automation, not what we need

Write your own combining the best parts
  → Save to the appropriate OpenClaw skills directory
```

## When No Skills Are Found

If no relevant skills exist, consider building one from scratch using the `skill-creator` skill, or help the user solve their problem directly.
