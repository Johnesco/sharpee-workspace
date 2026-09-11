#!/usr/bin/env python3
"""Build a Sharpee game for local play and IF Hub.

Usage:
    python tools/build.py <game> [--force] [--no-test] [--skip-install]

<game> is a folder name in this workspace (text-games/sharpee/<game>) or a path.

Modes, detected from the folder:
    chord    a <id>.story file at the root. Runs the Chord load gates
             (sharpee compose --check), sharpee build, and the tests document
             (<id>.tests.json) through sharpee test --json --capture-output
             --capture-world, then renders the stream (tools/tests_report.py).
    legacy   no .story, but browser/play.html from the old 0.9.x pipeline.
             Nothing is rebuilt; the existing output is re-laid at the root.
    static   no .story and no browser/, but play.html already at the root: a
             frozen published artifact where the built output *is* the repo
             (the familyzoo-vNN tutorial steps). The contract is verified and
             nothing is written.

What it writes at the game root (the IF Hub contract, C:/code/ifhub/docs/publishing.md):
    play.html               the built index.html, titled, with theme-listener.js wired
    game.js, *.css          the bundle and the engine/theme CSS the page loads
    lib/themes/             wired themes (the hub's Pages workflow deploys lib/, not themes/)
    theme-listener.js       hub theme protocol (postMessage + ?theme= full-page mode)
    (the .story itself)     fetched raw by the hub, which highlights Chord (no source.html)
    walkthrough.txt         the tests document's main line, one command per line
    walkthrough_output.txt  the transcript of that line, captured from sharpee test
    tests.html              the tests document run: lines, cards, every check with
                            match highlights, the world after each turn, raw records;
                            each level one press to open (tools/tests_report.py)

The engine's own outputs stay in dist/ (gitignored); the root layout is what gets committed.
"""

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tests_report  # noqa: E402  (tools/tests_report.py renders tests.html)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = TOOLS_DIR.parent
WEB_DIR = TOOLS_DIR / "web"

