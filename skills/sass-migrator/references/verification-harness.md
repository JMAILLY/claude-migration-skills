# Verification harness — prove the SCSS migration changed no CSS

Six Node scripts (plain `.mjs`). `compile.mjs` runs **inside the node
container** (it needs the project's `sass` and `fast-glob`); the others only
read/write files and run on the host with `node`.

| Script | Role |
|---|---|
| `compile.mjs` | compile every entrypoint (expanded, comments stripped) + tally ALL warnings by deprecation type |
| `cssdiff.mjs` | computed value per individual selector, last-wins (catches value changes, missing/added rules) |
| `strict.mjs` | order-aware: same rule sequence, same declarations, no reordered pair of interacting properties |
| `culprits.mjs` | classify `mixed-decls` sites by the include that precedes them |
| `reorder.mjs` | move nested-rule-emitting includes past the following plain-declaration run |
| `hook.mjs` | turn a flagged site into the `@content`-slot form |

Write everything under a scratch folder **inside the repo** (mounted into the
container, e.g. `.cssdiff/`), never commit it, delete it at the end.

```bash
# Inline the compose command. In zsh a "$DC" variable is NOT word-split
# ("no such file or directory: docker compose …"), and a command-rewriting
# proxy may mangle it anyway.
docker compose --project-directory . -f docker/compose/dev/docker-compose.yml exec -T node node .cssdiff/compile.mjs <sass-root> .cssdiff/golden
```

## 1. compile.mjs — every entrypoint + full warning tally

Globs every non-partial under `<sass-root>` (adapt the glob/ignore to the
build's real groups), compiles expanded with `verbose: true` (otherwise
repetitive warnings are truncated), strips comments (the parsers below choke on
them), writes `<out>/<rel>.css` and `<out>.warnings.tsv`
(`type  entry  file:line  message`).

```js
import * as sass from 'sass';
import fg from 'fast-glob';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const [base, out] = process.argv.slice(2);
const files = (await fg(`${base}/**/*.scss`, { ignore: ['**/_*.scss'] })).sort();
const counts = {}; const seen = []; let errors = 0;
for (const f of files) {
  const rel = path.relative(base, f).replace(/\.scss$/, '.css');
  try {
    const r = sass.compile(f, { style: 'expanded', charset: false, verbose: true, logger: {
      warn(msg, o) {
        const id = o.deprecationType?.id || (o.deprecation ? 'deprecation' : 'warn');
        counts[id] = (counts[id] || 0) + 1;
        const at = o.span ? `${o.span.url?.pathname.replace(/.*src\/sass\//, '')}:${o.span.start.line + 1}` : '';
        seen.push(`${id}\t${rel}\t${at}\t${msg.split('\n')[0]}`);
      },
      debug() {} } });
    mkdirSync(path.dirname(`${out}/${rel}`), { recursive: true });
    writeFileSync(`${out}/${rel}`, r.css.replace(/\/\*[\s\S]*?\*\//g, ''));
  } catch (e) { errors++; console.log(`ERROR ${rel}: ${e.message.split('\n').slice(0, 6).join(' | ')}`); }
}
writeFileSync(`${out}.warnings.tsv`, seen.join('\n'));
console.log(`files=${files.length} errors=${errors}`, counts);
```

Group the sites: `cut -f1,3 .cssdiff/cur.warnings.tsv | sort | uniq -c`.

## 2. cssdiff.mjs — computed value per individual selector

Expands every comma-group into individual selectors, keys by
`(@media/@supports context || selector)`, merges same-key blocks last-wins and
normalizes selector-list order. Prints `SEMANTIC DIFF` for any property whose
value changed, `MISSING RULE` for a selector present in A but not in B. Run it
**both ways**: `B A` lists the rules that were *added*.

Blind spot: it compares per property *name*, so `padding: 20px 0` swapping
places with `padding-left: 16px` is invisible. That is what `strict.mjs` is for.

```js
import { readFileSync } from 'node:fs';

function parse(css) {
  const rules = [], stack = []; let buf = '', cur = null;
  for (const c of css) {
    if (c === '{') { stack.push({ sel: buf.trim(), decls: [] }); buf = ''; cur = stack.at(-1); }
    else if (c === '}') {
      const d = buf.trim();
      if (cur && d.includes(':')) { const i = d.indexOf(':'); cur.decls.push([d.slice(0, i).trim(), d.slice(i + 1).trim()]); }
      if (cur) rules.push({ path: stack.map((s) => s.sel).join(' >> '), decls: cur.decls });
      stack.pop(); cur = stack.at(-1) || null; buf = '';
    } else if (c === ';') {
      const d = buf.trim(); buf = '';
      if (cur && d.includes(':')) { const i = d.indexOf(':'); cur.decls.push([d.slice(0, i).trim(), d.slice(i + 1).trim()]); }
    } else buf += c;
  }
  return rules;
}

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

