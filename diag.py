#!/usr/bin/env python3
"""
Script de diagnostic ProjectMind
Executer avec: python diag.py
"""
import sys
import os
print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print()

errors = []

# Test 1: packages
for pkg, imp in [
    ("python-dotenv", "dotenv"),
    ("fastapi",       "fastapi"),
    ("uvicorn",       "uvicorn"),
    ("jinja2",        "jinja2"),
    ("python-pptx",   "pptx"),
    ("requests",      "requests"),
]:
    try:
        mod = __import__(imp)
        ver = getattr(mod, "__version__", "?")
        print(f"  OK  {pkg} ({ver})")
    except ImportError as e:
        print(f"  ERR {pkg}: {e}")
        errors.append(f"Missing package {pkg}: pip install {pkg}")

print()

# Test 2: modules internes
for mod_path, display in [
    ("core.models",        "core/models.py"),
    ("ai.task_parser",     "ai/task_parser.py"),
    ("core.pptx_generator","core/pptx_generator.py"),
]:
    try:
        __import__(mod_path)
        print(f"  OK  {display}")
    except Exception as e:
        print(f"  ERR {display}: {e}")
        errors.append(f"{display}: {e}")

print()

# Test 3: init_db
try:
    from core.models import init_db
    init_db()
    print("  OK  SQLite init_db()")
except Exception as e:
    print(f"  ERR SQLite: {e}")
    errors.append(f"SQLite: {e}")

print()

# Test 4: templates
from pathlib import Path
for tmpl in ["templates/index.html", "templates/project.html", "templates/gantt.html"]:
    ok = Path(tmpl).exists()
    print(f"  {'OK ' if ok else 'ERR'} {tmpl}")
    if not ok:
        errors.append(f"Missing {tmpl} - run: git pull")

print()
if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  -> {e}")
    sys.exit(1)
else:
    print("ALL OK -> uvicorn main:app --reload --port 8766")
