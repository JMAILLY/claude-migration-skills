# Verification harness — prove the SCSS migration changed no CSS

Two Node scripts (plain `.mjs`, run on the host with `node`). One automates the
`mixed-decls` reorder; the other proves the compiled CSS is semantically
unchanged. Both are line/text based — the safety net is the semantic diff, not
the reorder.

Run all `sass` compiles **inside the node container** (host `sass` CLI is often
broken on Apple Silicon). Write outputs under the repo (mounted into the
container) so the host can read them, then clean them up.

```bash
DC="docker compose --project-directory . -f docker/compose/dev/docker-compose.yml exec -T node"
# NOTE: do not stuff the compose command in a shell var if a command-rewriting
# proxy mangles it — inline the full `docker compose … exec -T node …` instead.
```

## 1. reorder.mjs — move nested-rule-emitting includes to end of their decl run

Moves each `@include mixins.set-font-size(…)` / `@include mixins.fit-crop-element(…)`
past the contiguous same-indent declaration run that follows it, so no bare
declaration trails a nested rule. Safe *only* when the include emits no property
the caller re-declares afterward — verify with the semantic diff (§2), then hand
-fix the flagged collisions with a `& {}` wrap.

```js
import { readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

const root = process.argv[2]; // e.g. web/themes/custom/frontend/src/sass
const files = execSync(`find ${root} -name '*.scss'`).toString().trim().split('\n');

const isDecl = (t) =>
  /;\s*$/.test(t) && !t.endsWith('{') &&
  (/^[-a-zA-Z]+\s*:/.test(t) || /^@include\s/.test(t));
const isTarget = (t) =>
  /^@include\s+mixins\.(set-font-size|fit-crop-element)\b.*;\s*$/.test(t);

let total = 0;
for (const file of files) {
  const lines = readFileSync(file, 'utf8').split('\n');
  const out = [];
  let moved = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i], t = line.trim();
    if (!isTarget(t)) { out.push(line); continue; }
    const indent = line.match(/^\s*/)[0];
    let j = i + 1; const run = [];
    while (j < lines.length) {
      const l = lines[j];
      if (l.trim() === '') { run.push(l); j++; continue; }
      if (l.match(/^\s*/)[0] !== indent) break;   // dedent / deeper
      if (!isDecl(l.trim())) break;               // nested opener / selector
      run.push(l); j++;
    }
    while (run.length && run[run.length - 1].trim() === '') { run.pop(); j--; }
    if (run.filter((l) => l.trim()).length === 0) { out.push(line); continue; }
    out.push(...run, line); i = j - 1; moved++;
  }
  if (moved) { writeFileSync(file, out.join('\n')); total += moved;
    console.log(`${moved}\t${file.replace(root + '/', '')}`); }
}
console.log(`\nTotal reordered: ${total}`);
```

## 2. cssdiff.mjs — computed style per individual selector

Parses two expanded CSS files, expands every comma-group into individual
selectors, keys by `(@media/@supports context || selector)`, merges same-key
blocks last-wins (so `& {}` rule-splitting and cascade order are transparent),
and normalizes selector-list order. Prints `SEMANTIC DIFF` for any property whose
computed value changed, `MISSING RULE` for a selector present in A but not B.

