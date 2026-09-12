# Chord cookbook

Lessons that are true in this workspace and are not spelled out, or not spelled out plainly, in the upstream guide. The upstream guide at https://sharpee.net/chord/ and its grammar reference are the language's source of truth; this file is what we learned by compiling games here. Every entry says when it was verified and against which Chord version, so a stale entry is easy to spot.

`hello-chord/hello-chord.story` is the worked example for most of this.

## The loop

```
npx sharpee compose --check <id>.story     # the load gates: named, line-anchored diagnostics, nothing written
printf 'north\nlook\n' | npx sharpee play  # a transcript without recording anything
npx sharpee test                           # replay <id>.tests.json
```

A story that is gate-clean loads. Write, check, play, and only then write the tests document from real output. Verified Chord 3.6.0, 2026-09-07.

## Header

```
story
  title: Hello Chord
  authors:
    John Googol
  id: hello-chord
  story-version: 0.1.0
  ifid: BAEEF4A3-1ABC-4D82-8F61-96E068FAC715
  description: One sentence. It is the card blurb and the info.description channel.
  themes: modern-dark, retro-terminal, paper, system-6
  use scoring
    rank "Visitor" at 0
    rank "Sexton" at 10
    rank "Bell-Ringer" at 20
```

- `authors:` is a list, one name per line, indented under the key. An inline name is `parse.header-inline-list`. (3.6.0)
- `ifid:` is required to publish. `sharpee init` mints it into the header and `<id>.config.json`; `sharpee ifid` mints one for a story written by hand.
- `themes:` names the built-in themes the build wires into the page. The player picks them from the Settings menu.
- Rank announcements are automatic: "You have risen to the rank of a Sexton." prints on the turn the threshold is crossed.

## Rooms and exits

```
create the Nave
  a room
  aka church, aisle
  east to the Vestry
  up to the Bell Loft through the hatch
  south is blocked: no-leaving

  first time
    Text shown on the first visit only.

  The description, shown on later visits and on LOOK.
```

- Exits are two-way unless `, one-way`. A blocked exit names a phrase key; the phrase prints instead of moving. `is blocked while <condition>: key` makes it conditional.
- `first time` before the description is the first-visit paragraph. The status line shows the room name upper-cased.

## Doors and keys

```
create the hatch
  a door, lockable with the brass key
  aka loft hatch, trapdoor, door

  A square hatch with a keyhole set into its frame.
```

A door needs no `in`: the exit line `through the hatch` places it on both sides. It starts closed and locked; UNLOCK, OPEN, CLOSE, LOCK work with no rules written. Going through a locked door prints "The hatch is locked." (3.6.0)

## Where things sit

```
create the iron hook
  aka hook
  scenery, a supporter with capacity 1
  in the Vestry

create the brass key
  aka key
  on the iron hook
```

`in the <room or container>` and `on the <supporter>`. The room description gets "On the iron hook you see a brass key." for free, and TAKE KEY prints "You take the brass key from the iron hook." (3.6.0)

## A verb needs its trait

Standard verbs check a trait before the story's `on` clause runs. Without the trait the engine refuses first, in its own words, and the story never speaks.

| The player will | The thing needs |
|---|---|
| PULL | `pullable` |
| READ | `readable` |
| OPEN / CLOSE | `openable` (doors have it) |
| UNLOCK / LOCK | `lockable with the <key>` |
| PUT X ON | `a supporter with capacity N` |
| PUT X IN | `a container` |
| WEAR | `wearable` |
| EAT | `edible` |

Seen 2026-09-07: three ropes declared `scenery` with `on the player pulling` clauses. PULL RED ROPE answered "The red rope is not something you can pull." until the ropes became `scenery, pullable`. (3.6.0)

## Rules

```
create the white rope
  aka white, white bell rope
  scenery, pullable
  in the Bell Loft
  states: slack, pulled

  on the player pulling
    the red rope must be pulled: white-too-early
    the white rope must be slack: white-already-rung
    change the white rope to pulled
    phrase white-note
      Inline phrase text, indented under the key.
  end on
```

