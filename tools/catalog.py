#!/usr/bin/env python3
"""Rebuild CATALOG.md from library.json (run after adding files)."""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(R, 'library.json')))
rows = [f"| {it['type']} | {it['category']} | `{it['file']}` | {it.get('duration_s', '?')}s | {', '.join(it.get('tags', []))} |"
        for it in sorted(d['items'], key=lambda x: (x['type'], x['category'], x['id']))]
open(os.path.join(R, 'CATALOG.md'), 'w').write(
    "# Catalog\n\nAuto-generated from `library.json`. Regenerate with `python3 tools/catalog.py`.\n\n"
    "| Type | Category | File | Length | Tags |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
print(len(rows), 'items')