```js
import { readFileSync } from 'node:fs';

function parse(css) {
  const rules = [], stack = []; let buf = '', cur = null;
  for (const c of css) {
    if (c === '{') { stack.push({ sel: buf.trim(), decls: [] }); buf = ''; cur = stack.at(-1); }
    else if (c === '}') {
      if (cur) rules.push({ path: stack.map((s) => s.sel).join(' >> '), decls: cur.decls });
      stack.pop(); cur = stack.at(-1) || null; buf = '';
    } else if (c === ';') {
      const d = buf.trim(); buf = '';
      if (cur && d.includes(':')) { const i = d.indexOf(':'); cur.decls.push([d.slice(0, i).trim(), d.slice(i + 1).trim()]); }
    } else buf += c;
  }
  return rules;
}

// key = at-rule context || individual selector; merge last-wins.
function canon(rules) {
  const map = new Map();
  for (const r of rules) {
    const levels = r.path.split(' >> ');
    const group = levels.pop();
    const ctx = levels.join(' >> ');
    for (const sel of group.split(',').map((s) => s.replace(/\s+/g, ' ').trim()).filter(Boolean)) {
      const key = ctx + '||' + sel;
      const last = map.get(key) || {};
      for (const [p, v] of r.decls) last[p] = v;
      map.set(key, last);
    }
  }
  return map;
}

const [aF, bF] = process.argv.slice(2);
const A = canon(parse(readFileSync(aF, 'utf8')));
const B = canon(parse(readFileSync(bF, 'utf8')));
let diffs = 0;
for (const [key, a] of A) {
  const b = B.get(key);
  if (!b) { console.log('MISSING RULE: ' + key); diffs++; continue; }
  for (const p of new Set([...Object.keys(a), ...Object.keys(b)]))
    if (a[p] !== b[p]) { console.log(`SEMANTIC DIFF @ ${key}\n    ${p}: "${a[p]}" -> "${b[p]}"`); diffs++; }
}
console.log(`\nDifferences: ${diffs}`);
```

## 3. Procedure

```bash
# a) GOLDEN: pre-migration source (index version, still @import) compiled in place.
cp -r <theme>/src/sass /tmp/work_sass                 # back up your migrated work
git checkout -- <theme>/src/sass                      # restore index (session-start) version
mkdir -p .cssdiff/golden
for e in style ckeditor mail; do <DC> npx sass --no-source-map --quiet <theme>/src/sass/$e.scss .cssdiff/golden/$e.css; done

# b) FINAL: restore migrated work, compile.
rm -rf <theme>/src/sass && cp -r /tmp/work_sass <theme>/src/sass
mkdir -p .cssdiff/cur
for e in style ckeditor mail; do <DC> npx sass --no-source-map --quiet <theme>/src/sass/$e.scss .cssdiff/cur/$e.css; done

# c) strip comments, diff computed style per selector.
for e in style ckeditor mail; do
  perl -0pe 's{/\*.*?\*/}{}gs' .cssdiff/golden/$e.css > .cssdiff/golden/$e.nc.css
  perl -0pe 's{/\*.*?\*/}{}gs' .cssdiff/cur/$e.css   > .cssdiff/cur/$e.nc.css
  echo "== $e =="; node cssdiff.mjs .cssdiff/golden/$e.nc.css .cssdiff/cur/$e.nc.css | grep -v MISSING | tail
done
rm -rf .cssdiff                                       # clean up (never commit it)
```

## 4. Reading the output

- **`SEMANTIC DIFF … prop: "X" -> "Y"`** — a real regression. The recurring one
  is `max-width: 118px -> none` from reordering past `fit-crop-element` (which
  sets `max-width: none`). Fix: keep the include first and `& {}`-wrap the
  override.
- **`MISSING RULE`** on long multi-context selectors — `@extend` cross-product
  redundancy the module system dropped. Benign **iff** the short covering
  selector is still present with the same declarations:
  ```bash
  grep -Fc '.paragraph--type--block-webform h3' .cssdiff/cur/style.nc.css   # > 0
  ```
  Sort missing selectors by descendant depth; if even the shallowest are 2+
  level cross-context combos, they are pure redundancy (no element loses style).
- **`Differences: 0`** on values (ignoring benign MISSING) → the migration is
  provably iso-CSS. Ship it.

## Gotchas learned the hard way

- The naive brace parser mis-attributes declarations that sit right after an
  inline `/* comment */` (keys get polluted with the comment). **Strip comments
  first** (the `perl -0pe` step) — that removed dozens of phantom diffs.
- `git status --short` counts can drift by ±1 vs `git diff --name-only` when a
  working-tree edit happens to reproduce the staged content byte-for-byte.
- A command-rewriting shell proxy may summarize/mangle `sass`/`grep` output — if
  a redirect file looks truncated, read it with the file tool or bypass the proxy.
