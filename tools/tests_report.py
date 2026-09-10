#!/usr/bin/env python3
"""Render a `sharpee test --json` stream into tests.html for IF Hub.

Called by tools/build.py after the tests document runs; usable by hand on a saved
stream:

    python tools/tests_report.py <run.ndjson> <id>.tests.json -o tests.html [--title T] [--version V]

The stream is `sharpee test --json --capture-output --capture-world` (ADR-277 D1):
run-start, one transcript-start / command-result... / transcript-end per line of
the tree document, then run-end. The tests document pairs each run line with the
cards that authored it, so a branch can say which card of which line it forks from.

The page discloses in four levels, each one press to open:

    line    one `details.test` per run line. The main line is open; a branch is
            collapsed unless it failed. The summary row carries verdict, card
            count, assertion tally and duration; a branch names its fork.
    card    one `details.turn-detail` per card: the turn number, the command,
            the room after the turn, what the player carries, and the tally.
            Closed unless the card failed. A card with branches shows them
            beneath it as links even while closed.
    checks  `details.turn-extras`: every assertion with its verdict and the
            runner's message on failure, a "show" button that highlights what a
            contains/exact check matched in the prose (a failed not-contains
            highlights the offending text), and the world after the turn.
    raw     the NDJSON record and the authored card, pretty-printed.

Above the lines: totals, seed, toolchain, controls (expand/collapse all,
failures only, a text filter over everything a card holds, raw records included) and a table of
lines with their forks. The class names are ifPlayer's (details.test,
summary.turn-row, pre.turn-response, .hl, button.match-toggle, ...) so the hub's
test-report theme (site/themes.js buildTestReportCSS, injected into the Tests
iframe) applies to this page unchanged; standalone it is dark by default and
takes the hub's ?theme= full-page mode through theme-listener.js.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from collections import defaultdict, deque
from pathlib import Path


# ---------------------------------------------------------------------------
# stream and document
# ---------------------------------------------------------------------------

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


def input_of(card: dict) -> str:
    """The `input` the runner reports for a card: (opening), look for boot, else the command."""
    t = card.get("type")
    if t == "opening":
        return "(opening)"
    if t == "boot":
        return "look"
    return card.get("command", "")


def doc_lines(doc: dict) -> list[dict]:
    """Flatten the tree document into lines: the main line, then every branch,
    each knowing its parent line and the card index it forks from."""
    lines: list[dict] = []

    def walk(cards: list[dict], parent: int | None, fork: int | None, branch_id) -> None:
        me = {"cards": cards, "parent": parent, "fork": fork, "branch": branch_id,
              "seq": tuple(input_of(c) for c in cards), "children": []}
        idx = len(lines)
        lines.append(me)
        if parent is not None:
            lines[parent]["children"].append(idx)
        for i, c in enumerate(cards):
            for br in c.get("branches") or []:
                walk(br.get("cards") or [], idx, i, br.get("branch"))

    walk(doc.get("cards") or [], None, None, None)
    return lines


def collect_lines(records: list[dict]) -> tuple[dict, list[dict]]:
    """Group the stream into run lines in run order. Returns (run_meta, lines)."""
    meta: dict = {"start": None, "end": None}
    lines: list[dict] = []
    by_file: dict[str, dict] = {}
    for r in records:
        t = r.get("type")
        if t == "run-start":
            meta["start"] = r
        elif t == "run-end":
            meta["end"] = r
        elif t == "transcript-start":
            line = {"file": r.get("file", ""), "index": r.get("index", len(lines)),
                    "commandCount": r.get("commandCount"), "parent": r.get("parent"),
                    "start": r, "end": None, "results": []}
            lines.append(line)
            by_file[line["file"]] = line
        elif t == "command-result":
            line = by_file.get(r.get("file"))
            if line is None:
                line = {"file": r.get("file", ""), "index": len(lines), "commandCount": None,
                        "parent": None, "start": None, "end": None, "results": []}
                lines.append(line)
                by_file[line["file"]] = line
            line["results"].append(r)
        elif t == "transcript-end":
            line = by_file.get(r.get("file"))
            if line is not None:
                line["end"] = r
    return meta, lines


def pair_lines(run_lines: list[dict], dlines: list[dict]) -> None:
    """Attach the authored line (`doc`) to each run line by matching the command
    sequence, first come first served. Unmatched lines render without card data."""
    pool: dict[tuple, deque] = defaultdict(deque)
    for i, d in enumerate(dlines):
        pool[d["seq"]].append(i)
    for line in run_lines:
        seq = tuple(r.get("input", "") for r in line["results"])
        q = pool.get(seq)
        line["doc_index"] = q.popleft() if q else None
        line["doc"] = dlines[line["doc_index"]] if line["doc_index"] is not None else None
    by_doc = {line["doc_index"]: line for line in run_lines if line["doc_index"] is not None}
    for line in run_lines:
        line["by_doc"] = by_doc


# ---------------------------------------------------------------------------
# assertions and highlights
# ---------------------------------------------------------------------------

def unquote(s: str) -> str:
    s = s.strip()
    if s.startswith('"'):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return s.strip('"')
    return s


def parse_assertion(a: dict, idx: int) -> dict:
    d = a.get("description", "") or ""
    kind, expected = "other", d
    if d.startswith("not contains "):
        kind, expected = "not contains", unquote(d[len("not contains "):])
    elif d.startswith("contains "):
        kind, expected = "contains", unquote(d[len("contains "):])
    elif d.startswith("exact output"):
        kind, expected = "exact", d
    elif d.startswith("state "):
        kind, expected = "state", d[len("state "):]
    elif d.startswith("event "):
        kind, expected = "event", d[len("event "):]
    elif d.startswith("channel "):
        kind, expected = "channel", d[len("channel "):]
    return {"idx": idx, "kind": kind, "expected": expected, "passed": bool(a.get("passed")),
            "message": a.get("message"), "description": d}


def find_all(text: str, needle: str) -> list[tuple[int, int]]:
    spans, pos = [], 0
    if not needle:
        return spans
    while True:
        i = text.find(needle, pos)
        if i < 0:
            return spans
        spans.append((i, i + len(needle)))
        pos = i + len(needle)


def highlight(output: str, assertions: list[dict]) -> tuple[str, set[int]]:
    """Wrap what each check matched in <span class="hl" data-asserts="i j">.
    Returns the HTML and the set of assertion indexes that have something to show."""
    spans: list[tuple[int, int, int, bool]] = []
    for a in assertions:
        if a["kind"] == "contains" and a["passed"]:
            spans += [(s, e, a["idx"], False) for s, e in find_all(output, a["expected"])]
        elif a["kind"] == "not contains" and not a["passed"]:
            spans += [(s, e, a["idx"], True) for s, e in find_all(output, a["expected"])]
        elif a["kind"] == "exact" and a["passed"] and output:
            spans.append((0, len(output), a["idx"], False))
    showable = {i for _, _, i, _ in spans}
    if not spans:
        return html.escape(output), showable
    bounds = sorted({0, len(output)} | {s for s, _, _, _ in spans} | {e for _, e, _, _ in spans})
    out = []
    for b0, b1 in zip(bounds, bounds[1:]):
        covering = [(i, f) for s, e, i, f in spans if s <= b0 and e >= b1]
        seg = html.escape(output[b0:b1])
        if covering:
            ids = " ".join(str(i) for i in sorted({i for i, _ in covering}))
            cls = "hl hl-fail" if any(f for _, f in covering) else "hl"
            out.append(f'<span class="{cls}" data-asserts="{ids}">{seg}</span>')
        else:
            out.append(seg)
    return "".join(out), showable


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def status_of(r: dict) -> str:
    if r.get("skipped"):
        return "skip"
    return "pass" if r.get("passed") else "fail"


GLYPH = {"pass": "&#10003;", "fail": "&#10007;", "skip": "&ndash;"}


def card_json(card: dict | None) -> str:
    if not card:
        return ""
    c = dict(card)
    if c.get("branches"):
        c["branches"] = f"[{len(c['branches'])} branch(es), rendered as their own lines]"
    return json.dumps(c, indent=2, ensure_ascii=False)


def render_card(r: dict, card: dict | None, forks: list[dict]) -> tuple[str, int, int]:
    """One li.turn. Returns (html, assertions, assertions_passed)."""
    status = status_of(r)
    inp = r.get("input", "")
    ctype = (card or {}).get("type") or ("opening" if inp == "(opening)" else "turn")
    if ctype == "opening":
        cmd_label = "(opening)"
    elif ctype == "boot":
        cmd_label = "look  (boot)"
    else:
        cmd_label = inp
    turn = r.get("turn")
    tcount = f"T:{turn}" if turn is not None else "&mdash;"
    world = r.get("world") or {}
    room = ((world.get("location") or {}).get("name")) or ""
    inventory = [i.get("name", "") for i in (world.get("inventory") or [])]
    assertions = [parse_assertion(a, i) for i, a in enumerate(r.get("assertionResults") or [])]
    n = len(assertions)
    n_ok = sum(1 for a in assertions if a["passed"])
    output = (r.get("actualOutput") or "").strip()
    prose, showable = highlight(output, assertions)

    tally_cls = "skip" if status == "skip" else ("pass" if n_ok == n else "fail")
    tally = f"{GLYPH[tally_cls]} {n_ok}/{n}" if n else "&ndash;"
    inv_label = f"{len(inventory)} carried" if inventory else ""

    parts = [f'<li class="turn" data-status="{status}">',
             f'<details class="turn-detail" data-status="{status}"{" open" if status == "fail" else ""}>',
             f'<summary class="turn-row"><span class="turn-tcount">{tcount}</span>'
             f'<span class="turn-cmd">&gt; {esc(cmd_label)}</span>'
             f'<span class="turn-room">{esc(room)}</span>'
             f'<span class="turn-inv" title="{esc(", ".join(inventory) or "carrying nothing")}">{inv_label}</span>'
             f'<span class="turn-asserts"><span class="{tally_cls}">{tally}</span></span></summary>',
             '<div class="turn-body">']
    if output:
        parts.append(f'<pre class="turn-response">{prose}</pre>')
    elif ctype == "opening":
        parts.append('<pre class="turn-response empty">(the opening card checks what the client shows before play; no prose)</pre>')
    else:
        parts.append('<pre class="turn-response empty">(no output)</pre>')
    if r.get("expectedFailure"):
        parts.append('<div class="note">expected failure</div>')

    extras_open = " open" if status == "fail" else ""
    world_bits = f' &middot; {esc(room)}' if room else ""
    carried = f" &middot; {len(inventory)} carried" if world else ""
    parts.append(f'<details class="turn-extras"{extras_open}><summary class="turn-extras-summary">'
                 f'{n} check{"s" if n != 1 else ""} {GLYPH["pass" if n_ok == n else "fail"]}'
                 f'{world_bits}{carried} &middot; raw</summary><div class="turn-extras-body">')
    if assertions:
        parts.append('<h4>Checks</h4><ul class="assertions">')
        for a in assertions:
            cls = "pass" if a["passed"] else "fail"
            parts.append(f'<li class="{cls}"><span class="kind">{esc(a["kind"])}</span>'
                         f'<span class="label">{esc(a["expected"])}</span>')
            if a["idx"] in showable:
                parts.append(f'<button type="button" class="match-toggle" data-assertion-idx="{a["idx"]}">show</button>')
            if not a["passed"] and a.get("message"):
                parts.append(f'<div class="message">{esc(a["message"])}</div>')
            parts.append("</li>")
        parts.append("</ul>")
    else:
        parts.append('<h4>Checks</h4><div class="note">no assertions on this card</div>')
    if world:
        parts.append('<h4>World after this turn</h4><dl class="kv">')
        parts.append(f'<dt>Location</dt><dd>{esc(room) or "&mdash;"}</dd>')
        parts.append(f'<dt>Carrying</dt><dd>{esc(", ".join(inventory)) if inventory else "nothing"}</dd></dl>')
    parts.append('<details class="raw"><summary>Raw: the runner record and the authored card</summary>')
    parts.append(f'<pre class="raw-json">{esc(json.dumps(r, indent=2, ensure_ascii=False))}</pre>')
    if card:
        parts.append(f'<pre class="raw-json">{esc(card_json(card))}</pre>')
    parts.append("</details></div></details></div></details>")
    for f in forks:
        parts.append(f'<div class="fork">&#8627; branch <a href="#line-{f["index"]}">{esc(f["label"])}</a> '
                     f'&middot; {f["cards"]} card{"s" if f["cards"] != 1 else ""} '
                     f'<span class="{f["status"]}">{GLYPH[f["status"]]}</span></div>')
    parts.append("</li>")
    return "".join(parts), n, n_ok


def line_status(line: dict) -> str:
    end = line.get("end") or {}
    if end.get("status") == "failed" or any(status_of(r) == "fail" for r in line["results"]):
        return "fail"
    return "pass"


def line_label(line: dict) -> str:
    return line.get("file") or f"line {line.get('index')}"


def fork_of(line: dict) -> dict | None:
    """For a branch: the run line and card it forks from, when the pairing knows."""
    d = line.get("doc")
    if not d or d["parent"] is None:
        return None
    parent_run = line["by_doc"].get(d["parent"])
    if parent_run is None:
        return None
    fork_i = d["fork"]
    parent_results = parent_run["results"]
    rec = parent_results[fork_i] if fork_i is not None and fork_i < len(parent_results) else None
    return {"index": parent_run["index"], "label": line_label(parent_run), "card_no": fork_i,
            "turn": (rec or {}).get("turn"), "command": (rec or {}).get("input", "")}


def replayed_commands(line: dict, dlines: list[dict]) -> int:
    """How many commands the runner replays before this line's own cards."""
    d = line.get("doc")
    total = 0
    while d and d["parent"] is not None:
        parent = dlines[d["parent"]]
        total += sum(1 for c in parent["cards"][: (d["fork"] or 0) + 1] if c.get("type") != "opening")
        d = parent
    return total