## 3. strict.mjs — order-aware check

Requires the same sequence of rules (context + selector list) and, per rule,
the same multiset of declarations; then flags every pair of **interacting**
declarations whose relative order changed (same property, shorthand/longhand
such as `padding`/`padding-left`, `font`/`line-height`, `inset`/sides,
`gap`/`row-gap`). Non-interacting permutations (`font-size` vs `line-height`)
are counted as `permuted` but are not issues. `--normalize` sorts each
selector list, for comparing against the golden after `@extend` reshuffles.
It stops at the first rule-order mismatch — strip a known, accepted rule from
a copy to check the rest.

```js
import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const normalize = args.includes('--normalize');
const [aF, bF] = args.filter((a) => !a.startsWith('--'));

function parse(css) {
  const rules = [], stack = []; let buf = '';
  for (const c of css) {
    if (c === '{') {
      let sel = buf.trim().replace(/\s+/g, ' ');
      if (normalize) sel = sel.split(/\s*,\s*/).sort().join(', ');
      stack.push({ sel, decls: [] }); buf = '';
    } else if (c === '}') {
      const d = buf.trim();
      if (stack.length && d.includes(':')) stack.at(-1).decls.push(d.replace(/\s+/g, ' '));
      const r = stack.pop();
      if (r && r.decls.length) rules.push({ key: [...stack.map((s) => s.sel), r.sel].join(' >> '), decls: r.decls });
      buf = '';
    } else if (c === ';') {
      const d = buf.trim(); buf = '';
      if (stack.length && d.includes(':')) stack.at(-1).decls.push(d.replace(/\s+/g, ' '));
    } else buf += c;
  }
  return rules;
}

const prop = (d) => d.slice(0, d.indexOf(':')).trim().replace(/^-(webkit|moz|ms|o)-/, '');
const EXTRA = { 'line-height': ['font'], top: ['inset'], right: ['inset'], bottom: ['inset'], left: ['inset'], 'row-gap': ['gap'], 'column-gap': ['gap'] };
const conflicts = (x, y) => {
  const p = prop(x), q = prop(y);
  return p === q || p.startsWith(q + '-') || q.startsWith(p + '-') || (EXTRA[p] || []).includes(q) || (EXTRA[q] || []).includes(p);
};

const A = parse(readFileSync(aF, 'utf8')), B = parse(readFileSync(bF, 'utf8'));
let issues = 0, permuted = 0;
if (A.length !== B.length) { console.log(`RULE COUNT ${A.length} -> ${B.length}`); issues++; }
for (let i = 0; i < Math.min(A.length, B.length); i++) {
  const a = A[i], b = B[i];
  if (a.key !== b.key) { console.log(`RULE ORDER #${i}: ${a.key}  <>  ${b.key}`); issues++; break; }
  if (a.decls.join(';') === b.decls.join(';')) continue;
  permuted++;
  if ([...a.decls].sort().join(';') !== [...b.decls].sort().join(';')) {
    console.log(`DECL SET @ ${a.key}\n  ${a.decls.join('; ')}\n  ${b.decls.join('; ')}`); issues++; continue;
  }
  const tag = (l) => { const seen = {}; return l.map((d) => `${d}#${(seen[d] = (seen[d] || 0) + 1)}`); };
  const ta = tag(a.decls), tb = tag(b.decls), pos = Object.fromEntries(tb.map((d, j) => [d, j]));
  for (let x = 0; x < ta.length; x++) for (let y = x + 1; y < ta.length; y++)
    if (conflicts(ta[x], ta[y]) && pos[ta[x]] > pos[ta[y]]) {
      console.log(`ORDER FLIP @ ${a.key}\n  "${ta[x]}" now after "${ta[y]}"`); issues++;
    }
}
console.log(`rules=${A.length} permuted=${permuted} issues=${issues}`);
```

## 4. culprits.mjs — which include causes each mixed-decls site

Reads `<out>.warnings.tsv`, walks up from each warning line to the nearest
same-indent `@include` (or a closing `}` = child rule). Adjust the mixin
pattern and the sass root to the theme.

```js
import { readFileSync } from 'node:fs';

const [tsv, base] = process.argv.slice(2); // .cssdiff/cur.warnings.tsv web/themes/custom/frontend/src/sass/
const sites = [...new Set(readFileSync(tsv, 'utf8').trim().split('\n')
  .filter((l) => l.startsWith('mixed-decls')).map((l) => l.split('\t')[2]))];
