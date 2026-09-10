# Sharpee Game Workspace

Stories for the [Sharpee](https://sharpee.net) engine, written in Chord (`.story`
files) or TypeScript. Each subfolder is its own git repo, published through IF Hub.
This repo holds only the tooling and shared docs: `tools/`, `reference/`, `CLAUDE.md`, this file.

## New game

```
python tools/new_game.py <id> --title "Title" --description "One sentence."
python tools/new_game.py --adopt <game>     # write the missing docs into an existing game
python tools/check_games.py                 # the docs-and-layout gate for every game
```

`new_game.py` runs `sharpee init`, sets the story header, renders `CLAUDE.md`,
`README.md`, and `ifhub.conf` from `tools/templates/`, vendors the sdlc-baseline
GitHub templates, writes a minimal tests document, and runs `npm install`.
`reference/chord-cookbook.md` and `reference/tests-document.md` hold what we have
learned about Chord and its tests document here.

## Toolchain

```
npm install -g @sharpee/devkit      # the `sharpee` command: init, build, test, play, publish
sharpee init <game> -y              # scaffold a Chord project; it pins its own devkit and engine
```

Inside a game folder `npx sharpee ...` uses the version that game pins.

## Build

```
python tools/build.py <game> [--force] [--no-test] [--skip-install]
```

For a Chord game: `npm install` when needed, `sharpee compose --check` (the load
gates), `sharpee build`, `sharpee test --json` on `<id>.tests.json`, then the hub
folder at the game root: `play.html` (titled, theme listener wired), `game.js` and
the CSS, themes under `lib/themes/`, `tests.html`, `walkthrough.txt`
and `walkthrough_output.txt`. A game with no `.story` but an old `browser/play.html`
is re-laid as is.

## Game structure

```
<game>/
├── <id>.story               the game (import .chord fragments as it grows)
├── <id>.tests.json          tests document; sharpee test replays it
├── <id>.config.json         IFID
├── ifhub.conf               the IF Hub card (engine = sharpee)
├── browser/<id>.css         author CSS override
├── assets/  feelies/        media the story uses; extras the player opens
├── play.html, game.js, *.css, lib/themes/, theme-listener.js     built by tools/build.py
├── tests.html, walkthrough.txt, walkthrough_output.txt   (the .story is the source the hub shows)
└── index.html               written by the hub's ship.py
```

## Publish

```
python C:/code/ifhub/tools/ship.py <game> --local   # register on disk, preview in the hub
python C:/code/ifhub/tools/ship.py <game>           # publish to johnesco.github.io/<game>/ and push the hub
```

Contract: `C:/code/ifhub/docs/publishing.md`. Preview with the `hub-site` launch
config (`python C:/code/ifhub/tools/serve.py`), then
`http://127.0.0.1:8892/ifhub/app.html?game=<game>`.
