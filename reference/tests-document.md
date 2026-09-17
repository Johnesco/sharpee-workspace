# The tests document

A Chord game is tested by replaying **`<id>.tests.json`**, which sits beside the story file. `sharpee test` reads it; `tools/build.py` runs it with `--json --capture-output --capture-world`, renders `tests.html` from the stream through `tools/tests_report.py`, and derives `walkthrough.txt` and `walkthrough_output.txt` from it. The design is ADR-307 in the upstream repo: the tree of played turns is the model, the JSON is its serialization, and the runner re-derives every claim against the current story each run.

`.transcript` files are refused by name for Chord projects. The transcript standard still applies to the 0.9.x TypeScript games.

Verified against Sharpee 5.3.0 / Chord 3.6.0 on 2026-09-07, and again against Sharpee 5.4.1 on 2026-09-16, with `hello-chord/hello-chord.tests.json` (19 cards, 33 assertions).

## Shape

```json
{
  "version": 1,
  "story": "hello-chord",
  "seed": 42,
  "cards": [
    { "type": "opening",
      "assertions": { "channels": [
        { "id": "info.title", "is": "Hello Chord" },
        { "id": "info.description", "is": "A locked loft, three bell ropes, and one chord to ring before the rain stops." }
      ] } },
    { "type": "boot",
      "assertions": { "contains": ["Porch", "The rain has chased you under the porch of a small stone church."] } },
    { "type": "turn", "command": "take key",
      "assertions": { "contains": ["You take the brass key from the iron hook."],
                      "states": ["player.inventory contains brass key"] } },
    { "type": "turn", "command": "up",
      "assertions": { "contains": ["Bell Loft"], "states": ["player.location = Bell Loft"] },
      "branches": [
        { "branch": 1, "cards": [
          { "type": "turn", "command": "pull white rope",
            "assertions": { "contains": ["red first."], "states": ["the white rope is slack"] } }
        ] }
      ] },
    { "type": "turn", "command": "pull red rope",
      "assertions": { "contains": ["a deep bell answers"], "states": ["the red rope is pulled"] } }
  ]
}
```

- `version` is 1; the reader refuses newer. `story` must equal the story id. `seed` pins the random service so every run is the same.
- Cards are `opening` (no command; checks the channels the client shows before play), `boot` (the first look), and `turn` (a command). The opening comes first.
- `branches` live on the card branched from: `{ "branch": <stable id>, "cards": [...] }`, recursively. The runner replays the parent line once and then each branch from that point. The main line continues with the parent's remaining cards.
- Sibling order is array order. Labels are derived, not stored: the main line is `opening-<first room>`, a branch is `<room> · <command>`.

## Assertion families

| Family | Meaning | Example |
|---|---|---|
| `contains` | each string appears in the turn's prose | `"contains": ["Nave"]` |
| `notContains` | none of the strings appear | `"notContains": ["locked"]` |
| `exact` | the whole output, line by line | `"exact": ["Taken."]` |
| `states` | world facts after the turn (grammar below) | `"states": ["the red rope is pulled"]` |
| `events` | event types emitted this turn | `"events": ["if.event.opened"]` |
| `channels` | channel values by dotted id, `is` or `contains` | `{ "id": "info.title", "is": "Hello Chord" }` |

`states` strings, tried in this order (from the ADR-307 addendum, 2026-09-03):

- `story.state = <state>` / `!=`: the story's own `states:` phase.
- `<entity>.<property> = <value>` / `!=`, and `<entity>.<collection> contains <item>` / `not-contains`, with a single-word entity head. `player.location = Bell Loft` and `player.inventory contains brass key` both pass. A one-word `aka` alias serves as the head for a thing whose name is longer: `desk.location = Hall` for `the stone desk`, aka desk.
- The Chord-spelled form `[the] <name> is <state>` / `is not <state>`, using the story's own spelling of the name: `the red rope is pulled`, `the white rope is slack`.

## Where the runner parts from ADR-307

- **There is no `skip` family**, though ADR-307 lists one. `"assertions": {"skip": true}`
  fails the document reader (exit 2) with `unknown assertion family 'skip'`. And a
  card with no `assertions` block at all fails too (exit 1): *"command has no assertion — add
  one, or declare an auto-assertion: policy (ADR-294 D2)."* To capture output
  without claiming anything yet, give every card a trivially true assertion such
  as `{"notContains": ["zzzqqqxxx"]}`, run with `--capture-output`, then write the
  real assertions from what came back.
- **`states` entity heads must be one word.** `wumpus.location = Crooked Stair`
  passes; `slime pit.location = Dead Well` fails, because the head is two words.
  At 5.3.0 it failed silently; at 5.4.1 it says so: *"Could not parse expression:
  slime pit.location = Dead Well"*. Multi-word *values* are fine. For a
  multi-word entity, use a one-word `aka` alias as the head, or the Chord-spelled
  form (`the slime pit is <state>`).