const out = {};
for (const s of sites) {
  const [f, n] = s.split(':');
  const lines = readFileSync(base + f, 'utf8').split('\n');
  const ind = lines[n - 1].match(/^\s*/)[0].length;
  let culprit = 'inside-mixin?';
  for (let i = n - 2; i >= 0; i--) {
    const t = lines[i]; if (!t.trim()) continue;
    const li = t.match(/^\s*/)[0].length;
    if (li < ind) break;
    if (li > ind) continue;
    if (t.trim() === '}') { culprit = 'child-rule'; break; }
    const m = t.trim().match(/^@include\s+([\w.-]+)[^{]*;/);
    if (m) { culprit = m[1]; break; }
  }
  (out[culprit] ||= []).push(s);
}
for (const [k, v] of Object.entries(out)) console.log(k, v.length, v.join(' '));
```

`inside-mixin?` = the warning points into the mixin itself (fix its internals);
`child-rule` = move the declarations above the child (always exact).

## 5. reorder.mjs — move includes past their trailing declaration run

Moves each target include past the contiguous same-indent run of **plain
declarations** that follows it (blank lines and `//` comments are carried
along; the run stops at any `@include`, nested opener or indent change — an
`@include` inside the run could itself emit nested rules). Exact for includes
that emit only nested rules (`col`); for the others it is exact only when the
run does not touch the mixin's properties — run `strict.mjs` and convert the
flagged sites with `hook.mjs`.

```js
import { readFileSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

const root = process.argv[2]; // e.g. web/themes/custom/frontend/src/sass
const files = execSync(`find ${root} -name '*.scss'`).toString().trim().split('\n');
const isDecl = (t) => /^[-a-zA-Z]+\s*:[^{]*;\s*(\/\/.*)?$/.test(t);
const isTarget = (t) =>
  /^@include\s+mixins\.(set-font-size|wrapper|wrapper-custom|fit-crop-element|col)\b[^{]*;\s*(\/\/.*)?$/.test(t);

let total = 0;
for (const file of files) {
  const lines = readFileSync(file, 'utf8').split('\n');
  const out = []; let moved = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i], t = line.trim();
    if (!isTarget(t)) { out.push(line); continue; }
    const indent = line.match(/^\s*/)[0];
    let j = i + 1; const run = [];
    while (j < lines.length) {
      const l = lines[j];
      if (l.trim() === '' || /^\s*\/\//.test(l)) { run.push(l); j++; continue; }
      if (l.match(/^\s*/)[0] !== indent || !isDecl(l.trim())) break;
      run.push(l); j++;
    }
    while (run.length && (run.at(-1).trim() === '' || /^\s*\/\//.test(run.at(-1)))) { run.pop(); j--; }
    if (!run.some((l) => isDecl(l.trim()))) { out.push(line); continue; }
    out.push(...run, line); i = j - 1; moved++;
  }
  if (moved) { writeFileSync(file, out.join('\n')); total += moved; console.log(`${moved}\t${file.replace(root + '/', '')}`); }
}
console.log(`Total reordered: ${total}`);
```

## 6. hook.mjs — convert a flagged site to the `@content` slot

Prerequisite: the mixin has `@content;` between its declarations and its
nested rules (see SKILL.md Step 3). For each `file:line:N` (line = the include,
N = how many declarations directly above it were moved there by `reorder.mjs`
— read the original order with `git show HEAD:<file>`), wraps those N
declarations into the include's block. Processes each file bottom-up so line
numbers stay valid.

```js
import { readFileSync, writeFileSync } from 'node:fs';

const root = 'web/themes/custom/frontend/src/sass/';
const specs = process.argv.slice(2).map((s) => s.split(':')).map(([f, l, n]) => ({ f, l: +l, n: +n }));
const byFile = {};
for (const s of specs) (byFile[s.f] ||= []).push(s);
for (const [f, list] of Object.entries(byFile)) {
  const lines = readFileSync(root + f, 'utf8').split('\n');
  for (const { l, n } of list.sort((a, b) => b.l - a.l)) {
    const inc = lines[l - 1], indent = inc.match(/^\s*/)[0];
    const run = lines.slice(l - 1 - n, l - 1);
    for (const r of run)
      if (r.match(/^\s*/)[0] !== indent || !/^[-a-zA-Z]+\s*:[^{]*;$/.test(r.trim()))
        throw new Error(`${f}:${l} bad run line: ${r}`);
    lines.splice(l - 1 - n, n + 1, inc.replace(/;\s*$/, ' {'), ...run.map((r) => '  ' + r), indent + '}');
    console.log(`${f}:${l} wrapped ${n}`);
  }
  writeFileSync(root + f, lines.join('\n'));
}
```

```bash
node .cssdiff/hook.mjs nodes/_node.scss:16:4 layout/_footer.scss:72:9 …
```

## 7. Procedure

