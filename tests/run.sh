#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
fail=0
expect() { if grep -qF -- "$3" <<<"$2"; then echo "ok   $1"; else echo "FAIL $1: missing '$3'"; fail=1; fi; }
refute() { if grep -qF -- "$3" <<<"$2"; then echo "FAIL $1: should not contain '$3'"; fail=1; else echo "ok   $1"; fi; }
python3 tests/build_fixtures.py || { echo "fixture build failed"; exit 1; }
F=tests/fixtures/claude
PY="uv run --python 3.12 scripts/curate.py"

out=$($PY $F --plugins-dir $F/plugins --transcripts $F/projects)
expect count "$out" "Skills found: 9 (8 in the skills folder, 1 from plugins)"
expect total-cost "$out" "Total description size: 1092 characters, about 276 tokens"
expect top-row "$out" "| 1 | pdf-form-filler | 146 | 37 | 2023-11-14 | 3 |"
expect folded-yaml "$out" "| 9 | demo-plugin:plug-skill | 85 | 22 | 2023-11-14 | 2 |"
expect uses-changelog "$out" "| 7 | changelog-writer | 114 | 29 | 2023-11-14 | 4 |"
expect never-count "$out" "Never used: 2"
expect never-1 "$out" "- logo-resizer"
expect never-2 "$out" "- recipe-scaler"
expect cluster "$out" "Cluster 1 (max score 0.74): pdf-form-filler, pdf-forms"
expect only-one-cluster "$out" "Cluster 1"
refute no-cluster-2 "$out" "Cluster 2"
refute unrelated-not-clustered "$(grep "^Cluster" <<<"$out")" "invoice-maker"
expect keep-shop "$out" 'Project `-home-demo-shop`: keep invoice-maker, pdf-form-filler, sql-explainer'
expect archive-candidates "$out" "Archive candidates (never used, or lower-ranked in an overlap): logo-resizer, pdf-forms, recipe-scaler"

# without transcripts: usage is n/a
out=$($PY $F --plugins-dir $F/plugins)
expect no-transcripts "$out" "usage is unknown"

# dry run moves nothing
T=$(mktemp -d); cp -R $F "$T/claude"
before=$(find "$T/claude/skills" | sort | shasum)
out=$($PY "$T/claude" --archive logo-resizer,recipe-scaler)
after=$(find "$T/claude/skills" | sort | shasum)
expect dry-plan "$out" "DRY RUN, nothing moved"
expect dry-plan-move "$out" "MOVE $T/claude/skills/logo-resizer -> $T/claude/skills/_archive/logo-resizer"
[ "$before" = "$after" ] && echo "ok   dry-run-unchanged" || { echo "FAIL dry-run changed files"; fail=1; }
[ ! -d "$T/claude/skills/_archive" ] && echo "ok   no-archive-dir" || { echo "FAIL archive dir created"; fail=1; }

# apply moves exactly the chosen skills; unknown name is reported
out=$($PY "$T/claude" --archive logo-resizer,recipe-scaler,nope --apply); rc=$?
[ -f "$T/claude/skills/_archive/logo-resizer/SKILL.md" ] && [ ! -d "$T/claude/skills/logo-resizer" ] && echo "ok   applied-move" || { echo "FAIL apply"; fail=1; }
[ -f "$T/claude/skills/invoice-maker/SKILL.md" ] && echo "ok   others-kept" || { echo "FAIL others moved"; fail=1; }
expect unknown-name "$out" "SKIP nope: not found"
[ $rc -ne 0 ] && echo "ok   nonzero-on-skip" || { echo "FAIL rc"; fail=1; }
out=$($PY "$T/claude")
expect archived-excluded "$out" "Skills found: 6"
rm -rf "$T"

[ $fail -eq 0 ] && echo "ALL PASS" || { echo "FAILED"; exit 1; }