- **Cards after an ending run against a stopped engine.** Every command after a
  `win`, `lose` or `kill the player` records `Error: Cannot executeTurn() … The
  game has ended`, with no turn number, and a `notContains` check still passes on
  it. So a document that ends the game too early can go on passing on weak
  assertions — which is why the trivially true capture trick above is for
  drafting only. Give the turn after anything that might end the story a
  `contains` check.
- **A branch does not inherit an ending.** A branch forks from a copy of the
  game at its card, and the copy does not carry the engine's ended phase. A
  branch hung on the card that wins or kills starts in a game that is still
  playing: its first `look` just describes the room. To test what happens after
  an ending, the ending has to happen inside the branch (found 2026-09-17).

(Found 2026-09-10 while writing `wumpus-sharpee.tests.json`; re-checked against
Sharpee 5.4.1 on 2026-09-16.)

## The ending-and-restart branch

Every game here with an ending carries one branch proving that a finished story
can be restarted: the thing a stale engine breaks for every player who reaches an
ending, and which no other card checks. Because a branch does not inherit an
ending, it hangs on the main line's **second-to-last** card and replays the
ending move itself:

1. the ending command, with the same assertions as the main line's ending card;
2. `look` — `contains: ["The game has ended"]`;
3. `restart` — `contains: ["The story restarts."]`;
4. `look` — `contains` the opening room, and `notContains: ["The game has ended"]`.
   Where the start is random (wumpus), assert something every room prints instead.

The runner reports the ended `look` with no turn number and the fresh game's
`look` as turn 1. The branch is not on the main line, so `walkthrough.txt` does
not change. Games without an ending (the family zoo steps) carry none.

## Writing one by hand

Chord Writer records the document as you play, but it is macOS only. On Windows:

1. Play the line once and keep the output: `printf 'north\nread board\n' | npx sharpee play > out.txt`.
2. Turn each command into a `turn` card. Take `contains` strings verbatim from the output; whole sentences are safer than fragments.
3. Add a `states` line wherever the prose could stay the same while the world went wrong: inventory after TAKE, location after a move, an entity state after a puzzle step.
4. Put wrong-order and refusal checks in a `branches` entry on the card just before them, so the main line stays the walkthrough.
5. Run `npx sharpee test`. It exits 0 when every card passed, 1 on a failed assertion, 2 for a document it cannot read, 3 when the story fails to load.

Keep the main line playable start to finish: `walkthrough.txt` on the hub is exactly the main line's turn commands, and `walkthrough_output.txt` is their output from the same run.

## What the runner streams

`sharpee test --json --capture-output --capture-world` writes one JSON record per line, which `tools/tests_report.py` turns into `tests.html`. `--capture-world` adds a `world` object to every command result: the player's location and inventory after the turn, each as `{name, token}`.

```
{"type":"run-start","transcriptCount":2,"mode":"tree", ...}
{"type":"transcript-start","file":"opening-porch","index":0,"commandCount":17, ...}
{"type":"command-result","file":"opening-porch","input":"take key","passed":true,"turn":7,
 "actualOutput":"You take the brass key from the iron hook.",
 "assertionResults":[{"description":"contains \"You take the brass key from the iron hook.\"","passed":true},
                     {"description":"state player.inventory contains brass key","passed":true}]}
```

`input` is `(opening)` for the opening card and `look` for the boot card. `file` is the derived line label, and the first `transcript-start` is the main line.

## What tests.html shows

The report is the Inform 7 report's shape (ifPlayer's class names, so the hub's test-report theme styles it) with the whole stream behind four levels of disclosure, each one press:

1. **Line** — one section per run line: the main line open, a branch closed unless it failed. The header carries the verdict, card count, assertion tally and duration; a branch says which card of which line it replays through before it diverges. A table above lists every line with its fork.
2. **Card** — one row per card: turn number, command, the room after the turn, how many things the player carries, the tally. Closed unless it failed. A card that branches shows its branches beneath it as links while closed.
3. **Checks** — every assertion with its verdict and the runner's message when it failed; **show** highlights what a `contains` or `exact` check matched in the prose, and a failed `notContains` highlights the offending text; then the world after the turn.
4. **Raw** — the NDJSON record and the authored card, pretty-printed.

Controls: expand all, collapse all, failures only, and a filter that matches anything a card holds (raw records included) and opens the cards it finds. To rebuild the page from a saved stream without rebuilding the game: `python tools/tests_report.py run.ndjson <id>.tests.json -o tests.html --title "Title" --version "Sharpee 5.4.1"`.

## When a card fails after a story edit

That is the seam ADR-307 describes, not corruption. A changed description shows as a failed `contains` on that one turn; a removed room shows as a failed move and everything after it. Fix the card (or splice a turn in or out) and replay. The document is a script with claims, never a recording of truth.
