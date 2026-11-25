# Formats read by skill-curator

Source: Claude Code documentation (skills, plugins, session transcripts). Checked 2026-11-26. The transcript layout is the one documented publicly and seen in the open-source tooling around it. It is not a guaranteed API, so the script skips lines it does not understand.

## Skill folder

`<skills-dir>/<folder>/SKILL.md` starting with a YAML block:

```
---
name: my-skill
description: What it does. Use when the user says "...".
---
```

`description` may be plain, quoted, or a folded block (`>` or `|`). If `name` is missing the folder name is used.

## Plugin skills

Any folder that holds a `SKILL.md` under the plugins directory is treated as a plugin skill. Its full name is `<plugin>:<name>`, where `<plugin>` is the first folder under the plugins directory.

## Transcripts

One JSON object per line in `~/.claude/projects/<project>/<session>.jsonl`. An assistant line holds `message.content`, a list of blocks. A skill call is the block:

```
{"type": "tool_use", "name": "Skill", "input": {"skill": "my-skill"}}
```

Plugin skills appear as `plugin:skill`. The script matches either the full name or the bare name. The `<project>` folder name is used as the project label in the keep list.

## Token estimate

characters / 4, rounded up for each skill. It is a rough rule for English text, not a tokenizer.
