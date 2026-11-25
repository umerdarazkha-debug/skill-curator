#!/usr/bin/env python3
"""skill-curator: inventory installed Claude Code skills, cost, usage, overlaps.

Stdlib only. Never edits anything unless --apply is given with --archive.
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

STOP = set("""a an and are as at be by for from has have in into is it its of on or that the this to
use used when with your you user says say skill skills claude code can will any all not no do does
file files""".split())


def parse_frontmatter(text):
    """Return (name, description). Handles plain, quoted and folded (> |) values."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return None, ""
    lines = m.group(1).split("\n")
    out = {}
    i = 0
    while i < len(lines):
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", lines[i])
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2).strip()
        if val in (">", "|", ">-", "|-", ">+", "|+"):
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if val.startswith("|") else " "
            val = joiner.join(b for b in block if b is not None).strip()
        else:
            i += 1
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
        out[key] = val
    return out.get("name"), out.get("description", "")


def find_skills(root, source):
    """Folders directly under root that hold a SKILL.md."""
    found = []
    if not root or not os.path.isdir(root):
        return found
    for entry in sorted(os.listdir(root)):
        if entry.startswith("_") or entry.startswith("."):
            continue
        d = os.path.join(root, entry)
        sm = os.path.join(d, "SKILL.md")
        if os.path.isfile(sm):
            found.append(read_skill(d, sm, source, entry, None))
    return found


def find_plugin_skills(plugins_dir):
    found = []
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return found
    for dirpath, dirnames, filenames in os.walk(plugins_dir):
        dirnames.sort()
        if "SKILL.md" in filenames:
            parts = os.path.relpath(dirpath, plugins_dir).split(os.sep)
            plugin = parts[0]
            folder = os.path.basename(dirpath)
            found.append(read_skill(dirpath, os.path.join(dirpath, "SKILL.md"), "plugin", folder, plugin))
            dirnames[:] = []
    return found


def read_skill(d, sm, source, folder, plugin):
    with open(sm, encoding="utf-8", errors="replace") as f:
        text = f.read()
    name, desc = parse_frontmatter(text)
    name = name or folder
    chars = len(desc)
    mtime = datetime.fromtimestamp(os.path.getmtime(sm), tz=timezone.utc).strftime("%Y-%m-%d")
    full = "%s:%s" % (plugin, name) if plugin else name
    return {"name": name, "full": full, "plugin": plugin, "source": source, "path": d,
            "desc": desc, "chars": chars, "tokens": (chars + 3) // 4, "modified": mtime,
            "uses": 0, "project_uses": {}}


def iter_jsonl(root):
    if not root or not os.path.isdir(root):
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.endswith(".jsonl"):
                yield os.path.join(dirpath, fn)


def count_skill_calls(transcripts):
    """Return ({skill_name: count}, {project: {skill_name: count}}, files_scanned)."""
    total, per_project, nfiles = {}, {}, 0
    for path in iter_jsonl(transcripts):
        nfiles += 1
        rel = os.path.relpath(path, transcripts).split(os.sep)
        project = rel[0] if len(rel) > 1 else "(top level)"
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                msg = obj.get("message") if isinstance(obj, dict) else None
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                        inp = block.get("input") or {}
                        sk = inp.get("skill") or inp.get("name")
                        if isinstance(sk, str) and sk:
                            sk = sk.lstrip("/")
                            total[sk] = total.get(sk, 0) + 1
                            pp = per_project.setdefault(project, {})
                            pp[sk] = pp.get(sk, 0) + 1
    return total, per_project, nfiles


def apply_usage(skills, total, per_project):
    for s in skills:
        keys = {s["full"], s["name"]}
        n = 0
        for k in keys:
            n += total.get(k, 0)
        s["uses"] = n
        for proj, counts in per_project.items():
            c = sum(counts.get(k, 0) for k in keys)
            if c:
                s["project_uses"][proj] = c


def tokenize(desc):
    words = [w for w in re.findall(r"[a-z0-9]+", desc.lower()) if w not in STOP and len(w) > 2]
    feats = set(words)
    feats.update(a + " " + b for a, b in zip(words, words[1:]))
    return feats


