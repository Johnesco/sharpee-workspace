# {{title}} — Claude Project Memory

> Project-specific context for Claude Code sessions in this game. Shared context (toolchain, commands, testing standard, Chord conventions) comes from the workspace `CLAUDE.md` one level up, which Claude Code loads automatically. Do not restate it here; link to it.

<!-- workspace: ../CLAUDE.md -->

## Project Identity

**Name:** {{title}}
**Purpose:** {{description}}
**Engine:** {{engine_line}}
**Repository:** {{repo_url}}
**Live:** {{hub_url}}
**Created:** {{date}} with `tools/new_game.py`

## Project Context

[Two or three sentences: the premise, who the player is, what the game is trying to do.]

## Design Documents

[List the files in `docs/` that hold the authoritative design, or delete this section while the story file is the only design record.]

## Writing Style Rules

- [Voice, tense, sentence length. Delete the rules you do not need.]

## File Structure Overview

```
{{id}}/
├── CLAUDE.md                THIS FILE
├── README.md                public documentation
├── {{story_file}}           the game; import .chord fragments as it grows
├── {{id}}.tests.json        tests document, replayed by sharpee test
├── {{id}}.config.json       IFID
├── ifhub.conf               the IF Hub card
├── browser/{{id}}.css       author CSS override, loaded last
├── assets/  feelies/        media the story uses; extras the player opens
├── .github/                 issue and PR templates from sdlc-baseline
└── docs/                    design docs (optional)
```

Built output at the root (`play.html`, `game.js`, `*.css`, `lib/`, `tests.html`, `walkthrough*.txt`) is written by the workspace build and committed. `dist/` and `node_modules/` are ignored.

## Key Design Decisions (do not change without discussion)

- [Decisions that shape the game. Delete this section while it is empty.]

## Current Feature Status

### Implemented
- [ ] [feature]

### Planned
- [ ] [feature]

## Working in this project

**SDLC profile:** core

Shared rules live in the workspace: `../CLAUDE.md` (loaded automatically), `../reference/chord-cookbook.md` (Chord lessons that are true here), `../reference/tests-document.md` (the tests document). Build and ship from the workspace:

```bash
python ../tools/build.py {{id}} --force
python C:/code/ifhub/tools/ship.py {{id}}
```

This project uses the [sdlc-baseline](https://github.com/Johnesco/sdlc-baseline) universal workflow. Claude must follow these canonical docs:

- [Workflow (7 steps)](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/workflow.md) — ticket-first, decide before you build, documentation-aware
- [Roles & hat-switch protocol](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/roles.md) — PO / BA / Dev / Documenter / QA
- [Definition of Done](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/definition-of-done.md) — exit criteria by issue type, verification-first
- [Severity & priority matrix](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/severity-matrix.md)
- [Commit, PR, and branch conventions](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/commit-conventions.md)
- [Release management](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/release-management.md)
- [Testing](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/testing.md) — the local gate here is `python ../tools/build.py {{id}}`, which fails on any failed assertion
- [Backlog hygiene](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/backlog-hygiene.md)
- [ADR protocol](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/adrs.md)
- [Profiles](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/profiles.md)

**Three non-negotiables:**

1. **No code without a ticket.** An Issue, or an ADR stub for a decision.
2. **Decide before you build.** Anything above a tuning tweak gets a six-line ADR stub first.
3. **Claude cannot QA its own work.** The Verify column is always human-owned.

### Project-specific deviations

None yet.

### Architecture Decisions

ADRs live in `docs/adr/` once the first one exists (index: `docs/adr/README.md`). Format, stub, and threshold rule: [sdlc-baseline `docs/adrs.md`](https://github.com/Johnesco/sdlc-baseline/blob/main/docs/adrs.md).

## Project History

### Recent Changes
- {{date}}: Scaffolded with `tools/new_game.py` (`sharpee init`, templates, sdlc-baseline GitHub templates).