- Rule heads name the actor: `on the player pulling`, `after the player entering`, `after Marguerite taking`. The old `after entering it` form is `parse.removed-head-it`. (3.6.0)
- `on` runs before the action commits and may stop it; `after` runs once it has happened. `must` and `refuse` lines are legal only in `on` blocks.
- `must` lines read like prose: `<thing> must be <state>: <refusal-key>`, `the player must hold the key: key`, `the player must be in the Loft: key`. The first failing line prints its phrase and the action stops.
- `, once` on a head runs the clause a single time. `first time` / `second time` / `third time` inside a clause pick a body by visit count.
- Statements that do the work: `phrase`, `change <thing> to <state>`, `change the story to <state>`, `move <thing> to <place>`, `award <name>`, `win [<phrase>]`, `lose [<phrase>]`, `kill the player [<phrase>]`, `remove <thing>`, and the acting statement `<character> <verb> <object>`.

## States

- `states: slack, pulled` is one-way: a state can only move forward through the list. Add `, reversible` to go back. Reverting an irreversible state is `analysis.irreversible-state`.
- A state names what a thing *is*. Boolean pairs (`lit, unlit`) and negations are refused by `analysis.boolean-state` and `analysis.negated-state`. Put the fact on a thing you can examine instead: the thrusters are `cold` or `burned`, not `braked` true or false.
- Conditions: `when the red rope is pulled`, `while the fountain is flowing`, `the player has the key`, `the player is in the Nave`, `and`, `or`, `not`, parentheses.

## Text

```
define phrases en-US
  no-leaving:
    You look out at the rain. The rain looks back. Not yet.
  hello-chord:
    The win text. `win hello-chord` speaks it as the story ends.
```

- Refusal keys, blocked-exit keys, and `win`/`lose` phrases live in one `define phrases en-US` catalog. The block ends by dedent; no `end`.
- Inline `phrase key` with indented text inside a rule is fine for one-offs.
- `{br}` forces a line break inside a paragraph, for boards, signs, and letters. Lines inside a paragraph otherwise join with spaces.
- A paragraph break is a blank line, everywhere prose lives: create descriptions (consecutive bare paragraphs append as separate paragraphs), `first time`, `phrase` bodies, and `define phrases` entries. Never fake one with `{br}` on the sentence and a lone `{br}` line; that renders two hard breaks inside one paragraph. The No Signal Home port did exactly that for every TypeScript `

` (16 markers, cleaned 2026-09-09) because the translation mapped each `
` to `{br}` without asking whether the break was a line or a paragraph.
- Every bare `{marker}` must name something the story declares, or the gate fails.

## Player

```
create Rowan
  a person
  playable
  starts in the Porch

  Damp, but curious.

before the game starts
  change the player to Rowan
end before
```

The player is a role assigned in exactly one `before the game starts` block. `create the player` is gone (`parse.removed-create-player`); a story with no start block is `analysis.start-block-missing`. (3.6.0)

## Scoring and endings

- `use scoring` in the header; `score <name> worth N` on the thing or room that owns the points; `award <name>` in a rule. Awards are idempotent, so awarding twice counts once. SCORE prints "You have scored 10 out of 20, earning you the rank of a Sexton."
- `win <phrase>` inside an `on` clause ends the story after the phrase and the final rank announcement. The engine stops taking input; a piped `sharpee play` prints "Engine is not running" for anything after.

## Story verbs live in traits, not on entities

```
define action breaking
  grammar
    break the target
    smash the target
    break the target with the instrument
  the target must be reachable
  otherwise refuse break-cant

define trait breakable
  on the player breaking
    the player must hold the pipe wrench: break-need-tool
    it must be intact: break-already
    change it to shattered
    move the brass key to the Patient
    play sound glass-break when client has sound
    phrase break-glass
      You swing the wrench. The glass shatters cleanly.
  end on
end trait

create the glass case
  scenery, breakable
  states: intact, shattered
```

A verb the story defines dispatches through traits. An `on the player breaking` clause written directly in the entity's `create` block passes the gates and then fails at load: "entity `on` clauses never fire on the dispatch path". Put the clause in a `define trait`, refer to the entity as `it`, and add the trait word to the entity's kind line. `otherwise refuse <key>` on the action covers every target without the trait. Standard verbs (`turning`, `touching`, `examining`) still take entity clauses. Add a pattern to a standard verb with `extend action touching` / `grammar` / `reach into the target`. (3.6.0, Fever Dream, 2026-09-08)

## Prose that changes with state

Two mechanisms, different jobs:

- `on the player examining` with one `phrase … when <condition>` line per state **replaces** the description. Conditions can combine: `when the iron valve is idle and corruption`. Use it for things whose whole text changes.
- `phrase detail while <condition>:` **appends** to the description, inside the same paragraph, and works on rooms as well as things. Several `detail` phrases with exclusive conditions on one entity are fine. Give the room a short neutral base sentence and put the state-specific text, including the exit sentence, in each detail; otherwise the appended text lands after the exits.