```bash
# a) GOLDEN — before running any migrator.
mkdir -p .cssdiff   # + the scripts above
docker compose … exec -T node node .cssdiff/compile.mjs <sass-root> .cssdiff/golden
#    Forgot? Back up the work, `git checkout -- <sass-root>`, compile, restore.

# b) Migrators + Step 2 fixes, then compile and diff every entrypoint both ways.
docker compose … exec -T node node .cssdiff/compile.mjs <sass-root> .cssdiff/cur
cd .cssdiff && for f in $(cd golden && find . -name '*.css' | sort); do
  s=$(node cssdiff.mjs golden/$f cur/$f | grep -c SEMANTIC)
  m=$(node cssdiff.mjs golden/$f cur/$f | grep -c MISSING)
  x=$(node cssdiff.mjs cur/$f golden/$f | grep -c MISSING)
  [ "$s$m$x" != "000" ] && echo "$f semantic=$s missing=$m added=$x"
done; cd ..

# c) Once only intended differences remain: freeze stage1.
cp -r .cssdiff/cur .cssdiff/stage1

# d) mixed-decls: culprits → mixin internals → reorder → compile → strict vs stage1
node .cssdiff/culprits.mjs .cssdiff/cur.warnings.tsv <sass-root>/
node .cssdiff/reorder.mjs <sass-root>
docker compose … exec -T node node .cssdiff/compile.mjs <sass-root> .cssdiff/cur
for f in $(cd .cssdiff/stage1 && find . -name '*.css'); do
  r=$(node .cssdiff/strict.mjs .cssdiff/stage1/$f .cssdiff/cur/$f)
  echo "$r" | grep -q 'issues=0$' || { echo "== $f"; echo "$r"; }
done
#    ORDER FLIP → add @content to the mixin, hook.mjs the site, recompile, re-check.

# e) Final: strict vs golden with normalized selectors, cssdiff vs golden, warning count 0.
node .cssdiff/strict.mjs --normalize .cssdiff/golden/<f> .cssdiff/cur/<f>
rm -rf .cssdiff                                       # never commit it
```

## 8. Reading the output

- **`SEMANTIC DIFF … prop: "X" -> "Y"`** — a real regression. Recurring causes:
  - a whole component block differs (`padding`, `border-radius`, `font-*`) →
    a mixin defined twice (SKILL.md 2e);
  - `display: flex -> block`, `width: 100% -> auto`, `max-width: 118px -> none`
    → a reorder past `wrapper`/`fit-crop-element` hit a collision → `@content`
    slot, **not** `& {}` (it lands after the mixin's `@media` and beats it);
  - an extender lost declarations (`font-family: undefined`) in one entrypoint
    and gained them in another → a `@use` added for an `@extend` leaked a
    module or the extend no longer reaches it (2b, 2c).
- **`MISSING RULE`** — check what the missing selectors look like:
  - `<context> <extender>` mirroring an existing `<context> .target` override
    (e.g. `.node--reference .wysiwyg h4` next to `.node--reference .title4`)
    → **regression**: the element loses a contextual override. `@use` the
    context modules from the extending file (or a CSS-free partial loaded last).
  - pure cross-context combinations whose declarations a shorter selector
    already applies → benign redundancy. Confirm with
    `grep -Fc '<short selector>' .cssdiff/cur/<f>`.
- **`MISSING RULE` in the reverse run (added rules)** — a module emitted where
  it was not before (leak), or `load-css` re-emitting a dependency
  (`.ck .ck-content :root` — dead, never matches; accept and document).
- **`ORDER FLIP`** — interacting declarations swapped; convert the site.
- **`RULE ORDER` / `RULE COUNT`** in `strict.mjs` — a rule moved or appeared:
  emission order changed (a `@use` loaded a module earlier) or a `& {}` wrap
  split a rule.
- **All zero** (apart from documented, user-approved differences) → ship.

## Gotchas learned the hard way

- The naive brace parser mis-attributes declarations that sit right after an
  inline `/* comment */`. **Strip comments first** — `compile.mjs` does it.
- zsh: an unquoted `$VAR` holding a command or a file list is one word
  (`ENAMETOOLONG`, `no such file or directory: docker compose …`); use arrays
  (`E=(${(f)"$(find …)"})`) or inline the command. `echo ===` fails too
  (`== not found`, `=cmd` expansion) — quote it.
- `sed -n A,Bp` on a file without a trailing newline: `wc -l` is one short, so
  a range computed from it drops the last line (e.g. a closing brace when
  extracting a block into a partial). Check the tail with `od -c`.
- `make npm-build` may also compile an admin theme and rewrite its committed
  `.map` files — revert them before committing.
- `git status --short` counts can drift by ±1 vs `git diff --name-only` when a
  working-tree edit happens to reproduce the staged content byte-for-byte.
- A command-rewriting shell proxy may summarize/mangle `sass`/`grep` output — if
  a redirect file looks truncated, read it with the file tool or bypass the proxy.