def overlap_score(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def clusters(skills, threshold):
    feats = [tokenize(s["desc"]) for s in skills]
    parent = list(range(len(skills)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs = []
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            sc = overlap_score(feats[i], feats[j])
            if sc >= threshold:
                pairs.append((i, j, sc))
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(skills)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for members in groups.values():
        if len(members) > 1:
            ms = set(members)
            sc = [p[2] for p in pairs if p[0] in ms and p[1] in ms]
            shared = set.intersection(*[feats[m] for m in members])
            out.append({"members": sorted(skills[m]["full"] for m in members),
                        "max_score": max(sc), "shared": sorted(x for x in shared if " " in x)[:6] or sorted(shared)[:6]})
    out.sort(key=lambda c: (-c["max_score"], c["members"]))
    return out


def build_report(skills, clus, nfiles, have_transcripts, top_n, threshold):
    L = []
    total_chars = sum(s["chars"] for s in skills)
    total_tokens = sum(s["tokens"] for s in skills)
    L.append("# Skill curator report")
    L.append("")
    L.append("Skills found: %d (%d in the skills folder, %d from plugins)" % (
        len(skills), sum(1 for s in skills if s["source"] == "skills"), sum(1 for s in skills if s["source"] == "plugin")))
    L.append("")
    L.append("## Cost per session")
    L.append("")
    L.append("Claude loads every skill name and description at the start of each session.")
    L.append("Total description size: %d characters, about %d tokens (characters / 4, rounded up per skill)." % (total_chars, total_tokens))
    L.append("")
    L.append("## Top %d most expensive descriptions" % top_n)
    L.append("")
    L.append("| Rank | Skill | Chars | ~Tokens | Last modified | Uses |")
    L.append("|---|---|---|---|---|---|")
    ranked = sorted(skills, key=lambda s: (-s["chars"], s["full"]))
    for i, s in enumerate(ranked[:top_n], 1):
        uses = str(s["uses"]) if have_transcripts else "n/a"
        L.append("| %d | %s | %d | %d | %s | %s |" % (i, s["full"], s["chars"], s["tokens"], s["modified"], uses))
    L.append("")
    L.append("## Never used")
    L.append("")
    if not have_transcripts:
        L.append("No transcripts given (use --transcripts DIR), so usage is unknown.")
    else:
        never = sorted(s["full"] for s in skills if s["uses"] == 0)
        L.append("Transcript files scanned: %d" % nfiles)
        L.append("")
        L.append("Never used: %d" % len(never))
        for n in never:
            L.append("- %s" % n)
        if not never:
            L.append("- (none)")
        wasted = sum(s["tokens"] for s in skills if s["uses"] == 0)
        L.append("")
        L.append("Tokens spent each session on never-used skills: about %d" % wasted)
    L.append("")
    L.append("## Overlap clusters")
    L.append("")
    L.append("Score = shared words and word pairs divided by all words and word pairs (0 to 1). Threshold %.2f." % threshold)
    L.append("")
    if not clus:
        L.append("No clusters found.")
    for n, c in enumerate(clus, 1):
        L.append("Cluster %d (max score %.2f): %s" % (n, c["max_score"], ", ".join(c["members"])))
        L.append("  Shared phrases: %s" % ", ".join(c["shared"]))
    L.append("")
    L.append("## Proposed keep list")
    L.append("")
    L.append("This is a proposal. Nothing is moved unless you run with --apply --archive.")
    L.append("")
    by_full = {s["full"]: s for s in skills}
    drop = set()
    for c in clus:
        ordered = sorted(c["members"], key=lambda n: (-by_full[n]["uses"], by_full[n]["chars"], n))
        for n in ordered[1:]:
            drop.add(n)
    if not have_transcripts:
        L.append("Without transcripts only overlap can be judged.")
        L.append("")
        L.append("Archive candidates (lower-ranked in an overlap cluster): %s" % (", ".join(sorted(drop)) or "(none)"))
    else:
        projects = sorted({p for s in skills for p in s["project_uses"]})
        for p in projects:
            keep = sorted(s["full"] for s in skills if p in s["project_uses"])
            L.append("Project `%s`: keep %s" % (p, ", ".join(keep)))
        L.append("")
        glob_keep = sorted(s["full"] for s in skills if s["uses"] > 0 and s["full"] not in drop)
        L.append("Global keep (used and not a lower-ranked overlap): %s" % (", ".join(glob_keep) or "(none)"))
        arch = sorted(s["full"] for s in skills if s["uses"] == 0 or s["full"] in drop)
        L.append("")
        L.append("Archive candidates (never used, or lower-ranked in an overlap): %s" % (", ".join(arch) or "(none)"))
        save = sum(by_full[n]["tokens"] for n in arch)
        L.append("Tokens saved per session if all archived: about %d" % save)
    L.append("")
    return "\n".join(L)


def do_archive(skills_dir, names, apply_):
    by_name = {}
    for s in find_skills(skills_dir, "skills"):
        by_name[s["name"]] = s
        by_name[os.path.basename(s["path"])] = s
    arch_dir = os.path.join(skills_dir, "_archive")
    rc = 0
    print("")
    print("Archive plan (%s)" % ("APPLY" if apply_ else "DRY RUN, nothing moved; add --apply to move"))
    for n in names:
        s = by_name.get(n)
        if not s:
            print("  SKIP %s: not found in %s (plugin skills cannot be archived here)" % (n, skills_dir))
            rc = 1
            continue
        dest = os.path.join(arch_dir, os.path.basename(s["path"]))
        if os.path.exists(dest):
            print("  SKIP %s: %s already exists" % (n, dest))
            rc = 1
            continue
        print("  MOVE %s -> %s" % (s["path"], dest))
        if apply_:
            os.makedirs(arch_dir, exist_ok=True)
            shutil.move(s["path"], dest)
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Inventory Claude Code skills: cost, usage, overlap.")
    ap.add_argument("claude_dir", nargs="?", default="~/.claude", help="folder holding skills/ and plugins/ (default ~/.claude)")
    ap.add_argument("--skills-dir", help="override <claude_dir>/skills")
    ap.add_argument("--plugins-dir", help="plugins folder to scan for plugin skills (optional)")
    ap.add_argument("--transcripts", help="folder of session .jsonl files, e.g. ~/.claude/projects")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--threshold", type=float, default=0.25, help="overlap score for linking two skills")
    ap.add_argument("--out", help="also write the Markdown report here")
    ap.add_argument("--archive", help="comma-separated skill names to move to _archive")
    ap.add_argument("--apply", action="store_true", help="really move the --archive skills")
    a = ap.parse_args(argv)

    claude = os.path.expanduser(a.claude_dir)
    skills_dir = os.path.expanduser(a.skills_dir) if a.skills_dir else os.path.join(claude, "skills")
    plugins_dir = os.path.expanduser(a.plugins_dir) if a.plugins_dir else None
    transcripts = os.path.expanduser(a.transcripts) if a.transcripts else None

    skills = find_skills(skills_dir, "skills") + find_plugin_skills(plugins_dir)
    if not skills:
        print("No skills found in %s" % skills_dir, file=sys.stderr)
        return 2
    have_t = bool(transcripts)
    nfiles = 0
    if have_t:
        total, per_project, nfiles = count_skill_calls(transcripts)
        apply_usage(skills, total, per_project)
    clus = clusters(skills, a.threshold)
    report = build_report(skills, clus, nfiles, have_t, a.top, a.threshold)
    print(report)
    if a.out:
        with open(os.path.expanduser(a.out), "w", encoding="utf-8") as f:
            f.write(report + "\n")
    rc = 0
    if a.archive:
        names = [n.strip() for n in a.archive.split(",") if n.strip()]
        rc = do_archive(skills_dir, names, a.apply)
    elif a.apply:
        print("--apply needs --archive NAMES. Nothing done.", file=sys.stderr)
        rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main())
