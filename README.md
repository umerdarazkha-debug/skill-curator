# skill-curator

Claude Code puts the name and description of every installed skill into every session. With 50 or 100 skills that is a lot of tokens spent before you type a word, and many skills are never used or say the same thing as another one.

## What it does

- Lists each skill: name, description length (characters and about tokens), last-modified date, number of times it was called.
- Adds up the description cost per session.
- Ranks the most expensive descriptions (top 20 by default).
- Lists skills that were never used.
- Groups skills whose descriptions share many words and word pairs (simple overlap score, no ML).
- Proposes a keep list per project and an archive list.
- `--apply --archive a,b` moves chosen skills into `_archive`. Without `--apply` it only prints the plan.

## Install

```bash
git clone https://github.com/umerdarazkha-debug/skill-curator ~/.claude/skills/skill-curator
```

Needs `uv`. The script uses only the Python standard library.

## Use

Ask Claude: "audit my skills". Or:

```bash
uv run --python 3.12 scripts/curate.py ~/.claude --plugins-dir ~/.claude/plugins \
  --transcripts ~/.claude/projects --out skill-report.md
```

The script reads files only. It never reads anything except SKILL.md files and transcript files in the folders you give it.

## Test

`bash tests/run.sh` builds a fake `.claude` folder (8 skills, 1 plugin skill, 2 projects) and checks exact counts, the overlap cluster, the never-used list and that a dry run moves nothing. Offline.

## Limits

- Overlap is word counting. Two skills with different words but the same job will not match.
- Usage comes from `Skill` calls in transcripts. Old transcripts that were deleted mean undercounting.
- Token counts are characters / 4, not exact.

## License

MIT