# Files the built page loads; everything else in dist/web/<id>/ is a flat asset.
BUILD_SKIP = {"index.html", "index-testing.html", "game.js.map"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def read_conf(path: Path) -> dict:
    conf: dict[str, str] = {}
    if not path.exists():
        return conf
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("["):
            break
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        conf[k.strip()] = v.strip()
    return conf


def resolve(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.is_absolute() or "/" in name_or_path or "\\" in name_or_path:
        return p.resolve()
    return WORKSPACE_ROOT / name_or_path


def find_story(game_dir: Path, conf: dict) -> Path | None:
    src = conf.get("source", "")
    if src and src.endswith(".story") and (game_dir / src).exists():
        return game_dir / src
    stories = sorted(p for p in game_dir.glob("*.story") if p.is_file())
    if not stories:
        return None
    for s in stories:
        if s.stem == game_dir.name:
            return s
    return stories[0]


def story_id(story: Path) -> str:
    for line in story.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s+id:\s*(\S+)\s*$", line)
        if m:
            return m.group(1)
    return story.stem


def run(cmd: list[str], cwd: Path, capture: bool = False) -> subprocess.CompletedProcess:
    # shell=True so npx/npm resolve through their .cmd shims on Windows.
    return subprocess.run(cmd, cwd=str(cwd), shell=True, text=True,
                          capture_output=capture, encoding="utf-8", errors="replace")


def step(title: str) -> None:
    print(f"\n--- {title} ---")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# hub theme wiring
# ---------------------------------------------------------------------------

# Maps the hub's palette (ifhub/site/themes.js game colors) onto the engine's
# --theme-* token contract (engine.css, ADR-188). !important beats the wired
# [data-theme] blocks regardless of which theme the player picked in-page.
THEME_INIT = """
<script src="theme-listener.js"></script>
<script>
ThemeListener.init({
  buildCSS: function(g, sb) {
    return 'html {' +
      ' --theme-bg: ' + g.bodyBg + ' !important;' +
      ' --theme-bg-alt: ' + g.gridBg + ' !important;' +
      ' --theme-desktop-bg: ' + g.bodyBg + ' !important;' +
      ' --theme-text: ' + g.bufferFg + ' !important;' +
      ' --theme-text-muted: ' + g.gridFg + ' !important;' +
      ' --theme-accent: ' + g.inputFg + ' !important;' +
      ' --theme-accent-text: ' + g.bodyBg + ' !important;' +
      ' --theme-border: ' + g.gridFg + ' !important;' +
      ' --theme-menu-bg: ' + g.gridBg + ' !important;' +
      ' --theme-menu-hover: ' + g.bodyBg + ' !important;' +
      ' --theme-font: ' + g.monoFamily + ' !important;' +
      ' --theme-font-body: ' + g.propFamily + ' !important;' +
      ' --theme-font-chrome: ' + g.monoFamily + ' !important;' +
      ' --theme-font-size: ' + g.bufferSize + ' !important;' +
      ' --theme-line-height: ' + g.bufferLineHeight + ' !important; }\\n' +
      '* { scrollbar-color: ' + sb.thumb + ' ' + sb.track + '; }\\n' +
      '::-webkit-scrollbar { width: 10px; background: ' + sb.track + '; }\\n' +
      '::-webkit-scrollbar-thumb { background: ' + sb.thumb + '; border-radius: 4px; }\\n' +
      '::-webkit-scrollbar-thumb:hover { background: ' + sb.thumbHover + '; }\\n';
  },
  dispatchResize: false
});
</script>
"""

# The same protocol for the two plain pages this script writes (source, tests).
# ---------------------------------------------------------------------------
# tests document → tests.html, walkthrough.txt, walkthrough_output.txt
# ---------------------------------------------------------------------------

def main_line_commands(doc: dict) -> list[str]:
    """Turn commands on the tests document's main line (branches excluded)."""
    return [c["command"] for c in doc.get("cards", [])
            if c.get("type") == "turn" and c.get("command")]


def parse_ndjson(text: str) -> list[dict]:
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def write_walkthrough(game_dir: Path, doc: dict, records: list[dict]) -> None:
    # A game may ship a full-coverage walkthrough that is deliberately wider
    # than the tests document's main line: it visits every room and exercises
    # every thing, including the refusals. When one is present it is the
    # walkthrough, and the tests document stays the regression gate.
    marker = game_dir / "walkthrough.coverage.json"
    if marker.exists():
        try:
            meta = json.loads(marker.read_text(encoding="utf-8"))
            print(f"  walkthrough: full-coverage ({meta.get('commands', '?')} commands, "
                  f"{meta.get('rooms_swept', '?')}/{meta.get('rooms_total', '?')} rooms, "
                  f"{meta.get('things_covered', '?')}/{meta.get('things_total', '?')} things) "
                  "— kept, not regenerated from the tests document")
        except json.JSONDecodeError:
            print("  walkthrough: full-coverage marker present — kept")
        return

    commands = main_line_commands(doc)
    if commands:
        (game_dir / "walkthrough.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")
        print(f"  walkthrough.txt: {len(commands)} commands")
    starts = [r for r in records if r.get("type") == "transcript-start"]
    if not starts:
        return
    first = starts[0].get("file")
    out: list[str] = []
    for r in records:
        if r.get("type") != "command-result" or r.get("file") != first:
            continue
        text = (r.get("actualOutput") or "").rstrip()
        cmd = r.get("input", "")
        if cmd == "(opening)":
            continue
        if r.get("turn") == 1 and cmd == "look":
            out.append(text)          # the boot look: the story's opening, no prompt
        else:
            out.append(f"> {cmd}\n{text}")
    (game_dir / "walkthrough_output.txt").write_text("\n\n".join(out) + "\n", encoding="utf-8")
    print(f"  walkthrough_output.txt: {len(out)} entries")


def write_tests_html(game_dir: Path, title: str, records: list[dict], version: str,
                     doc_name: str, exit_code: int, doc: dict | None = None) -> tuple[int, int, int, int]:
    """Render the sharpee test --json stream into tests.html (tools/tests_report.py:
    lines, cards, checks with match highlights, the world after each turn, raw
    records; each level one press to open). Returns (cards, cards_passed, asserts, asserts_passed)."""
    page, stats = tests_report.render(records, doc or {}, title=title, version=version,
                                      doc_name=doc_name, exit_code=exit_code)
    (game_dir / "tests.html").write_text(page, encoding="utf-8")
    return stats["cards"], stats["cards_ok"], stats["asserts"], stats["asserts_ok"]


# ---------------------------------------------------------------------------
# layout
# ---------------------------------------------------------------------------

def lay_out_chord(game_dir: Path, build_dir: Path, title: str, force: bool) -> None:
    play = game_dir / "play.html"
    if play.exists() and not force:
        print("  play.html exists (use --force to overwrite); bundle and CSS refreshed anyway")
    else:
        page = (build_dir / "index.html").read_text(encoding="utf-8")
        page = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", page, count=1)
        page = page.replace('href="themes/', 'href="lib/themes/')
        if "</body>" in page:
            page = page.replace("</body>", THEME_INIT + "</body>", 1)
        else:
            page += THEME_INIT
        play.write_text(page, encoding="utf-8")
        print("  play.html")

    copied = 0
    for item in sorted(build_dir.iterdir()):
        if item.name in BUILD_SKIP:
            continue
        if item.is_dir():
            if item.name == "themes":
                dest = game_dir / "lib" / "themes"
            else:
                dest = game_dir / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
            copied += 1
        else:
            shutil.copy2(item, game_dir / item.name)
            copied += 1
    print(f"  {copied} bundle files and folders (themes under lib/themes/)")

    listener = game_dir / "theme-listener.js"
    if not listener.exists() or force:
        shutil.copy2(WEB_DIR / "theme-listener.js", listener)
        print("  theme-listener.js")


def lay_out_legacy(game_dir: Path, force: bool) -> None:
    browser = game_dir / "browser"
    skip = {"index.html", "walkthrough.html", "walkthrough.json"}
    n = 0
    for item in sorted(browser.iterdir()):
        if item.name in skip:
            continue
        dest = game_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            if dest.exists() and not force and item.name == "play.html":
                print("  play.html exists (use --force to overwrite)")
                continue
            shutil.copy2(item, dest)
        n += 1
    print(f"  {n} files re-laid from browser/ (legacy 0.9.x output)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Sharpee game for local play and IF Hub.")
    parser.add_argument("game", help="Game folder name in this workspace, or a path")
    parser.add_argument("--force", action="store_true", help="Overwrite play.html and theme-listener.js")
    parser.add_argument("--no-test", action="store_true", help="Skip the tests document")
    parser.add_argument("--skip-install", action="store_true", help="Never run npm install")
    args = parser.parse_args()

    game_dir = resolve(args.game)
    if not game_dir.is_dir():
        fail(f"not a folder: {game_dir}")
    conf = read_conf(game_dir / "ifhub.conf")
    title = conf.get("title", game_dir.name)
    story = find_story(game_dir, conf)

    if story is None:
        if (game_dir / "browser" / "play.html").exists():
            print(f"=== build {game_dir.name} (Sharpee, legacy browser/ output) ===")
            lay_out_legacy(game_dir, args.force)
            print(f"\n  Play locally:  python -m http.server 8000 --directory \"{game_dir}\"")
            print(f"  Ship to hub:   python C:/code/ifhub/tools/ship.py {game_dir.name}")
            return
        if (game_dir / "play.html").exists():
            # A frozen published artifact: the built output *is* the repo. Nothing
            # to compile, nothing to re-lay — verify the contract and report.
            print(f"=== build {game_dir.name} (Sharpee, prebuilt static folder) ===")
            missing = [n for n in ("play.html", "theme-listener.js") if not (game_dir / n).exists()]
            if missing:
                fail(f"prebuilt folder is missing {', '.join(missing)}")
            print("  play.html and theme-listener.js present; nothing to build")
            print(f"\n  Play locally:  python -m http.server 8000 --directory \"{game_dir}\"")
            print(f"  Ship to hub:   python C:/code/ifhub/tools/ship.py {game_dir.name}")
            return
        fail("no .story file at the game root, no browser/play.html to re-lay, and no "
             "prebuilt play.html. TypeScript 5.x projects are not supported by this script yet.")

    sid = story_id(story)
    build_dir = game_dir / "dist" / "web" / sid
    print(f"=== build {game_dir.name} (Sharpee, Chord: {story.name}, id {sid}) ===")

    if not (game_dir / "node_modules").is_dir():
        if args.skip_install:
            fail("node_modules/ is missing and --skip-install was given")
        step("npm install")
        if run(["npm", "install", "--no-audit", "--no-fund"], game_dir).returncode:
            fail("npm install failed")

    ver = run(["npx", "sharpee", "--version"], game_dir, capture=True)
    version = (ver.stdout or "").strip().splitlines()[-1] if ver.stdout else "Sharpee"
    print(f"  toolchain: {version}")

    step("load gates: sharpee compose --check")
    if run(["npx", "sharpee", "compose", "--check", story.name], game_dir).returncode:
        fail("the story failed its load gates; fix the diagnostics above")

    step("sharpee build")
    if run(["npx", "sharpee", "build"], game_dir).returncode:
        fail("sharpee build failed")
    if not (build_dir / "index.html").exists():
        fail(f"expected {build_dir}/index.html after the build")

    tests_doc = game_dir / f"{sid}.tests.json"
    test_failed = False
    if args.no_test:
        step("tests skipped (--no-test)")
    elif not tests_doc.exists():
        step("tests")
        print(f"  no {tests_doc.name}; no tests.html or walkthrough files written")
    else:
        step(f"sharpee test ({tests_doc.name})")
        doc = json.loads(tests_doc.read_text(encoding="utf-8"))
        res = run(["npx", "sharpee", "test", "--json", "--capture-output", "--capture-world"],
                  game_dir, capture=True)
        records = parse_ndjson(res.stdout or "")
        if res.stderr and res.stderr.strip():
            tail = res.stderr.strip().splitlines()[-3:]
            for t in tail:
                print(f"  {t}")
        cards, cards_ok, asserts, asserts_ok = write_tests_html(
            game_dir, title, records, version, tests_doc.name, res.returncode, doc)
        print(f"  {cards_ok}/{cards} cards, {asserts_ok}/{asserts} assertions -> tests.html")
        write_walkthrough(game_dir, doc, records)
        if res.returncode != 0 or asserts_ok != asserts:
            test_failed = True

    step("lay out the hub folder")
    lay_out_chord(game_dir, build_dir, title, args.force)

    print()
    if test_failed:
        print("  TESTS FAILED: see tests.html. The folder was laid out anyway; fix before shipping.")
    print(f"  Play locally:  python -m http.server 8000 --directory \"{game_dir}\"")
    print(f"  Ship to hub:   python C:/code/ifhub/tools/ship.py {game_dir.name}")
    if test_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
