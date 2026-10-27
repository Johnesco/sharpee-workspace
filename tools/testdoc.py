"""Read a Chord game's tests document, in either of its on-disk forms.

    <id>.tests.json   one nested document (version 1, ADR-307), engine <= 5.4.x
    <id>.tests/       a manifest plus one segment file per run of cards between
                      fork points (version 3, ADR-355), engine >= 5.5.0

Both come back as the nested shape the rest of the workspace tooling reads:
{"version", "story", "seed", "cards": [...]}, where a card that forks carries
`branches: [{"branch": <ordinal>, "cards": [...]}]` and the cards after the fork
follow it in the same list.

Segment rules (ADR-355 D2, D4): a segment names its `parent` and the `ordinal`
it descends at. Ordinal 0 is the continuation of the parent's line after its
last card (the fork card); ordinals 1..n are the fork's branches, in order.
"""

import json
from pathlib import Path

MANIFEST = "manifest.json"


def tests_path(game: Path, sid: str) -> Path | None:
    """The tests document on disk, directory form first, or None."""
    directory = game / f"{sid}.tests"
    if directory.is_dir():
        return directory
    single = game / f"{sid}.tests.json"
    return single if single.exists() else None


def load_tests(path: Path) -> dict:
    """Load either form as one nested document."""
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads((path / MANIFEST).read_text(encoding="utf-8"))
    segments = {}
    for f in path.glob("*.json"):
        if f.name == MANIFEST or f.name.startswith("."):
            continue
        seg = json.loads(f.read_text(encoding="utf-8"))
        segments[seg["id"]] = seg
    children: dict[str, dict[int, dict]] = {}
    root = None
    for seg in segments.values():
        if "parent" in seg:
            children.setdefault(seg["parent"], {})[seg["ordinal"]] = seg
        else:
            root = seg
    if root is None:
        raise ValueError(f"{path}: no root segment")

    def build(seg: dict) -> list[dict]:
        cards = [dict(c) for c in seg["cards"]]
        kids = children.get(seg["id"], {})
        if kids and cards:
            last = cards[-1]
            branches = [{"branch": n, "cards": build(kids[n])} for n in sorted(kids) if n > 0]
            if branches:
                last["branches"] = branches
            if 0 in kids:
                cards += build(kids[0])
        return cards

    return {"version": manifest.get("version"), "story": manifest.get("story"),
            "seed": manifest.get("seed"), "cards": build(root)}
