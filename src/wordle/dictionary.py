import importlib.resources
from pathlib import Path

if (p := Path("/usr/share/dict/words")).exists():
    with p.open("rt") as fin:
        ALL_WORDS = set(fin.read().splitlines())
else:
    ALL_WORDS = set(importlib.resources.read_text(__package__, "words").splitlines())