def render(records: list[dict], doc: dict, title: str, version: str, doc_name: str,
           exit_code: int) -> tuple[str, dict]:
    meta, run_lines = collect_lines(records)
    dlines = doc_lines(doc) if doc else []
    pair_lines(run_lines, dlines)

    # which branch run lines hang on which (run line, card index)
    forks_at: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for line in run_lines:
        d = line.get("doc")
        if d and d["parent"] is not None:
            parent_run = line["by_doc"].get(d["parent"])
            if parent_run is not None:
                forks_at[(parent_run["index"], d["fork"])].append(
                    {"index": line["index"], "label": line_label(line),
                     "cards": len(line["results"]), "status": line_status(line)})

    cards = cards_ok = asserts = asserts_ok = 0
    lines_ok = 0
    sections, rows = [], []
    for line in run_lines:
        st = line_status(line)
        lines_ok += st == "pass"
        d = line.get("doc")
        results = line["results"]
        n_cards = len(results)
        n_cards_ok = sum(1 for r in results if status_of(r) != "fail")
        end = line.get("end") or {}
        ms = end.get("duration")
        is_main = (d is None and line["index"] == 0) or (d is not None and d["parent"] is None)
        fork = None if is_main else fork_of(line)
        replayed = replayed_commands(line, dlines) if d else 0

        if is_main:
            kind, note = "main line", ""
        elif fork:
            kind = "branch"
            note = (f'Replays <a href="#line-{fork["index"]}">{esc(fork["label"])}</a> through '
                    f'T:{fork["turn"]} <code>&gt; {esc(fork["command"])}</code> '
                    f'({replayed} command{"s" if replayed != 1 else ""} replayed, none re-asserted), then diverges.')
        else:
            kind = "branch"
            note = f'Branch of {esc(line.get("parent") or "the main line")}.'

        card_html = []
        for i, r in enumerate(results):
            card = d["cards"][i] if d and i < len(d["cards"]) else None
            h, n, n_ok = render_card(r, card, forks_at.get((line["index"], i), []))
            card_html.append(h)
            cards += 1
            cards_ok += status_of(r) != "fail"
            asserts += n
            asserts_ok += n_ok

        meta_bits = [kind, f"{n_cards} card{'s' if n_cards != 1 else ''}",
                     f"{n_cards_ok}/{n_cards} {GLYPH['pass' if n_cards_ok == n_cards else 'fail']}"]
        if ms is not None:
            meta_bits.append(f"{ms} ms")
        open_attr = " open" if (is_main or st == "fail") else ""
        sections.append(
            f'<details class="test" id="line-{line["index"]}" data-status="{st}"{open_attr}>'
            f'<summary class="test-summary"><span class="glyph {st}">{GLYPH[st]}</span>'
            f'<span class="test-name">{esc(line_label(line))}</span>'
            f'<span class="test-summary-meta">{" &middot; ".join(meta_bits)}</span></summary>'
            f'<div class="test-body">' + (f'<div class="line-note">{note}</div>' if note else "") +
            '<ul class="transcript">' + "".join(card_html) + "</ul></div></details>")
        if is_main:
            forks_from = "&mdash;"
        elif fork:
            forks_from = f'{esc(fork["label"])} &middot; T:{fork["turn"]} {esc(fork["command"])}'
        else:
            forks_from = esc(line.get("parent") or "")
        rows.append(
            f'<tr class="{st}"><td><a href="#line-{line["index"]}">{esc(line_label(line))}</a></td>'
            f'<td>{forks_from}</td>'
            f'<td class="num">{n_cards}</td><td class="num pass">{n_cards_ok}</td>'
            f'<td class="num {"fail" if n_cards - n_cards_ok else ""}">{n_cards - n_cards_ok}</td>'
            f'<td class="num">{ms if ms is not None else ""}</td></tr>')

    end = meta.get("end") or {}
    status = "PASS" if exit_code == 0 and asserts_ok == asserts and cards_ok == cards else "FAIL"
    when = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    total_ms = end.get("totalDuration")
    seed = doc.get("seed") if doc else None
    n_lines = len(run_lines)

    summary = (
        '<div class="summary">'
        f'<div class="item"><span class="num status {status}">{status}</span></div>'
        f'<div class="item"><span class="num pass-num">{lines_ok}</span><span class="label">lines passed</span></div>'
        f'<div class="item"><span class="num {"fail-num" if n_lines - lines_ok else ""}">{n_lines - lines_ok}</span><span class="label">lines failed</span></div>'
        f'<div class="item"><span class="num pass-num">{cards_ok}</span><span class="label">cards passed</span></div>'
        f'<div class="item"><span class="num {"fail-num" if cards - cards_ok else ""}">{cards - cards_ok}</span><span class="label">cards failed</span></div>'
        f'<div class="item"><span class="num pass-num">{asserts_ok}</span><span class="label">of {asserts} assertions</span></div>'
        + (f'<div class="item"><span class="num">{total_ms}</span><span class="label">ms</span></div>' if total_ms is not None else "")
        + "</div>")
    games = (f'<div class="games"><span class="relpath">{esc(doc_name)}</span>'
             + (f'<span class="seed">seed {esc(seed)}</span>' if seed is not None else "")
             + f'<span>{esc(version)}</span><span>generated {when}</span>'
             + f'<span>{esc(end.get("totalUnreached", 0))} unreached &middot; {esc(end.get("totalSkipped", 0))} skipped &middot; {esc(end.get("totalErrors", 0))} errors</span></div>')
    controls = (
        '<div class="controls">'
        '<button type="button" id="expand-all">Expand all</button>'
        '<button type="button" id="collapse-all">Collapse all</button>'
        '<label><input type="checkbox" id="failures-only"> failures only</label>'
        '<input type="search" id="filter" placeholder="filter cards: command, prose, checks, room, item" aria-label="filter cards">'
        '<span class="hint" id="filter-hint"></span></div>')
    lines_table = (
        '<h2>Lines</h2><table class="lines"><thead><tr><th>line</th><th>forks from</th>'
        '<th class="num">cards</th><th class="num">passed</th><th class="num">failed</th><th class="num">ms</th></tr></thead>'
        '<tbody>' + "".join(rows) + '</tbody></table>')

    page = (PAGE_HEAD.replace("@@TITLE@@", esc(title))
            + f'<div class="wrap"><h1>{esc(title)} &mdash; test report</h1>'
            f'<div class="subtitle">{n_lines} line{"s" if n_lines != 1 else ""} &middot; {cards} cards &middot; {asserts} assertions'
            f'{" &middot; " + str(total_ms) + " ms" if total_ms is not None else ""}</div>'
            + summary + games + controls + lines_table
            + '<h2>Tests</h2><div class="tests">' + "".join(sections) + "</div></div>"
            + PAGE_TAIL)
    stats = {"cards": cards, "cards_ok": cards_ok, "asserts": asserts, "asserts_ok": asserts_ok,
             "lines": n_lines, "lines_ok": lines_ok, "status": status}
    return page, stats


