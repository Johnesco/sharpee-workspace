#!/usr/bin/env python3
"""The docs-and-layout gate for every game in this workspace.

    python tools/check_games.py            # every game
    python tools/check_games.py <game>...  # some games
    python tools/check_games.py -v         # list what passed, too

Deterministic and standard-library only: no network, no npm, no clock. The same
working tree always gives the same answer. Exit 0 = every game green, 1 = a
FAIL somewhere, 2 = bad arguments. WARNs never fail the gate.

A game folder is a subfolder holding an ifhub.conf, a .story file, or a
package.json that depends on @sharpee/*. tools/, reference/, and website/ are
never games.

What it protects, and why:

  docs      CLAUDE.md and README.md exist, and CLAUDE.md carries the
            `<!-- workspace: ../CLAUDE.md -->` marker instead of a copy of the
            workspace rules. A game doc that restates the engine version or
            points at the deleted fork clone is drift; both have happened.
  conf      ifhub.conf has what the hub reads (engine = sharpee, title, author,
            description, tags, an existing source file, hub = yes|no), and a
            game marked hub = yes has a play.html at the root. Registering the
            workspace root once nearly listed three games with broken links.
  source    a Chord game has an ifid in the header and its config.json, and a
            <id>.tests.json (engine <= 5.4) or <id>.tests/ (5.5, segmented) that parses and names the same story id. A
            TypeScript game has src/index.ts.
  layout    a built game has theme-listener.js and game.js beside play.html,
            and ignores dist/ and node_modules/. A game still on the 0.9.x
            browser/ layout is a WARN until build.py re-lays it. A folder that
            already has play.html at the root and nothing to compile from is
            `static` — a frozen published artifact, where the built output *is*
            the repo.
  entry     a Chord game's src/browser-entry.ts is the installed devkit
            template with the game's own four values filled in. The entry
            is story-owned source that no upgrade refreshes, and neither the
            build nor `sharpee test` loads it: at engine 5.4.0 every game
            here built clean and passed its tests with a page that loaded
            blank. The template is read from the game's node_modules, so
            this WARNs until npm install has run. An entry customised on
            purpose carries `custom-entry:` in a comment and is a WARN, to
            be re-checked by hand after every engine bump.
  github    the sdlc-baseline issue and PR templates are vendored, the one
            category consumption.md says must be copied.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testdoc  # noqa: E402  (tools/testdoc.py reads either tests-document form)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
NOT_GAMES = {"tools", "reference", "website", "node_modules", ".claude", ".git"}
MARKER = "<!-- workspace: ../CLAUDE.md -->"
VERSION_RESTATED = re.compile(r"(?i)(?:\bsharpee|\bchord|@sharpee/[\w-]+)\W{0,4}v?\d+\.\d+\.\d+")
DEAD_PATHS = ("C:/code/fork/sharpee", "C:\\code\\fork\\sharpee", "oldzoo/")
REQUIRED_CONF = ("engine", "title", "author", "description", "tags")
GITHUB_FILES = (".github/ISSUE_TEMPLATE/bug.yml", ".github/ISSUE_TEMPLATE/feature.yml",
                ".github/PULL_REQUEST_TEMPLATE.md")
ENTRY = Path("src") / "browser-entry.ts"
ENTRY_TEMPLATE = Path("node_modules/@sharpee/devkit/templates/browser/chord-browser-entry.ts.template")
CUSTOM_ENTRY = "custom-entry:"
# Each placeholder in the devkit template, and where the game's own entry keeps its value.
ENTRY_VALUES = {
    "{{STORY_TITLE}}": (r"\* Browser entry point for (.+?) \u2014 a Chord", 0),
    "{{STORAGE_PREFIX}}": (r"const THEME_STORAGE_KEY = '(.+?)-theme';", 0),
    "{{DEFAULT_THEME}}": (r"defaultTheme: '(.+?)'", 0),
    "{{THEMES_JSON}}": (r"themes: (\[.*?\n      \]),\n", re.S),
}


def read_conf(path: Path) -> dict:
    conf: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("["):
            break
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        conf[k.strip()] = v.strip()
    return conf


def is_game(folder: Path) -> bool:
    if folder.name in NOT_GAMES or folder.name.startswith("."):
        return False
    if (folder / "ifhub.conf").exists() or any(folder.glob("*.story")):
        return True
    pkg = folder / "package.json"
    return pkg.exists() and "@sharpee/" in pkg.read_text(encoding="utf-8", errors="replace")


def discover() -> list[Path]:
    return sorted(p for p in WORKSPACE_ROOT.iterdir() if p.is_dir() and is_game(p))


class Report:
    def __init__(self, name: str):
        self.name = name
        self.fails: list[str] = []
        self.warns: list[str] = []
        self.oks: list[str] = []

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)


def check_docs(game: Path, r: Report) -> None:
    claude = game / "CLAUDE.md"
    if not claude.exists():
        r.fail("CLAUDE.md missing (python tools/new_game.py --adopt <game> writes one)")
    else:
        text = claude.read_text(encoding="utf-8", errors="replace")
        if MARKER in text:
            r.ok("CLAUDE.md links to the workspace")
        else:
            r.fail(f"CLAUDE.md lacks the workspace marker {MARKER}")
        hits = sorted(set(m.group(0) for m in VERSION_RESTATED.finditer(text)))
        if hits:
            r.fail("CLAUDE.md restates engine versions: " + ", ".join(hits[:4])
                   + (" ..." if len(hits) > 4 else "") + " (the workspace CLAUDE.md is the one home for that)")
        else:
            r.ok("CLAUDE.md restates no engine versions")
        dead = [p for p in DEAD_PATHS if p in text]
        if dead:
            r.fail("CLAUDE.md points at things that no longer exist: " + ", ".join(dead))
    if (game / "README.md").exists():
        r.ok("README.md present")
    else:
        r.fail("README.md missing")


def check_conf(game: Path, r: Report) -> str:
    """Returns the hub flag ('yes'/'no'/'')."""
    conf_path = game / "ifhub.conf"
    if not conf_path.exists():
        r.fail("ifhub.conf missing")
        return ""
    conf = read_conf(conf_path)
    missing = [k for k in REQUIRED_CONF if not conf.get(k)]
    if missing:
        r.fail("ifhub.conf missing " + ", ".join(f"`{k} =`" for k in missing))
    else:
        r.ok("ifhub.conf has engine, title, author, description, tags")
    if conf.get("engine") and conf["engine"] != "sharpee":
        r.fail(f"ifhub.conf engine = {conf['engine']} (expected sharpee)")
    src = conf.get("source")
    if src and not (game / src).exists():
        r.fail(f"ifhub.conf source = {src} but that file does not exist")
    hub = conf.get("hub", "").lower()
    if hub not in ("yes", "no"):
        r.fail("ifhub.conf needs `hub = yes` or `hub = no`")
    if hub == "yes" and not (game / "play.html").exists():
        r.fail("hub = yes but no play.html at the root: the hub would list a broken game")
    if conf.get("binary"):
        r.warn("ifhub.conf has a `binary =` line; the hub ignores it, drop it")
    if conf.get("sourceBrowser", "").lower() == "yes" and (game / "play.html").exists() \
            and not (game / "source.html").exists():
        r.warn("sourceBrowser = yes but no source.html; build.py writes one")
    return hub


def check_source(game: Path, r: Report) -> str:
    """Returns the mode: chord | typescript | legacy | none."""
    stories = sorted(p for p in game.glob("*.story") if p.is_file())
    if stories:
        story = next((s for s in stories if s.stem == game.name), stories[0])
        text = story.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?m)^  id:\s*(\S+)", text)
        sid = m.group(1) if m else story.stem
        if sid != game.name:
            r.warn(f"story id `{sid}` differs from the folder name `{game.name}` (the hub id is the folder)")
        if re.search(r"(?m)^  ifid:\s*[0-9A-Fa-f-]{36}", text):
            r.ok("story header has an ifid")
        else:
            r.fail("story header has no ifid: (sharpee publish and the hub need one; `sharpee ifid` mints it)")
        cfg = game / f"{sid}.config.json"
        if cfg.exists():
            try:
                if json.loads(cfg.read_text(encoding="utf-8")).get("ifid"):
                    r.ok(f"{cfg.name} carries the ifid")
                else:
                    r.fail(f"{cfg.name} has no ifid")
            except json.JSONDecodeError:
                r.fail(f"{cfg.name} is not valid JSON")
        else:
            r.warn(f"{sid}.config.json missing (sharpee init writes it)")
        tests = testdoc.tests_path(game, sid)
        if tests is None:
            r.fail(f"{sid}.tests.json or {sid}.tests/ missing: a Chord game needs its tests document (reference/tests-document.md)")
        else:
            try:
                doc = testdoc.load_tests(tests)
                cards = doc.get("cards") or []
                problems = []
                want = 3 if tests.is_dir() else 1
                if doc.get("version") != want:
                    problems.append(f"version must be {want}")
                if doc.get("story") != sid:
                    problems.append(f"story must be `{sid}`")
                if not cards:
                    problems.append("no cards")
                if cards and cards[0].get("type") != "opening":
                    problems.append("first card must be the opening")
                if problems:
                    r.fail(f"{tests.name}: " + "; ".join(problems))
                else:
                    turns = sum(1 for c in cards if c.get("type") == "turn")
                    r.ok(f"{tests.name}: {len(cards)} cards, {turns} turns on the main line")
                    if turns == 0:
                        r.warn(f"{tests.name} has no turn cards yet; only the opening and boot are checked")
            except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
                r.fail(f"{tests.name} is not readable: {e}")
        pkg = game / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace") or "{}")
            dev = data.get("devDependencies", {}) or {}
            if "@sharpee/devkit" in dev:
                r.ok("package.json pins @sharpee/devkit")
            else:
                r.warn("package.json does not pin @sharpee/devkit; npx sharpee will fetch whatever is latest")
        return "chord"
    if (game / "src" / "index.ts").exists():
        if (game / "browser" / "play.html").exists() and not (game / "play.html").exists():
            r.warn("legacy 0.9.x layout: play.html is under browser/; run tools/build.py to re-lay it at the root")
            return "legacy"
        return "typescript"
    if (game / "browser" / "play.html").exists():
        r.warn("legacy layout with no src/index.ts; build.py can still re-lay browser/")
        return "legacy"
    if (game / "play.html").exists():
        r.ok("prebuilt layout: play.html at the root, nothing to build")
        return "static"
    r.fail("no .story file, no src/index.ts, no browser/play.html and no play.html: "
           "nothing to build and nothing built")
    return "none"


def check_layout(game: Path, r: Report, mode: str) -> None:
    play = game / "play.html"
    if play.exists():
        for name in ("theme-listener.js",) + (("game.js",) if mode == "chord" else ()):
            if (game / name).exists():
                r.ok(f"{name} beside play.html")
            else:
                r.fail(f"play.html present but {name} missing")
        text = play.read_text(encoding="utf-8", errors="replace")
        if 'href="themes/' in text:
            r.fail("play.html links themes/ at the root; the hub's Pages workflow deploys lib/themes/, not themes/")
        if "ThemeListener.init" not in text:
            r.warn("play.html does not call ThemeListener.init; hub themes will not reach it")
    ignore = game / ".gitignore"
    if ignore.exists():
        lines = {l.strip().rstrip("/") for l in ignore.read_text(encoding="utf-8", errors="replace").splitlines()}
        for want in ("node_modules", "dist"):
            if want in lines or f"/{want}" in lines:
                r.ok(f".gitignore ignores {want}/")
            else:
                r.warn(f".gitignore does not ignore {want}/")
    else:
        r.warn(".gitignore missing (node_modules/ and dist/ would be committed)")


def check_entry(game: Path, r: Report) -> None:
    entry = game / ENTRY
    if not entry.exists():
        r.ok("no src/browser-entry.ts: the build uses the installed devkit template")
        return
    template = game / ENTRY_TEMPLATE
    if not template.exists():
        r.warn("src/browser-entry.ts not checked: @sharpee/devkit is not installed (npm install)")
        return
    text = entry.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    rendered = template.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    custom = CUSTOM_ENTRY in text
    for placeholder, (pattern, flags) in ENTRY_VALUES.items():
        m = re.search(pattern, text, flags)
        if not m:
            msg = f"src/browser-entry.ts has no value for {placeholder}, so it cannot be compared to the devkit template"
            (r.warn if custom else r.fail)(msg)
            return
        rendered = rendered.replace(placeholder, m.group(1))
    unknown = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", rendered)))
    if unknown:
        r.warn("the devkit template has placeholders this check does not know: " + ", ".join(unknown)
               + " (teach ENTRY_VALUES in tools/check_games.py)")
        return
    if text == rendered:
        r.ok("src/browser-entry.ts matches the installed devkit template")
    elif custom:
        r.warn("src/browser-entry.ts is marked custom-entry: and differs from the devkit template; "
               "re-check it by hand after every engine bump")
    else:
        r.fail("src/browser-entry.ts differs from the installed devkit template, so the page can load blank "
               "while the build and sharpee test both pass; regenerate it from the template "
               "(reference/chord-cookbook.md, \"Moving a game to a new engine release\")")


def check_github(game: Path, r: Report) -> None:
    missing = [f for f in GITHUB_FILES if not (game / f).exists()]
    if missing:
        r.fail("sdlc-baseline GitHub templates missing: " + ", ".join(missing)
               + " (python tools/new_game.py --adopt <game>)")
    else:
        r.ok("GitHub issue and PR templates vendored")


def check_game(game: Path) -> Report:
    r = Report(game.name)
    check_docs(game, r)
    check_conf(game, r)
    mode = check_source(game, r)
    check_layout(game, r, mode)
    if mode == "chord":
        check_entry(game, r)
    check_github(game, r)
    r.mode = mode  # type: ignore[attr-defined]
    return r


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv[1:] or "--verbose" in sys.argv[1:]
    bad = [a for a in sys.argv[1:] if a.startswith("-") and a not in ("-v", "--verbose")]
    if bad:
        print(f"unknown flag: {' '.join(bad)}", file=sys.stderr)
        sys.exit(2)
    if args:
        games = []
        for a in args:
            p = Path(a)
            if not p.is_dir():
                p = WORKSPACE_ROOT / a
            if not p.is_dir():
                print(f"not a game folder: {a}", file=sys.stderr)
                sys.exit(2)
            games.append(p.resolve())
    else:
        games = discover()
    if not games:
        print("no game folders found")
        sys.exit(0)

    reports = [check_game(game) for game in games]
    for r in reports:
        status = "FAIL" if r.fails else ("WARN" if r.warns else "OK")
        print(f"{status:4}  {r.name}  ({getattr(r, 'mode', '?')})")
        for m in r.fails:
            print(f"      x {m}")
        for m in r.warns:
            print(f"      ! {m}")
        if verbose:
            for m in r.oks:
                print(f"      + {m}")
    print()
    failed = sum(1 for r in reports if r.fails)
    total = len(reports)
    print(f"{total - failed}/{total} games pass the gate" + ("" if not failed else "; fix the x lines above"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
