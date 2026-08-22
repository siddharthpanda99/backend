"""Audit all @node decorated functions for categories and tags."""
import re
from pathlib import Path
from collections import defaultdict

modules_dir = Path(__file__).resolve().parent.parent / "Python Libs" / "common_lib" / "src" / "common_lib" / "modules"

counts = defaultdict(int)
total = 0

NODE_RE = re.compile(r"@node\((.*?)\)\s*(?:async\s+)?def\s+(\w+)", re.DOTALL)
CAT_RE = re.compile(r'category=["\']([^"\']*)["\']')
TAGS_RE = re.compile(r'tags=\[(.*?)\]')
NAME_RE = re.compile(r'name=["\']([^"\']*)["\']')

def scan(py_file):
    global total
    try:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for m in NODE_RE.finditer(content):
            block = m.group(1)
            name_m = NAME_RE.search(block)
            cat_m = CAT_RE.search(block)
            tags_m = TAGS_RE.search(block)
            name = name_m.group(1) if name_m else m.group(2)
            cat = cat_m.group(1) if cat_m else "unknown"
            tags = re.findall(r'["\']([a-zA-Z_]+)["\']', tags_m.group(1)) if tags_m else []
            counts[cat] += 1
            total += 1
    except Exception:
        pass

for py_file in modules_dir.rglob("nodes.py"):
    scan(py_file)
for nodes_dir in modules_dir.rglob("nodes"):
    if nodes_dir.is_dir() and nodes_dir.name == "nodes":
        for py_file in nodes_dir.rglob("*.py"):
            if py_file.name != "__init__.py":
                scan(py_file)

print(f"Total @node decorated functions: {total}")
print(f"Distinct categories: {len(counts)}")
print()
print("All categories by count:")
for cat, c in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {c}")
