# Sharpee Games Workspace

This directory holds every Sharpee-engine interactive fiction project authored by John Googol. Each subdirectory is its own git repo with its own `CLAUDE.md`, spec, and version history. This file is **workspace-shared context**: conventions and references that apply to *every* game below it. The workspace repo itself holds only `tools/`, `reference/`, `CLAUDE.md`, `README.md`, and `.gitignore`; game folders are ignored.

**Games:**
- `hello-chord/` — Chord reference project (2026-09-07). Four rooms, one puzzle, a tests document, and the first game shipped to IF Hub through this workspace's `tools/build.py`. Copy its layout for new games.
- `no-signal-home-sharpee/` — the flagship. Chord edition migrated to 3.6.0 on 2026-09-08 under its ticket #32: full map, Act 1 with all five opening outcomes, NPC topics, two endings. TypeScript edition and the 3.0.0 draft in `legacy/`. Shipped to IF Hub 2026-09-08 (repo renamed to `no-signal-home-sharpee` to match). Three endings and the cargo/cryo gates remain on its board; nautical direction input is the open language gap.
- `fever-dream-sharpee/`, `guess-the-verb-sharpee/` — translated to Chord on 2026-09-08 and shipped to IF Hub; each keeps its TypeScript edition in `legacy/` until the Chord edition has been played through in the browser.
- `wumpus-sharpee/` — Hunt the Wumpus (story 0.3.0, 2026-09-11). 25 rooms on a 5x5
  lattice with tunnels cut and diagonal shafts added; one wumpus, one pit, one arrow,
  and a miss is fatal. The topology is machine-checked for connectivity, degree, unique
  warning signatures and winnability before the story is emitted. Built and gate-clean,
  played in a browser, **not yet shipped**. Two things to know before touching it: its
  `package.json` pins the whole `@sharpee/*` scope with npm `overrides`, because 5.3.1
  is broken for npm consumers and pinning only the direct dependencies still leaves 25
  transitive packages on it; and a `walkthrough.coverage.json` must never appear at its
  root, because a room-sweeping walkthrough cannot survive a cave where two rooms kill
  you. Its `docs/spike-findings.md` is the fullest record in this workspace of what
  Chord 3.6.0 does and does not do.
- `sample-sharpee/` — Chord twin of the Inform 7 "Sample" in `C:/code/text-games/i7/sample/`, translated 2026-09-08 for engine comparison.
- `sharpee-sound-test/` — TypeScript audio diagnostic pinned to 0.9.111, frozen, not a git repo. The build script's legacy mode re-lays its `browser/` output at the root if it is ever shipped.
- `website/` — dead. It mirrored the fork's Astro site and the fork is gone. Delete when convenient.

The old `oldzoo/` tutorial project is gone; its archive is `C:/code/familyzoo-final.bundle`.

---

## Toolchain (verified 2026-09-07)

- Engine: `@sharpee/*` **5.3.0** on npm. Language: **Chord 3.6.0**. `@sharpee/devkit` owns the `sharpee` command: `init`, `build`, `publish`, `compose --check`, `test`, `play`, `introspect`, `ifid`.
- Install once for scaffolding: `npm install -g @sharpee/devkit`. Every scaffolded game pins its own devkit and engine; inside a game folder `npx sharpee` uses the pinned copy.
- `sharpee init <name> -y` scaffolds a Chord project (`<id>.story`, `<id>.config.json` with the IFID, `package.json`, `src/browser-entry.ts`, `browser/<id>.css`, `assets/`, `feelies/`). `--ts` scaffolds TypeScript.
- Docs: the Chord guide and grammar reference at https://sharpee.net/chord/ are the source of truth. The upstream repo (https://github.com/ChicagoDave/sharpee) keeps the ADRs (214–331 cover Chord) and `packages/chord/chord.ebnf`. The old read-only clone at `C:/code/fork/sharpee` **no longer exists**; nothing here should depend on it.
- `C:/code/npmsharpee/` is the 0.9.x-era tooling workspace. Its `ship.py`, `sharpee_adapter.py`, guide mirror, and the `sync-sharpee` skill all predate 5.x and the fork's removal. `probe.js` and `transcript-runner.js` there still work for the 0.9.x TypeScript games. Treat everything else in it as historical.
- Chord Writer, the IDE, is macOS only. On this machine the CLI is the toolchain.

## Building and shipping

```bash
python tools/new_game.py <id> --title "Title" --description "One sentence."   # scaffold a Chord game with docs
python tools/new_game.py --adopt <game>                                      # write missing docs into an existing game
python tools/check_games.py [<game>] [-v]                                    # the docs-and-layout gate, every game
python tools/build.py <game> [--force] [--no-test] [--skip-install]          # gates, build, tests, hub folder
python C:/code/ifhub/tools/ship.py <game> --local                             # register on disk, preview
python C:/code/ifhub/tools/ship.py <game>                                     # publish + list on the live hub
```

## Docs model (one fact, one home)

The workspace is a library; each game is a thin consumer, the same way every project consumes sdlc-baseline. Claude Code loads this file from any game folder because it reads `CLAUDE.md` up the directory tree, so nothing below repeats what is here.