Story states are bare words in conditions: `while normal`, `when clarity`, `while not normal`, `phrase x when corruption`. (3.6.0, Fever Dream)

## Text and state are rendered after the turn's clauses run

Changing a state in `after the player entering` (or in an `on every turn` daemon that fires the same turn) changes the room description the player is about to read: the text is rendered after the clauses, not before. To let the player see a description once before a state flips, delay the flip a turn with a sequence:

```
create the Cistern
  states: sealed, breached
  after the player entering while clarity, once
    change the Cistern to breached
  end after

define sequence the spray exposure
  when the Cistern becomes breached
  1 turns later
    change the story to corruption
    play sound spray-hiss when client has sound
    phrase spray-exposure
end sequence
```

Sequence steps are `at turn <n>`, `<n> turns later` (always "turns", even for 1), or `when <owner> becomes <state>`. (3.6.0, Fever Dream)

## Containers, keys, and things out of play

- `scenery, a container, openable, lockable with the brass key` starts closed but **unlocked**. Add `starts locked` for a cabinet the key must open. Doors do start locked.
- A thing created with no `in`/`on` line is out of play until a rule moves it: `move the trapdoor to the Corridor`, `move the brass key to the Patient` (into a person's inventory). That is the way to conceal something Chord has no flag for. Such a thing lists without an article until it has been placed somewhere ("a pipe wrench, brass key"); cosmetic, still open.
- Chord cannot rename an entity. Carry a transformed name as an `aka` alias.

## Small syntax that bites

- A room whose name has no article (`create Cold Storage`) cannot be a placement target: `in Cold Storage` is read as a trait line. Give rooms the article (`create the Cold Storage`) and use it everywhere.
- A `##` comment needs a blank line before and after it.
- Media: `define sound glass-break from "sfx/glass.ogg"` with the file at `assets/sfx/glass.ogg`. The build keeps the `sfx/` folder beside the page, and the hub's Pages workflow deploys `sfx/`, so no layout tricks are needed for sound. Play with `play sound glass-break when client has sound`; a region's `after the player entering` / `after the player leaving` pair carries `play ambient` / `stop ambient`.

## What the standard library already has (3.6.0)

Before defining a verb, check the standard action ids: `looking_under`, `looking_behind`, `searching`, `digging`, `climbing`, `using`, `turning`, `pulling`, `pushing`, `inserting`, `putting`, `unlocking`, `switching_on`, `wearing`, `reading`, `inventory`, `help`, `hints`, `smelling`, `listening`, `touching`, `throwing`, `giving`, `entering`, `attacking`, `eating`, `drinking`, `waiting`, `sleeping` and the rest. Underscored names are written as they are in rule heads (`on the player switching_on`). A synonym is one `extend action` line; the slot word must be the one the action already uses: `taking` calls it `the item`, `examining`, `pushing`, `pulling`, `searching`, `opening` call it `the target`, `inserting` uses `the item` and `the container`. Guess the Verb carries about fifty of these lines. (Guess the Verb, 2026-09-08)

A story verb whose pattern restates a standard one wins for every target: `turn the target` under a story `dialing` action stole the kitchen faucet from the standard `turning`. Give the story verb only the patterns the standard library lacks.

## Refusal, mutation, and the one order they may come in

- `refuse` lines must precede every `change`, `move`, `set`, and `award` in a clause (`analysis.refusal-after-mutation`). A clause either refuses or mutates; it cannot do the work and then stop the standard action.
- `refuse when not …` is not a form. State the requirement positively: `the player must hold the garden trowel: dig-need-tool`, `it must hold the clock spring: wind-missing-spring`, `the player must be in the Garden: dig-nothing`.
- When the standard action refuses after your `on` clause ran (a scenery thing being taken or pushed without the matching trait), everything the clause did is discarded, text included. To let a standard verb mutate the world, the action has to commit: give the thing the trait (`pushable`, `pullable`, `climbable`, `diggable with the tool`) or make it portable and act in `after`. The doormat in Guess the Verb is portable so that `take mat` commits; its `after the player taking` reveals the key, awards the point, and moves the mat back.
- An `on` clause that speaks replaces the standard action's own text for that turn; a clause that only mutates lets the standard text print. `search overcoat` printed only the story's line.
- `it` is only a word inside `define trait`. In a `create` block, name the thing.
- The player cannot be made to act (`the player opens the trunk` is `analysis.act-player-actor`), and `set the trunk to open` is not a form. A container the story wants "unlocked" by an event is a state (`latched`, `released`) gated in `on the player opening`; the player still types OPEN.
- Scores awarded from more than one place, or from a trait or action body, belong in the story header (`score iron-key worth 1` under `use scoring`). A score declared on an entity is only awardable from that entity's own clauses.

## Movement synonyms, and winning on a score

```
extend action going
  grammar
    head north
      means direction north
    proceed up
      means direction up
```

A `means <key> <value>` line under a pattern sets that pattern's semantic default, which is how the standard going rules carry their direction. Twelve literal patterns cover `head` and `proceed` for the six directions; a slot (`head the direction`) does not work. (Sample, 2026-09-08)

Chord has no score condition, so a game that wins "when the score reaches 10" gives each scored discovery a state and checks them in a header daemon:

```
  on every turn while the dusty journal is consulted and the rusty coin is polished and the golden ring is found and the silver locket is glowing
    win victory
  end on
```

It fires on the turn the last one flips, after that turn's own text, which is what Inform's every-turn rule did. (Sample)

`use the item on the other` cannot be an `extend action unlocking` line: the first noun binds as the action's target whatever the slot is called, so the key becomes the thing being unlocked. Keep USE as a hint action. A plain thing can be `openable` on its own (a journal); OPEN then commits, `after the player opening` awards and speaks, and READ carries the same passage through `on the player reading`.

## Clocks, regions, NPCs, and the rest of the toolbox (No Signal Home)

No Signal Home exercises most of what the language has. The forms below all compiled and ran at 3.6.0 on 2026-09-08.

- **Clocks.** `define sequence <name>` with steps `at turn 10`, `when <owner> becomes <state>`, `N turns later`; each step holds statements, and `kill the player <key> when <condition>` inside one is a timed death. Every command spends a turn.
- **Regions.** `create the Lower Deck / a region / containing <rooms>` with `after the player entering, once` on the region: the moment the player crosses in, the story's own state flips (`change the story to boarded`) and a sequence keyed on `when the story becomes boarded` starts counting.
- **A daemon that nags.** `on every turn while the proximity alarm is screaming / phrase alarm-nag` in the header, with `define phrase alarm-nag, cycling … or … or … end phrase` rotating three lines. This is the Chord stand-in for a global action interceptor, which the language does not have.
- **People.** `a person, proper, passive` / `guard` / `wanderer with move-chance 30`, `pronouns she`, a `states:` line for their arc, and `define topics for <name> / about "the cargo", "the hold": phrase <key> / end topics` for ASK. A guard announces "Okafor blocks your way!"; a wanderer follows and "notices you".
- **Doors and openings.** A door between rooms is `a door` named on both rooms' exit lines (`through the pressure hatch`). One that should stand open needs `openable` and `starts open`, and the gate then lives on the room (`south is blocked while the docking controls is not sealed: key`). A keyed door is `a door, lockable with the <key>` and starts locked; a keyed container needs `starts locked` as well.
- **Scenery that reads.** `readable` alone prints "The sign reads:" and nothing else. Give it `on the player reading / phrase <key>` with the text.
- **Hidden things.** `concealed` on a thing placed in a room; the standard SEARCH in that room reveals it ("Hidden here, you discover: a data chip").
- **Cutting.** `scenery, plural, cuttable with the cable snips` plus `on the player cutting`; the standard `cutting` action carries the tool check, the clause carries the story.
- **Grammar patterns are literal words.** `fire thrusters` is a phrase; `fire the thrusters` declares a slot named `thrusters` (`analysis.slot-shadows-entity`). Never write `the` in a pattern unless you mean a slot.
- **Turns are visible.** The alarm clock's `at turn 10` counts every command including LOOK and EXAMINE; the tests document has to spend exactly that many.

## Things that compile but do nothing at 3.6.0

- Per-entity `phrase taking-fixed-in-place:` (and the other standard-message aliases) inside a `create` block passed the gates and never changed the output. Use `on the player taking` / `refuse desk-heavy` with your own phrase instead.
- A free-text slot (`the code is a topic`, `the code takes the rest of the line`) parsed as an entity at runtime: `dial 739` answered "You can't see any such thing." Digits are not allowed in grammar patterns either. Guess the Verb dropped typed combinations and opens the safe from the known numbers.
- `extend action going` with `head the direction` treated the direction as an entity; leave movement synonyms to the standard `going`.

## `win` does not stop the clause

A `win` (or `lose`, or `kill the player`) that fires conditionally does **not**
halt the statements after it. They all still run, so a naive fallthrough prints
after the ending:

```
> shoot east
The arrow goes into the dark and something very large stops breathing.

*** You have killed the wumpus ***

The arrow clatters off bare rock. Somewhere, something wakes up.
```

Every statement after a conditional ending needs its own guard. Naming the
condition twice (once positive for the `win`, once negated for the rest) works
but duplicates a long predicate. Cheaper: have the winning case set a state, and
key everything off the state.

```chord
  change the wumpus to shot when the player is in the Cave Mouth and the wumpus is in the Font
  ...
  win kill-wumpus when the wumpus is shot
  phrase arrow-missed when not the wumpus is shot
  move the wumpus to a random adjacent room when not the wumpus is shot
```

(Hunt the Wumpus, 3.6.0, 2026-09-10)

## Advancing a one-way state ladder, written backwards

Statements run in order, so stepping `states: sleeping, stirring, hunting` one
stage per event has to be written from the far end back, or a sleeping thing
advances twice in the same turn:

```chord
  change the wumpus to hunting when the wumpus is stirring
  change the wumpus to stirring when the wumpus is sleeping
```

Forwards, the first line makes it `stirring` and the second immediately sees
`stirring` and pushes it to `hunting`. (Hunt the Wumpus, 3.6.0, 2026-09-10)

## Adjacency: no predicate, but there is a destination

There is no adjacency condition — "is X next to Y", "the room north of here" —
and the ADR names that a deliberate non-goal. But `move <thing> to a random
adjacent room` **is** a statement, and works. So a wandering hazard is easy; a
rule that reasons about the map is not, and the map, being hand-authored, is
authoring-time data anyway. A room can name its own neighbours in a `detail`
condition, and an action can carry one line per square of the map:

```chord
  phrase detail while the wumpus is in the Font or the wumpus is in the Sump:
    Blood is smeared along the walls here.
```

Because the condition tests where the thing *is*, it stays correct when the thing
moves. (Hunt the Wumpus, 3.6.0, 2026-09-10)

## A thing in the room the player should not see listed

`concealed` on a thing keeps it out of the room listing. Without it a hazard the
player walks into announces itself one line before it acts: "You can see wumpus
here." (Hunt the Wumpus, 3.6.0, 2026-09-10)

## Asking about the room the player is standing in

There is no `the player's location is …` condition, so "how does this room
compare" looks like one line per room. It is not. A condition that mentions `it`
is **open** — a predicate over entities — and `any <condition>` asks whether
anything satisfies it. Put the player in the condition and `any` finds the one
room that is both in that state and holding the player:

```chord
define condition here-new: it is seen-once and the player is in it
define condition here-again: it is seen-twice and the player is in it

define action recalling
  grammar
    map
    remember
  phrase recall-new when any here-new
  phrase recall-again when any here-again
```

Three lines instead of one per room per state. `no <condition>` is the negative
form. Applying `any`/`no` to a *closed* condition (one that never says `it`) is
`analysis.closed-condition-selection`, and testing an open one for plain truth is
`analysis.open-condition-truth`. (Hunt the Wumpus, 3.6.0, 2026-09-11)

## `after the player entering` does not fire for the starting room

Being placed somewhere is not entering it. A room whose state is stepped on the
way in stays on its initial state while the player stands in it at turn one,
which reads as a bug and gates nothing. Seed it in `before the game starts`
alongside whatever else that room needs. (Hunt the Wumpus, 3.6.0, 2026-09-11)

## `move the player` is a silent no-op in a start block

```chord
before the game starts
  change the player to the hunter
  move the player to the Shambles      ## gate-clean, and does nothing
  move the hunter to the Shambles      ## works
end before
```

The first form passes every gate and leaves the character wherever `starts in`
put them. If the same block is also placing hazards, they move and the player
does not — which is how Hunt the Wumpus first started a playthrough already
inside the slime pit. Name the character, not the role. (3.6.0, 2026-09-11)

## `phrase detail` is prose, not layout

A `detail` must carry a `while <condition>` (`analysis.detail-unconditional`:
unconditional detail belongs in the description), it appends *inside* the
description's paragraph, and it **silently drops `{br}`** — at the start of the
text, in the middle, anywhere. So a detail can never be given a line of its own.

Anything the player needs to find at a glance — an exit list, a readout — wants
a header daemon instead, whose output is its own block:

```chord
  on every turn
    phrase tunnels-cistern when the player is in the Cistern
    ...
  end on
```

A bare `on every turn` with no `while` is legal, and it correctly prints nothing
on a turn the player dies, because the kill ends the turn first. (Hunt the
Wumpus, 3.6.0, 2026-09-11)

## Computed text, if a hatch is genuinely warranted

Verified while building (and then removing) an ASCII map drawn from live world
state. Useful the next time the language truly cannot say something:

- `sharpee build` handles a hatch-bearing story — `hasHatches` selects a build
  route rather than failing it, and the build prints a notice that the bundle now
  carries author code.
- A `define text` producer can read the world. Entities are enumerable by walking
  the id space, which is **base 36** with a kind prefix (`r01`..`r0p` for 25 rooms,
  `a02` an actor, `o01` an object) — `r10` does not exist, so a decimal probe stops
  at `r09` and looks like a dead end. `entity.traits.room` carries `visited` and
  `exits`; `world.getContainingRoom(id)` locates anything.
- The prose pipeline collapses every run of whitespace. The exemption is on the
  phrase: `{ kind: 'literal', whitespace: 'verbatim', text: … }`. That puts real
  spaces in the DOM; the browser still needs `white-space: pre-wrap` from the
  author stylesheet.
- **Fixed-width text is a platform feature, but not from Chord.** `decorations.css`
  ships an ADR-174 vocabulary — `sharpee-font-mono`, `sharpee-code`,
  `sharpee-command`, plus colours, sizes, `center`, `indent`. The bracket spelling
  `[font-mono:…]` in phrase text does **not** reach it at 3.6.0; it renders
  literally in the terminal and the browser both. A hatch can attach it
  structurally, and that does produce a real span:

  ```ts
  decorations: [{ className: 'sharpee-font-mono', content: [grid] }]
  ```

(3.6.0, 2026-09-11)

## Known limits

- **A finished story used to be unrecoverable; it is not any more.** Between
  2026-09-10 and 2026-09-11 the engine stopped at `win` / `lose` / `kill the
  player` and *everything* after it — typed commands and the browser client's own
  File → Restart — threw `Engine is not running`, leaving the player with a raw
  error on every keystroke and no way back but reloading. Fixed upstream: the
  engine now answers with a message naming the meta commands that still work
  (RESTART, RESTORE, QUIT, UNDO), and RESTART after an ending yields a genuinely
  fresh game, random placement re-rolled. Verified 2026-09-12. If you meet the old
  behaviour, the toolchain is behind.


- The direction set is closed: eight compass points plus up and down. But new direction *words* are easy: `extend action going` with bare-word patterns (`fore` / `means direction north`, `aft` / south, `port` / west, `starboard` / east, plus the `go fore` forms) compiled and played correctly in No Signal Home on 2026-09-08. Where there is no exit the engine still answers "You can't go that way."
- No global action interceptor. A whole-room verb catcher exists only for death (`deadly:`); use an `on every turn while <condition>` daemon to nag instead of block.
- Chord Writer records tests documents while you play, but it is macOS only. On Windows the document is written by hand; see `tests-document.md`.

## Migrating a 3.0-era story to 3.6

The 3.0.0 draft of No Signal Home (now `no-signal-home-sharpee/legacy/story/`) failed 19 gates at 3.6.0, all mechanical; the migration was done on 2026-09-08 and these were the fixes:

| Diagnostic | Fix |
|---|---|
| `parse.header-inline-list` | `authors:` takes one name per line beneath it |
| `parse.removed-head-it` | `after examining it` becomes `after the player examining` |
| `parse.removed-create-player` | create the character by name, mark it `playable` |
| `analysis.start-block-missing` | add `before the game starts` with `change the player to <character>` |

Also since 3.0: `import "<file>"` is the single generalized import (`.chord` assumed, story-rooted paths); `import phrasebook` is gone.

## Multi-file stories

A `.story` file imports `.chord` fragments: `import "regions/harbor"`. The header stays in the `.story`; a fragment holds whole declarations only. Convention: `regions/`, `npcs/`, `voices/`. Nothing here is split yet; `hello-chord` is one file on purpose.
