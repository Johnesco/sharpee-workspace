// Usage (from a game folder on Sharpee 5.7.0+): node ../tools/fold_boot_cards.mjs <id>.tests
// Moves a pre-5.7.0 tests tree: folds the 'boot' card's assertions into the 'opening' card
// (ADR-404), deletes it, and rewrites the tree canonically through @sharpee/branch-tester.
import fs from 'node:fs'; import path from 'node:path'; import url from 'node:url';
import { createRequire } from 'node:module';
const dir = path.resolve(process.argv[2]);
const req = createRequire(path.join(process.cwd(), 'x.js'));
const bt = await import(url.pathToFileURL(req.resolve('@sharpee/branch-tester')).href);
const files = {}; let n = 0;
for (const f of fs.readdirSync(dir)) {
  let text = fs.readFileSync(path.join(dir, f), 'utf8');
  const j = JSON.parse(text);
  if (Array.isArray(j.cards)) {
    const i = j.cards.findIndex(c => c.type === 'boot');
    if (i >= 0) {
      const boot = j.cards[i]; const op = j.cards.find(c => c.type === 'opening');
      for (const [k, v] of Object.entries(boot.assertions ?? {})) {
        op.assertions ??= {};
        op.assertions[k] = Array.isArray(v) ? [...(op.assertions[k] ?? []), ...v] : v;
      }
      if (boot.branches?.length) throw new Error('boot card carries branches in ' + f);
      j.cards.splice(i, 1); n++; text = JSON.stringify(j);
    }
  }
  files[f] = text;
}
const r = bt.assembleTree(files);
if (r.status !== 'ok') { console.error(r); process.exit(1); }
const out = bt.segmentTree(r.document);
for (const f of fs.readdirSync(dir)) fs.unlinkSync(path.join(dir, f));
for (const [f, t] of Object.entries(out)) fs.writeFileSync(path.join(dir, f), t);
console.log('folded', n, 'boot card(s); canonical:', bt.checkCanonicalTree(out).status ?? JSON.stringify(bt.checkCanonicalTree(out)));
