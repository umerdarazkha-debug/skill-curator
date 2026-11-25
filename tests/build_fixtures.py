#!/usr/bin/env python3
"""Build synthetic fixtures that imitate ~/.claude (skills, plugins, project transcripts)."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "fixtures", "claude")
SKILLS = {
 "pdf-form-filler": "Fill in PDF forms and extract form fields from PDF documents. Use when the user says \"fill this pdf form\", \"pdf form fields\", \"complete the form\".",
 "pdf-forms": "Fill PDF forms and read form fields from PDF documents. Use when the user says \"fill this pdf form\", \"pdf form fields\", \"complete the form\".",
 "invoice-maker": "Create a clean invoice from a list of line items and a client name. Use when the user says \"make an invoice\", \"bill the client\".",
 "meeting-notes": "Turn a rough meeting transcript into decisions and action items. Use when the user says \"summarise this meeting\", \"action items\".",
 "sql-explainer": "Explain a SQL query step by step in plain English. Use when the user says \"explain this query\", \"what does this sql do\".",
 "changelog-writer": "Write a release changelog from git commit messages. Use when the user says \"write the changelog\", \"release notes\".",
 "logo-resizer": "Resize a logo image to the sizes that app stores ask for. Use when the user says \"resize my logo\", \"app icon sizes\".",
 "recipe-scaler": "Scale a cooking recipe up or down for a different number of servings. Use when the user says \"double this recipe\".",
}
PLUGIN = ("demo-plugin", "plug-skill", "Lint markdown files and fix heading order. Use when the user says \"lint my markdown\".")
USES = {  # project -> list of skill names called
 "-home-demo-shop": ["pdf-form-filler"] * 3 + ["invoice-maker"] * 2 + ["sql-explainer"],
 "-home-demo-blog": ["changelog-writer"] * 4 + ["meeting-notes", "pdf-forms", "demo-plugin:plug-skill", "demo-plugin:plug-skill"],
}
def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(text)
def main():
    if os.path.isdir(ROOT): shutil.rmtree(ROOT)
    for n, d in SKILLS.items():
        p = os.path.join(ROOT, "skills", n, "SKILL.md")
        w(p, "---\nname: %s\ndescription: %s\n---\n\n# %s\nBody.\n" % (n, d, n))
        os.utime(p, (1700000000, 1700000000))  # 2023-11-14 UTC
    p = os.path.join(ROOT, "plugins", PLUGIN[0], "skills", PLUGIN[1], "SKILL.md")
    w(p, "---\nname: %s\ndescription: >\n  %s\n---\nBody\n" % (PLUGIN[1], PLUGIN[2]))
    os.utime(p, (1700000000, 1700000000))
    for proj, names in USES.items():
        lines = [json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}})]
        for i, n in enumerate(names):
            lines.append(json.dumps({"type": "assistant", "message": {"role": "assistant", "model": "claude-test",
                "content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "id": "t%d" % i, "name": "Skill", "input": {"skill": n}}],
                "usage": {"input_tokens": 10, "output_tokens": 5}}}))
        lines.append("not json at all")  # must be skipped
        lines.append(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "x", "name": "Bash", "input": {"command": "ls"}}]}}))
        w(os.path.join(ROOT, "projects", proj, "session-1.jsonl"), "\n".join(lines) + "\n")
main()