| Fact | Home | Everyone else |
|---|---|---|
| Chord language, engine API | https://sharpee.net/chord/ and the upstream ADRs | link, never mirror |
| Engine and Chord version verified here | the toolchain line above | link, or the game's `package.json` pin |
| Build, test, ship commands | `tools/*.py` docstrings, summarized above | link |
| Hub folder contract | `C:/code/ifhub/docs/publishing.md` | link |
| Lessons that are true here | `reference/chord-cookbook.md`, `reference/tests-document.md` | link |
| SDLC process | sdlc-baseline | the link block in each game's `CLAUDE.md` |
| Game design, status, deviations | the game's `CLAUDE.md` and `docs/` | never upstream |

Each game holds only what must be local: `CLAUDE.md` from `tools/templates/` (identity, design, deviations, status, the sdlc link block, and the marker `<!-- workspace: ../CLAUDE.md -->`), `README.md`, `ifhub.conf`, the `.github` templates GitHub reads from fixed paths, and its own `docs/`. `new_game.py` writes all of that, `check_games.py` keeps it true, and a game doc that restates an engine version fails the gate.

`build.py` lays the hub contract out at the game root: `play.html` (the built page, titled, `theme-listener.js` wired), `game.js` and the CSS, wired themes under `lib/themes/` (the hub's Pages workflow deploys `lib/`, not `themes/`), the `.story` itself fetched raw and highlighted by the hub (its Chord highlighter landed 2026-09-09; no `source.html`, no `sourceBrowser`), `tests.html`, `walkthrough.txt`, `walkthrough_output.txt`. Contract: `C:/code/ifhub/docs/publishing.md`. Preview: the `hub-site` launch config, then `http://127.0.0.1:8892/ifhub/app.html?game=<game>`.

Known gap: the hub's Pages workflow copies only `web lib assets audio sfx src` plus root files by extension (`.story` included since 2026-09-09), so flat media a Chord build lays beside the page will not deploy until the template in `ifhub/tools/publish.py` learns about it. No game here has media yet.

`ifhub.conf` for a Chord game: `engine = sharpee`, `title`, `author`, `description`, `tags`, `source = <id>.story`, `sourceLabel`, `walkthrough = walkthrough.txt`, `hub = no` (ship flips it). The old `binary = dist/web` line is ignored by the hub.

---

## Testing Standard (applies to every game here)

Two test worlds, by project type:

**Chord projects** — `sharpee test` replays **`<id>.tests.json`** beside the story (ADR-307). It is the source of truth: a tree of cards (`opening`, `boot`, `turn`) with `contains`, `notContains`, `exact`, `states`, `events`, and `channels` assertions, and `branches` on any card for alternate lines. `.transcript` files are refused by name. On Windows the document is written by hand (Chord Writer records it on macOS). `hello-chord/hello-chord.tests.json` is the worked example: the main line through the win plus one branch of wrong-order refusals. Useful `states` forms: `player.inventory contains brass key`, `player.location = Bell Loft`, `the red rope is pulled`.

Iterate with `npx sharpee compose --check <id>.story` (line-anchored diagnostics, nothing written) and `printf 'north\nlook\n' | npx sharpee play` (a quick transcript without recording).

**TypeScript projects (0.9.x)** — the transcript standard still applies: write a `.transcript` first; `probe.js` is the escape hatch. Assertions `[OK:]`, `[EVENT:]`, `[STATE:]`; runners `transcript-test`, `npx sharpee build --test`, `node C:/code/npmsharpee/transcript-runner.js <game-dir>` (blank-output detection), `node C:/code/npmsharpee/probe.js <game-dir> "cmd" [":state"]`. The player entity is named `yourself` in `[STATE:]` expressions. Full syntax: `C:/code/npmsharpee/docs/guides/transcript-testing.md` (mirror frozen at 2026-04-15).

**The hub report differs by platform, by design (decided 2026-09-08).** Each text platform tests in its own harness and ships its own `tests.html`, or none; the only hub requirements are a self-contained page and the hub theme (`C:/code/ifhub/docs/publishing.md`). For Chord games `build.py` renders the full `sharpee test --json --capture-output --capture-world` stream through `tools/tests_report.py`: lines, cards, every check with match highlights, the world after each turn, and the raw records, each level one press to open, in ifPlayer's class names so the hub's test-report theme applies. Levels and the by-hand command: `reference/tests-document.md`.

**Silent output is almost always a bug.** If a command produces no text, a message or phrase lookup failed.

---

## Conventions inherited by all games

- Chord first for new games. Reach for TypeScript hatches (`define text ... from "./src/x.ts"`, ADR-259) only when the language cannot say it.
- All player-facing text lives in the story: descriptions, `phrase` blocks, and a `define phrases en-US` catalog for refusal and blocked-exit keys. Never hardcoded English in TypeScript actions.
- Chord refuses boolean and negated state pairs: a state names what a thing *is* (`slack, pulled`), never the absence of something.
- Things the player acts on with a stdlib verb need the matching trait: `pullable` for PULL, `readable` for READ, `openable`/`lockable with the <key>` for doors and containers, `a supporter with capacity N` to hold things. Without it the engine refuses before the story's `on` clause can speak.
- TypeScript custom actions follow the four-phase pattern: `validate` → `execute` → `report` / `blocked`.
- Each game pins `@sharpee/*` to one version and bumps deliberately. Version drift between games is expected.
- SDLC workflow: ticket-first, documentation-aware (see `C:/code/SDLC-baseline/`). Each game adapts its own `CLAUDE.md` from that template.

---

*Add workspace-wide conventions here as they emerge. Game-specific details belong in the per-repo `CLAUDE.md`.*