# ---------------------------------------------------------------------------
# page chrome
# ---------------------------------------------------------------------------

PAGE_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@ &mdash; tests</title>
<style>
:root { --bg: #101418; --fg: #d8dee6; --muted: #7f8b99; --line: #232b35; --pass: #6fcf7f; --pass-bg: rgba(111,207,127,.12);
  --fail: #ff7a7a; --fail-bg: rgba(255,122,122,.14); --warn: #e0b458; --accent: #8fd3ff; --code-bg: #161c23; --hover: #1a2129;
  --hl-bg: rgba(255,232,138,.3); --hl-fg: #ffe88a; --room: #c49ee0; --ui-font: Georgia, "Times New Roman", serif; --mono: ui-monospace, Consolas, monospace; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.5 var(--ui-font); }
.wrap { max-width: 980px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.subtitle { color: var(--muted); font: 13px var(--mono); margin-bottom: 14px; }
.summary { display: flex; flex-wrap: wrap; gap: 12px 24px; border: 1px solid var(--line); border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; background: var(--code-bg); }
.summary .item { display: flex; align-items: baseline; gap: 6px; }
.summary .num { font: bold 18px var(--mono); }
.summary .pass-num { color: var(--pass); } .summary .fail-num { color: var(--fail); }
.summary .label { color: var(--muted); font: 12px var(--mono); text-transform: uppercase; letter-spacing: .06em; }
.status.PASS { color: var(--pass); } .status.FAIL { color: var(--fail); }
.games { font: 13px var(--mono); color: var(--muted); margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin: 0 0 6px; font: 13px var(--mono); }
.controls button, button.match-toggle { font: 12px var(--mono); color: var(--fg); background: var(--code-bg); border: 1px solid var(--line); border-radius: 4px; padding: 3px 8px; cursor: pointer; }
.controls button:hover, button.match-toggle:hover { background: var(--hover); }
.controls input[type=search] { font: 13px var(--mono); color: var(--fg); background: var(--code-bg); border: 1px solid var(--line); border-radius: 4px; padding: 4px 8px; min-width: 260px; }
.controls label { display: flex; gap: 6px; align-items: center; cursor: pointer; }
.controls .hint { color: var(--muted); font-size: 12px; }
h2 { font-size: 13px; font-family: var(--mono); color: var(--muted); letter-spacing: .06em; text-transform: uppercase; margin: 24px 0 10px; }
table.lines { border-collapse: collapse; width: 100%; font: 13px var(--mono); }
table.lines th, table.lines td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
table.lines th { color: var(--muted); font-weight: normal; }
table.lines th.num, table.lines td.num { text-align: right; }
table.lines td.pass { color: var(--pass); } table.lines td.fail { color: var(--fail); }
table.lines a, .line-note a, .fork a { color: var(--accent); text-decoration: none; }
table.lines a:hover, .line-note a:hover, .fork a:hover { text-decoration: underline; }
details.test { border: 1px solid var(--line); border-radius: 6px; margin: 0 0 12px; background: var(--code-bg); }
summary { cursor: pointer; list-style: none; }
summary::-webkit-details-marker { display: none; }
summary.test-summary { display: flex; gap: 10px; align-items: center; padding: 8px 12px; font: 14px var(--mono); }
summary.test-summary::before { content: "\\25B8"; color: var(--muted); width: 1em; }
details.test[open] > summary.test-summary::before { content: "\\25BE"; }
.glyph.pass { color: var(--pass); } .glyph.fail { color: var(--fail); } .glyph.skip { color: var(--muted); }
.test-name { font-weight: bold; }
.test-summary-meta { color: var(--muted); margin-left: auto; font-size: 12px; text-align: right; }
.test-body { border-top: 1px solid var(--line); }
.line-note { padding: 6px 12px; color: var(--muted); font: 12px var(--mono); border-bottom: 1px solid var(--line); }
.line-note code { color: var(--accent); }
ul.transcript { list-style: none; margin: 0; padding: 0; }
li.turn { border-bottom: 1px solid var(--line); }
li.turn:last-child { border-bottom: 0; }
summary.turn-row { display: grid; grid-template-columns: 4.5em minmax(10em, 1fr) minmax(6em, auto) auto 5em; gap: 10px; align-items: baseline; padding: 5px 12px; font: 13px var(--mono); }
summary.turn-row:hover { background: var(--hover); }
details.turn-detail[data-status="fail"] > summary.turn-row { background: var(--fail-bg); }
.turn-tcount { color: var(--muted); }
.turn-cmd { color: var(--accent); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.turn-room { color: var(--room); font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.turn-inv { color: var(--muted); font-size: 12px; text-align: right; }
.turn-asserts { text-align: right; }
.turn-asserts .pass, .fork .pass { color: var(--pass); } .turn-asserts .fail, .fork .fail { color: var(--fail); } .turn-asserts .skip { color: var(--muted); }
.turn-body { padding: 6px 12px 10px 5.5em; }
pre.turn-response { white-space: pre-wrap; margin: 4px 0 8px; font: inherit; color: var(--fg); }
pre.turn-response.empty { color: var(--muted); font-style: italic; }
.hl.hl-active { background: var(--hl-bg); color: var(--hl-fg); box-shadow: 0 0 0 1px var(--hl-fg); border-radius: 2px; }
.hl.hl-active.hl-fail { background: var(--fail-bg); color: var(--fail); box-shadow: 0 0 0 1px var(--fail); }
details.turn-extras > summary { font: 12px var(--mono); color: var(--muted); padding: 2px 0; }
details.turn-extras > summary::before { content: "\\25B8 "; }
details.turn-extras[open] > summary::before { content: "\\25BE "; }
.turn-extras-body { padding: 4px 0 0 1em; }
h4 { margin: 8px 0 4px; font: 12px var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.note { color: var(--muted); font: 12px var(--mono); }
ul.assertions { list-style: none; margin: 0; padding: 0; font: 13px var(--mono); }
ul.assertions li { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; padding: 2px 0; }
ul.assertions li.pass > .label::before { content: "\\2713 "; color: var(--pass); }
ul.assertions li.fail > .label::before { content: "\\2717 "; color: var(--fail); }
ul.assertions .kind { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; min-width: 7em; }
ul.assertions .label { white-space: pre-wrap; }
ul.assertions .message { flex-basis: 100%; color: var(--fail); padding-left: 7.7em; white-space: pre-wrap; }
button.match-toggle.active { background: var(--hl-bg); color: var(--hl-fg); border-color: var(--hl-fg); }
li.fail button.match-toggle.active { background: var(--fail-bg); color: var(--fail); border-color: var(--fail); }
dl.kv { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; margin: 0; font: 13px var(--mono); }
dl.kv dt { color: var(--muted); } dl.kv dd { margin: 0; }
details.raw > summary { font: 12px var(--mono); color: var(--muted); margin-top: 8px; }
details.raw > summary::before { content: "\\25B8 "; } details.raw[open] > summary::before { content: "\\25BE "; }
pre.raw-json { font: 12px/1.4 var(--mono); background: var(--bg); border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px; overflow: auto; max-height: 26em; margin: 4px 0; }
.fork { padding: 2px 12px 6px 5.5em; font: 12px var(--mono); color: var(--muted); }
body.failures-only li.turn[data-status="pass"], body.failures-only li.turn[data-status="skip"], body.failures-only details.test[data-status="pass"] { display: none; }
li.turn.filtered-out, details.test.filtered-out { display: none; }
@media (max-width: 640px) { summary.turn-row { grid-template-columns: 3.5em 1fr auto; } .turn-room, .turn-inv { display: none; } .turn-body, .fork { padding-left: 12px; } }
</style>
</head>
<body>
"""

PAGE_TAIL = """
<script>
(function () {
  // "show" on a check highlights what it matched in the prose; radio-style per card.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.match-toggle');
    if (!btn) return;
    var turn = btn.closest('.turn-detail');
    if (!turn) return;
    var idx = btn.getAttribute('data-assertion-idx');
    var wasActive = btn.classList.contains('active');
    turn.querySelectorAll('.match-toggle.active').forEach(function (b) { b.classList.remove('active'); });
    turn.querySelectorAll('.hl.hl-active').forEach(function (s) { s.classList.remove('hl-active'); });
    if (wasActive) return;
    btn.classList.add('active');
    turn.querySelectorAll('.hl').forEach(function (span) {
      var ids = (span.getAttribute('data-asserts') || '').split(' ');
      if (ids.indexOf(idx) >= 0) span.classList.add('hl-active');
    });
  });
  var all = function (sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); };
  document.getElementById('expand-all').addEventListener('click', function () {
    all('details').forEach(function (d) { d.open = true; });
  });
  document.getElementById('collapse-all').addEventListener('click', function () {
    all('details').forEach(function (d) { d.open = false; });
  });
  document.getElementById('failures-only').addEventListener('change', function (e) {
    document.body.classList.toggle('failures-only', e.target.checked);
  });
  var hint = document.getElementById('filter-hint');
  document.getElementById('filter').addEventListener('input', function (e) {
    var q = e.target.value.trim().toLowerCase();
    var shown = 0, total = 0;
    all('li.turn').forEach(function (li) {
      total += 1;
      var hit = !q || (li.textContent || '').toLowerCase().indexOf(q) >= 0;
      li.classList.toggle('filtered-out', !hit);
      if (hit) shown += 1;
      if (hit && q.length >= 2) { var d = li.querySelector('details.turn-detail'); if (d) d.open = true; }
    });
    all('details.test').forEach(function (t) {
      var visible = t.querySelectorAll('li.turn:not(.filtered-out)').length;
      t.classList.toggle('filtered-out', !!q && !visible);
      if (q && visible) t.open = true;
    });
    hint.textContent = q ? shown + ' of ' + total + ' cards match' : '';
  });
})();
</script>
<script src="theme-listener.js"></script>
<script>
if (window.ThemeListener) ThemeListener.init({
  buildCSS: function (g, sb) {
    return ':root { --bg: ' + g.bodyBg + ' !important; --fg: ' + g.bufferFg + ' !important; --muted: ' + g.gridFg +
      ' !important; --accent: ' + g.inputFg + ' !important; --code-bg: ' + g.bufferBg + ' !important; --line: ' + g.gridBg +
      ' !important; --mono: ' + g.monoFamily + ' !important; }\\n' +
      'body { background: ' + g.bodyBg + ' !important; color: ' + g.bufferFg + ' !important; }\\n' +
      '* { scrollbar-color: ' + sb.thumb + ' ' + sb.track + '; }\\n';
  },
  dispatchResize: false
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Render a sharpee test --json stream into tests.html.")
    ap.add_argument("stream", help="NDJSON from sharpee test --json --capture-output --capture-world")
    ap.add_argument("doc", nargs="?", help="the <id>.tests.json the stream ran (optional)")
    ap.add_argument("-o", "--out", default="tests.html")
    ap.add_argument("--title", default=None)
    ap.add_argument("--version", default="Sharpee")
    ap.add_argument("--exit-code", type=int, default=0)
    args = ap.parse_args()
    records = parse_ndjson(Path(args.stream).read_text(encoding="utf-8"))
    doc = json.loads(Path(args.doc).read_text(encoding="utf-8")) if args.doc else {}
    title = args.title or (doc.get("story") if doc else Path(args.stream).stem)
    page, stats = render(records, doc, title=title, version=args.version,
                         doc_name=Path(args.doc).name if args.doc else "", exit_code=args.exit_code)
    Path(args.out).write_text(page, encoding="utf-8")
    print(f"{args.out}: {stats['status']} {stats['cards_ok']}/{stats['cards']} cards, "
          f"{stats['asserts_ok']}/{stats['asserts']} assertions, {stats['lines_ok']}/{stats['lines']} lines")


if __name__ == "__main__":
    main()
