#!/usr/bin/env python3
"""Scaffold a Sharpee (Chord) game in this workspace, or adopt an existing one.

Usage:
    python tools/new_game.py <id> --title "Title" [--author "John Googol"]
                             [--description "One sentence."] [--tags "chord, puzzle"]
                             [--no-install] [--root <dir>]
    python tools/new_game.py --adopt <game>

New game (in order):
    1. `sharpee init <id> -y`  (the global `sharpee` when installed, else npx @sharpee/devkit)
    2. the story header and package.json get the real title, author, description
    3. CLAUDE.md, README.md, ifhub.conf rendered from tools/templates/
    4. .github issue/PR templates and scripts/setup-labels.sh copied from sdlc-baseline
    5. a minimal <id>.tests.json, so `sharpee test` is green from the first commit
    6. npm install

Adopt:
    Writes only the files that are missing (CLAUDE.md, README.md, ifhub.conf, the
    GitHub templates, the tests document) into an existing game folder. Never
    overwrites. Title, author, and description come from ifhub.conf when it
    exists, else from the story header.

Git: nothing here runs git. IF Hub's ship.py creates the repo on the first ship,
or create it earlier with `gh repo create`.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = TOOLS_DIR.parent
TEMPLATES = TOOLS_DIR / "templates"
SDLC_BASELINE = Path(os.environ.get("SDLC_BASELINE", "C:/code/SDLC-baseline"))
GH_ORG = os.environ.get("IFHUB_GH_ORG", "Johnesco")

# The files sdlc-baseline says must be vendored because GitHub reads them from
# fixed paths (docs/consumption.md). Same list as scripts/sync-github-templates.sh.
GITHUB_FILES = [
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/ISSUE_TEMPLATE/task.yml",
    ".github/ISSUE_TEMPLATE/spike.yml",
    ".github/ISSUE_TEMPLATE/doc.yml",
    "scripts/setup-labels.sh",
]

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path) -> int:
    return subprocess.run(cmd, cwd=str(cwd), shell=True).returncode


def sharpee_cmd() -> list[str]:
    if shutil.which("sharpee"):
        return ["sharpee"]
    return ["npx", "-y", "-p", "@sharpee/devkit@latest", "sharpee"]


# ---------------------------------------------------------------------------
# story header
# ---------------------------------------------------------------------------

def parse_header(text: str) -> dict:
    """title, id, description, authors from the story header block."""
    out: dict = {"authors": []}
    in_authors = False
    for line in text.splitlines():
        if line.startswith("create ") or line.startswith("define ") or line.startswith("before "):
            break
        if in_authors:
            if line.startswith("    ") and line.strip():
                out["authors"].append(line.strip())
                continue
            in_authors = False
        m = re.match(r"^  ([a-z-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "authors":
            in_authors = True
            if val:
                out["authors"].append(val)
        elif key in ("title", "id", "description", "ifid", "story-version"):
            out[key] = val
    return out


def patch_header(story: Path, title: str, author: str, description: str) -> None:
    text = story.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^  title: .*$", f"  title: {title}", text, count=1)
    text = re.sub(r"(?m)^  authors:\n(?:    [^\n]*\n)+", f"  authors:\n    {author}\n", text, count=1)
    text = re.sub(r"(?m)^  description: .*$", f"  description: {description}", text, count=1)
    story.write_text(text, encoding="utf-8")


def patch_package(pkg: Path, title: str, author: str, description: str) -> None:
    if not pkg.exists():
        return
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["description"] = description
    data["author"] = author
    sharpee = data.setdefault("sharpee", {})
    if isinstance(sharpee, dict):
        sharpee["title"] = title
        sharpee["author"] = author
    pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

def render(template_name: str, ctx: dict) -> str:
    text = (TEMPLATES / template_name).read_text(encoding="utf-8")
    for key, val in ctx.items():
        text = text.replace("{{" + key + "}}", str(val))
    leftover = re.findall(r"\{\{([a-z_]+)\}\}", text)
    if leftover:
        fail(f"template {template_name} has unfilled placeholders: {sorted(set(leftover))}")
    return text


def write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        print(f"  = {path.name} (kept)")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"  + {path.name}")
    return True


def copy_github_files(target: Path) -> None:
    if not SDLC_BASELINE.is_dir():
        print(f"  ! sdlc-baseline not found at {SDLC_BASELINE}; run scripts/sync-github-templates.sh later")
        return
    for rel in GITHUB_FILES:
        src = SDLC_BASELINE / rel
        dest = target / rel
        if dest.exists():
            print(f"  = {rel} (kept)")
            continue
        if not src.exists():
            print(f"  ! {rel} missing in sdlc-baseline; skipped")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"  + {rel}")


def minimal_tests(story_id: str, title: str, description: str, first_room: str | None) -> dict:
    boot: dict = {"type": "boot", "assertions": {"contains": [first_room] if first_room else []}}
    return {
        "version": 1,
        "story": story_id,
        "seed": 42,
        "cards": [
            {"type": "opening", "assertions": {"channels": [
                {"id": "info.title", "is": title},
                {"id": "info.description", "is": description},
            ]}},
            boot,
        ],
    }


def first_room_name(story_text: str) -> str | None:
    """The first `create the X` block that declares `a room`."""
    blocks = re.split(r"(?m)^create ", story_text)
    for block in blocks[1:]:
        head, _, body = block.partition("\n")
        if re.search(r"(?m)^  a room\b", body):
            name = head.strip()
            return re.sub(r"^(the|a|an) ", "", name, flags=re.I)
    return None


def find_story(game_dir: Path) -> Path | None:
    stories = sorted(p for p in game_dir.glob("*.story") if p.is_file())
    for s in stories:
        if s.stem == game_dir.name:
            return s
    return stories[0] if stories else None


def read_conf(path: Path) -> dict:
    conf: dict = {}
    if not path.exists():
        return conf
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s or s.startswith("["):
            continue
        k, v = s.split("=", 1)
        conf[k.strip()] = v.strip()
    return conf


def context(game_id: str, title: str, author: str, description: str, tags: str,
            story_file: str, engine_line: str) -> dict:
    return {
        "id": game_id,
        "title": title,
        "author": author,
        "description": description,
        "tags": tags,
        "story_file": story_file,
        "engine_line": engine_line,
        "date": dt.date.today().isoformat(),
        "repo_url": f"https://github.com/{GH_ORG}/{game_id}",
        "hub_url": f"https://{GH_ORG.lower()}.github.io/ifhub/app.html?game={game_id}",
    }


def write_docs(target: Path, ctx: dict, with_tests: bool, story_text: str | None) -> None:
    print("docs and templates:")
    write_if_missing(target / "CLAUDE.md", render("CLAUDE.md", ctx))
    write_if_missing(target / "README.md", render("README.md", ctx))
    write_if_missing(target / "ifhub.conf", render("ifhub.conf", ctx))
    copy_github_files(target)
    if with_tests:
        tests = target / f"{ctx['id']}.tests.json"
        if not tests.exists():
            room = first_room_name(story_text) if story_text else None
            doc = minimal_tests(ctx["id"], ctx["title"], ctx["description"], room)
            tests.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            print(f"  + {tests.name} (opening + boot cards)")
        else:
            print(f"  = {tests.name} (kept)")


# ---------------------------------------------------------------------------
# modes
# ---------------------------------------------------------------------------

def new_game(args: argparse.Namespace) -> None:
    game_id = args.id
    if not ID_RE.match(game_id):
        fail("the id must be lowercase letters, digits, and hyphens (it becomes the folder, story id, and repo name)")
    root = Path(args.root).resolve() if args.root else WORKSPACE_ROOT
    target = root / game_id
    if target.exists():
        fail(f"{target} already exists (use --adopt to fill in a folder that already has a story)")
    title = args.title or game_id
    author = args.author
    description = args.description or "An interactive fiction adventure."
    tags = args.tags

    print(f"=== new game {game_id}: {title} ===")
    print("sharpee init:")
    cmd = sharpee_cmd() + ["init", game_id, "-y"]
    if run(cmd, root):
        fail("sharpee init failed")
    story = find_story(target)
    if story is None:
        fail("sharpee init did not leave a .story file; is this devkit older than 5.x?")

    patch_header(story, title, author, description)
    patch_package(target / "package.json", title, author, description)
    print(f"  header: title, authors, description set in {story.name}")

    # The scaffold's own README is generic; ours names the hub and the workspace commands.
    scaffold_readme = target / "README.md"
    if scaffold_readme.exists():
        scaffold_readme.unlink()

    ctx = context(game_id, title, author, description, tags, story.name,
                  f"Sharpee, written in Chord (`{story.name}`)")
    write_docs(target, ctx, with_tests=True, story_text=story.read_text(encoding="utf-8"))

    if args.no_install:
        print("npm install: skipped (--no-install)")
    else:
        print("npm install:")
        if run(["npm", "install", "--no-audit", "--no-fund"], target):
            fail("npm install failed")

    print()
    print("Next:")
    print(f"  cd {target}")
    print(f"  npx sharpee play                          # walk the scaffold, then edit {story.name}")
    print(f"  npx sharpee compose --check {story.name}  # the load gates while you write")
    print(f"  python ../tools/build.py {game_id}        # gates, build, tests, hub folder")
    print(f"  python C:/code/ifhub/tools/ship.py {game_id} --local")


def adopt(args: argparse.Namespace) -> None:
    target = Path(args.adopt)
    if not target.is_absolute() and not target.exists():
        target = WORKSPACE_ROOT / args.adopt
    target = target.resolve()
    if not target.is_dir():
        fail(f"not a folder: {target}")
    game_id = target.name
    conf = read_conf(target / "ifhub.conf")
    story = find_story(target)
    header = parse_header(story.read_text(encoding="utf-8")) if story else {}

    title = conf.get("title") or header.get("title") or game_id
    author = conf.get("author") or (header.get("authors") or [args.author])[0]
    description = conf.get("description") or header.get("description") or "An interactive fiction adventure."
    tags = conf.get("tags") or args.tags

    if story:
        story_file = story.name
        engine_line = f"Sharpee, written in Chord (`{story.name}`)"
    elif (target / "src" / "index.ts").exists():
        story_file = "src/index.ts"
        engine_line = "Sharpee, TypeScript (`src/index.ts`)"
    else:
        fail("no .story file and no src/index.ts; nothing to adopt")

    print(f"=== adopt {game_id}: {title} ===")
    ctx = context(game_id, title, author, description, tags, story_file, engine_line)
    write_docs(target, ctx, with_tests=bool(story),
               story_text=story.read_text(encoding="utf-8") if story else None)
    print()
    print("Now fill in the bracketed sections of CLAUDE.md, then run python tools/check_games.py "
          f"{game_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold or adopt a Sharpee game in this workspace.")
    parser.add_argument("id", nargs="?", help="Game id: lowercase, digits, hyphens")
    parser.add_argument("--title", help="Display title (default: the id)")
    parser.add_argument("--author", default="John Googol")
    parser.add_argument("--description", help="One sentence for the card and the story header")
    parser.add_argument("--tags", default="chord", help="Comma-separated hub tags")
    parser.add_argument("--no-install", action="store_true", help="Skip npm install")
    parser.add_argument("--root", help="Create the game under this folder instead of the workspace")
    parser.add_argument("--adopt", metavar="GAME", help="Write missing docs into an existing game folder")
    args = parser.parse_args()

    if args.adopt:
        adopt(args)
    elif args.id:
        new_game(args)
    else:
        parser.error("give a game id, or --adopt <game>")


if __name__ == "__main__":
    main()
