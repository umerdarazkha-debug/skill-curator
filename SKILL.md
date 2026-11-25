---
name: skill-curator
description: Audit the Claude Code skills you have installed. Lists every skill with description size in characters and approximate tokens, last-modified date and how often it was really used (counted from session transcripts), finds skills with overlapping trigger phrases, and proposes a keep list and an archive list. Archiving is dry-run until you pass --apply. Use when the user says "too many skills", "which skills do I actually use", "skills are eating my context", "clean up my skills", "audit my skills", "find duplicate skills", "archive unused skills".
---

# Skill curator

Every installed skill puts its name and description into the context of every session. Skills you never use still cost tokens. This skill measures that and proposes what to archive.

## Steps

1. Ask which folder to audit. Default is `~/.claude`. Ask if they also want plugin skills counted (a plugins folder) and usage counted (the folder of session transcripts, normally `~/.claude/projects`). Usage needs the transcripts folder. Without it the report says usage is unknown.
2. Run the report (from the skill folder):

```bash
uv run --python 3.12 scripts/curate.py ~/.claude \
  --plugins-dir ~/.claude/plugins --transcripts ~/.claude/projects --out skill-report.md
```

   Options: `--top N` (default 20), `--threshold 0.25` (lower finds more overlaps), `--skills-dir DIR` if skills live elsewhere.
3. Read the report to the user in plain words:
   - Total description cost per session (characters, about tokens).
   - The most expensive descriptions.
   - Never-used skills and the tokens they waste.
   - Overlap clusters. Open the SKILL.md files in a cluster and say whether they really do the same job. The score is word overlap only. It can be wrong in both directions.
   - The proposed keep list, per project folder name, and the archive candidates.
4. Ask which skills to archive. Never choose for the user. Show the plan first:

```bash
uv run --python 3.12 scripts/curate.py ~/.claude --archive name1,name2
```

   This prints `MOVE a -> b` lines and moves nothing.
5. Only after a clear yes, repeat the same command with `--apply`. Skills move to `<skills-dir>/_archive/<folder>`. To restore one, move the folder back. Names starting with `_` are skipped by the scan.

## Rules

- Plugin skills are counted but cannot be archived by this script. Tell the user to disable the plugin instead.
- A skill with zero uses may still matter (rare yearly task). Say so for anything the user hesitates over.
- Usage means a `Skill` tool call in a transcript. A skill that Claude read by path, or that the user ran as a slash command in a way the log does not record as a `Skill` call, shows as unused. Check the count before archiving.
- Details on the formats the script reads: `references/formats.md`.
