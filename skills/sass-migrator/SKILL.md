---
name: sass-migrator
description: >
  Migrate a Dockerized, Makefile-driven Drupal theme's SCSS off deprecated Dart
  Sass syntax with sass-migrator, and clear the deprecation warnings at the
  source. Use when the user mentions sass-migrator, migrating @import to
  @use/@forward, the Sass module system, or Dart Sass deprecation warnings
  (mixed-decls, slash-div / division, strict-unary, global-builtin, legacy
  color functions). Covers the migrator run order, the fixes the migrator can
  NOT do (cross-file @extend and its contextual cross-products, nested
  @import, mixins defined twice, CSS max()/min() shims, mixed-decls source
  fixes via an @content slot), and a compiled-CSS non-regression harness with
  an order-aware check that proves the output is unchanged. IMPORTANT: all
  builds MUST go through Makefile/npm targets inside the node container, never
  on the host.
---

# SCSS modernization with sass-migrator (Dockerized Drupal theme)

Migrate a Drupal theme's SCSS off the deprecated bits of Dart
Sass (`@import`, global built-ins, `/` division, ambiguous unary minus,
`mixed-decls`) and clear every warning **without changing the computed CSS**.
Reference runs: `akena.com` (theme `frontend`, 120 `.scss` files, ~500 rules)
and `ginger-sofreco` (theme `frontend`, 78 `.scss` files, 35 entrypoints,
758 warnings → 0).

This skill pairs with `gulp-to-vite` — do the Gulp→Vite migration first (it gives
you `make npm-build`), then this to modernize the SCSS the new build compiles.

## Golden rule: everything goes through the container

Dockerized + Makefile-driven. Compile inside the `node` service, never on the
host — the host `sass` CLI often pulls a broken `@parcel/watcher` on Apple
Silicon (`No prebuild ... darwin-arm64`), which is **not** a code bug.

| Need | Command |
|---|---|
| Production build (warning count) | `make npm-build` |
| Every entrypoint, ALL warnings tallied by type | `compile.mjs` from `references/verification-harness.md`, run in the container |
| One entrypoint, ALL warnings (verbose) | `docker compose … exec -T node npx sass --verbose --no-source-map <in>.scss <out>.css` |
| Run a migrator | `npx sass-migrator <migrator> --migrate-deps <entries…>` (host is fine — it only rewrites source) |

`make npm-build` (and the Sass JS API) only print the **first 5** warnings per
deprecation then `WARNING: N repetitive deprecation warnings omitted`. Count
with `verbose: true` / `--verbose`: on ginger-sofreco the truncated count said
`mixed-decls: 35`, the real one was 181.

Build entrypoints are usually every non-partial file the build globs (e.g.
`src/sass/**/*.scss` minus `_*.scss`), not just `style.scss` — read the
`vite.config` / sass plugin to get the real list. Paragraph/node folders often
compile one CSS file each.

**zsh**: `E=$(find …)` is not word-split, so the migrator receives one huge
path (`ENAMETOOLONG: name too long, scandir`). Use an array:
```zsh
E=(${(f)"$(find . -name '*.scss' -not -name '_*' | sort)"}); npx sass-migrator module --migrate-deps $E
```

## Order of operations

0. **Golden** — compile every entrypoint from the untouched source *before*
   running anything (Step 4). Keep it for the whole run.
1. **module** — `@import` → `@use`/`@forward` + namespacing (also fixes
   `global-builtin`, and converts `darken()`/`lighten()` to `color.adjust()`).
2. **division** — `/` → `math.div()` / multiplication.
3. **strict-unary** — disambiguate `$a -$b`.
4. **mixed-decls** — no migrator exists; fix at the source (see below).

Always `--migrate-deps` and always pass **every entrypoint at once** so shared
partials migrate consistently.

### Full migrator catalog

`sass-migrator help` lists all of them. Run `--dry-run` for each on the target;
apply only the ones that report changes **and** whose deprecation the
installed Sass actually emits:

| Migrator | Fixes | When to run |
|---|---|---|
| `module` | `@import` → `@use`/`@forward` + namespacing | **Core.** Always first. |
| `division` | `/` → `math.div()` / multiplication | **Core.** After module. |
| `strict-unary` | ambiguous `$a -$b` → `$a - $b` | **Core.** After division. |
| `calc-interpolation` | removes `#{…}` interpolation inside `calc()`/`clamp()`/`min()`/`max()` | If the theme builds calc strings with interpolation. |
| `color` | legacy color functions → `color.adjust`/`color.channel` | If `color-functions` remains after `module` (module usually already converted them). |
| `if-function` | legacy `if()` → the new CSS-style `if(sass(…): …; else: …)` | **Only if the installed Sass emits an `if-function` deprecation.** The new syntax needs a recent Dart Sass; on an older pin (1.80.x) it is unsupported — revert its edits. |
| `namespace` | rename `@use` namespaces (`--rename`) | Cosmetic, opt-in. Not a deprecation fix. |

Dry-run sweep to see which actually apply:
```bash
for m in module division strict-unary calc-interpolation color if-function; do
  echo "== $m =="; npx sass-migrator $m --migrate-deps --dry-run $E 2>&1 | tail -n +2 | head
done
npx sass --version   # in the container — decides whether if-function is applicable
```
`division`/`strict-unary` may legitimately report "Nothing to migrate!" —
re-run them after `module` to be sure.

## Step 0 — Dry-run + scope

```bash
npx sass-migrator module --migrate-deps --dry-run $E   # lists files it will touch, exit 0 = parses OK
```

- A partial that only **defines** members (a mixin/variable file) and references
  nothing else is left **untouched** — that is correct, not a miss.
- If the user says "ignore file X, it errors" — dry-run first anyway. The module
  migrator usually parses files the user thinks are broken; only genuinely
  unparseable files fail, and then you exclude them by temporarily commenting
  their `@import` line, migrating, then porting that one line by hand.
- **Pre-scan for duplicated members** — under `@import` the last definition of
  a mixin/function wins *globally and at call time*; under modules every call
  resolves lexically to its own module's copy. Find them before migrating:
  ```bash
  grep -rhoE '^\s*@(mixin|function) [a-zA-Z0-9_-]+' --include='*.scss' . | awk '{print $2}' | sort | uniq -d
  ```
  See 2e.

## Step 1 — Run the migrators

```bash
npx sass-migrator module        --migrate-deps $E
npx sass-migrator division      --migrate-deps $E
npx sass-migrator strict-unary  --migrate-deps $E
```

Note: piping migrator output through a filter can swallow it and leave the files
migrated with a later "Nothing to migrate!" — check `git diff`, not stdout.

## Step 2 — Fix what the migrator gets WRONG or SKIPS

Compile every entrypoint; fix errors first, then diff against the golden
(Step 4) **before** touching mixed-decls, so each regression is attributable.

### 2a. `math.max()` / `math.min()` on CSS functions — build ERROR

The module migrator namespaces every `max(`/`min(` to `math.max`/`math.min`,
which **breaks** CSS usages like `max(44px, env(safe-area-inset-right))`
(`env() is not a number`). The migrator also keeps/emits shim functions:

```scss
@function max($numbers...) { @return m#{a}x(#{$numbers}) }   // literal CSS max()
@function min($numbers...) { @return m#{i}n(#{$numbers}) }
```

Fix: revert the `math.max(`/`math.min(` call sites back to plain `max(`/`min(`
(they then resolve to the shims → literal CSS), and drop the now-unused
`@use "sass:math"`. Keep the shims — they preserve
`@supports (padding: max(0px))` (a plain `max(0px)` would fold to `0px`).

Under `@import` that shim also overrode `max()` in **every later file**, so the
migrator binds those calls to the shim's module: `fancybox.max(…)` plus a
`@use "…/fancybox"` in an unrelated file. When the arguments are CSS-valid
(`max(300px, calc(25% - 24px))`), replace with plain `max(` and drop the
`@use`: the only output change is Sass flattening the nested calc
(`max(300px, 25% - 24px)`), which is equivalent.

### 2b. Cross-file `@extend .class` — build ERROR ("target selector not found")

Under `@import` everything shared one global scope, so `@extend .title1` found
`.title1` anywhere. Under modules, an `@extend` only reaches selectors in the
**current module and the modules it (transitively) `@use`s/`@forward`s**. The
migrator does NOT add these.

```bash
grep -rn '@extend \.' --include='*.scss' . | grep -v '//'
grep -rnE '^\s{0,2}\.<class>\b' --include='*.scss' .   # canonical definition, per class
```

Add `@use "<path-to-defining-partial>";` to the extending file — but check two
things, because `@use` both **emits** the module's CSS on first load and
**bounds** what the extend reaches:

1. **Emission order / leaks.** If the extending file is loaded *before* the
   defining module in some entrypoint, the `@use` moves that module's CSS up;
   if the extending file is shared with another entrypoint (e.g. a CKEditor
   stylesheet), the defining module's CSS now leaks into it. Both show up in
   the diff.
2. **Contextual cross-products.** The global extend also copied every
   *contextual* override of the target onto the extender:
   `.node--reference .title4 { color; margin: 0 }` produced
   `.node--reference .wysiwyg h4 { … }`. With only the canonical module
   `@use`d, those rules disappear (`MISSING RULE` in the diff) and the
   element loses the override — a **real regression**, not redundancy.
   Fix: the extending file must also `@use` every module holding a contextual
   override of the target (the missing selectors name them).

When the extending file sits early in the load order, those `@use`s would
reorder the CSS. Move its extends into a **CSS-free partial** that `@use`s the
targets and contexts, and `@use` it **last** in the entrypoint (every module
already loaded → nothing re-emitted; extends rewrite the targets in place):

```scss
// components/_wysiwyg-titles.scss — @use'd last from styles.scss only
@use "titles";
@use "../nodes/reference";
@use "../pages/sitemap";
.wysiwyg {
  h1 { @extend .title1; }
  h4 { @extend .title4; }
}
```

A file that is already loaded last (e.g. `views/_jobs`) can take the extra
`@use`s directly. Neither constraint is visible in the code — explain it in
the commit/MR.

### 2c. Nested `@import` inside a rule

```scss
.ck .ck-content { @import 'components/titles'; h1 { @extend .title1; } }
```
The migrator turns it into `@include meta.load-css('components/titles')`,
which nests the CSS correctly — but **extends never reach `load-css`'d CSS**,
so `@extend .title1` errors. Fix: move the whole body of that rule into a
partial that `@use`s the targets, and `load-css` that partial:

```scss
// ckeditor.scss
.ck { .ck-content { font-family: …; @include meta.load-css('components/ckeditor-content'); } }
// components/_ckeditor-content.scss
@use "titles"; @use "buttons";
h1 { @extend .title1; }      // → .ck .ck-content .title1, .ck .ck-content h1
```

`load-css` re-emits the CSS of the partial's dependencies even when already
loaded, so a variables module with `:root { … }` yields a dead
`.ck .ck-content :root { … }` (can never match). Accept and document it.

Also note what the *old* build really did with nested imports: in the golden,
extends from top-level files did **not** reach the nested copy, and nested
mixin definitions stayed local. Reproduce the golden, not the intent.

### 2d. Default arguments that shadow a global

```scss
@mixin col($col, $spacing: $spacing) { … }   // migrator leaves it un-namespaced
```
`Undefined variable` at the first call without the argument. Fix:
`$spacing: variables.$spacing`.

### 2e. Mixin/function defined twice

Found by the Step 0 pre-scan. Example: `make-btn` in `_mixins` and again in
`_buttons`, while `make-btn-primary` (in `_mixins`) calls `make-btn`. Under
`@import`, every entrypoint that loaded `_buttons` first ran the `_buttons`
copy; under modules `_mixins` calls its own stale copy. Symptom: whole
`SEMANTIC DIFF` blocks on one component.

Fix: move the callers next to the copy that actually ran, delete the dead copy.
Watch for entrypoints where the old build resolved to the *other* copy (nested
`@import` keeps definitions local): one module cannot reproduce both. That is
a product decision — show the user the concrete value differences and ask
(aligning on the site's copy is the usual answer).

## Step 3 — mixed-decls (no migrator; fix at the source)

### Root cause
A **declaration after a nested rule** in the same style rule — almost always a
mixin that emits declarations *and* a nested rule (`@media` via
`breakpoint()`/`rfs()`, `@supports`, `&:before`) followed in the caller by
more declarations. Classify the warning sites by the include that precedes
them (`culprits.mjs` in the harness) — typical: `set-font-size`, `wrapper`,
`col`, `fit-crop-element`.

### What is exact
Current Dart Sass **hoists** every declaration of a block above its nested
rules. A fix is output-identical iff each block's declarations keep their
relative order (for properties that interact). So:

| Situation | Fix | Exact? |
|---|---|---|
| Include emits **only** nested rules (`col()` → `@media`) | move it after the declaration run | always |
| Declarations after a **child selector** | move them above the child | always |
| Mixin's own trailing decls (`set-font-size`: `line-height` after `rfs()`) | move them above the nested-emitting include inside the mixin | if no interaction (`font-size` vs `line-height`: none) |
| Include emits decls + nested rules, caller decls don't touch its properties | move the include after the run | yes — verify |
| Same, but the caller **overrides** one of its properties (`display: flex` after `wrapper()`'s `display: block`; `padding: 20px 0` vs `padding-left`) | **`@content` slot** (below) | by construction |

### The `@content` slot
Give the mixin a `@content;` between its declarations and its nested rules,
and pass the caller's trailing declarations in the block:

```scss
@mixin wrapper($w: 'min') {
  display: block;
  padding-left: $spacing-sm;
  @content;
  @include breakpoint(tablet) { padding-left: $spacing-xl; }
}
.page-header {
  @include mixins.wrapper() {
    display: flex;
    padding: 20px 0;
  }
}
```

Existing callers without a block are unaffected. For mixins with `@if`
branches, put `@content` at the end of each branch's declarations.

### Do NOT use `& {}` for collisions
`& { padding: 20px 0; }` is emitted **after** the mixin's `@media`, so it now
beats the breakpoint's `padding-left` — a regression at that breakpoint. A
`& {}` wrap is only safe when no nested rule of the block sets an interacting
property; prefer the `@content` slot.

### Scale
Automate the safe reorder (`reorder.mjs`: runs restricted to plain
declarations), run the order-aware check, then convert only the flagged sites
to the `@content` form (`hook.mjs`). Never trust the reorder blind.

## Step 4 — Prove zero regression (do NOT skip)

Scripts in `references/verification-harness.md`:

1. **Golden** = compile every entrypoint from the pre-migration source.
2. **Semantic diff** (`cssdiff.mjs`) golden vs current, both directions
   (`MISSING RULE` in reverse = rules *added*, e.g. leaked modules).
3. **stage1 snapshot** once Step 2 is clean, then **order-aware check**
   (`strict.mjs`) stage1 vs final after Step 3, and golden vs final with
   selector lists normalized.

Why both: `cssdiff.mjs` merges last-wins *per property name*, so it cannot see
`padding: 20px 0` swapping places with `padding-left: 16px`.
`strict.mjs` requires the same rule sequence and the same declarations, and
flags any reordered pair of **interacting** properties (same property,
shorthand/longhand, `font`/`line-height`, `inset`/sides, `gap`/`row-gap`).

Interpretation:
- `SEMANTIC DIFF` → regression: duplicated member (2e), lost contextual
  extend (2b), or a mixed-decls collision.
- `MISSING RULE` → benign **only** if the selector is a pure cross-context
  combination whose declarations are already applied by a shorter selector.
  If it is `<context> <extender>` mirroring a `<context> .target` override,
  it is a regression (2b).
- `ORDER FLIP` → convert that site to the `@content` slot.
- Added rules in an entrypoint → a `@use` leaked a module (2b) or `load-css`
  re-emitted a dependency (2c).

Then confirm the warning count:
```bash
make npm-build 2>&1 | grep -E '^\s+web/themes/custom/' | sed -E 's#(web/themes/custom/[a-z]+)/.*#\1#' | sort | uniq -c
```
Warnings left under another theme are out of scope (Step 5).

## Step 5 — Out of scope

- **Unused/other entrypoints** (e.g. a `backend` admin theme still on `@import`,
  or an entry the user says is unused): don't migrate. If the user disables it in
  `vite.config`, revert any stray edits you made there so the diff stays scoped.
- A build that also compiles the admin theme rewrites its committed `.map`
  files: `git checkout --` them before committing.
- `@use 'include'` lines left in paragraph files may no longer provide members
  (the migrator adds direct `@use`s) but still emit the `:root` block each
  CSS had — keep them for output parity.

## Step 6 — Git workflow

Ask the user which **target branch** the MR should go into (it often stacks on
in-flight work such as the `gulp-to-vite` or a global-refactor branch rather than
`develop`), then hand the whole branch/commit/push/MR flow to the
**`merge-request`** skill. The commit/MR must state the constraints the code
cannot (no SCSS comments): which partials must be loaded last, which
entrypoint deliberately differs, any accepted dead rule.

## Namespacing note (for the human)

`@use "…/mixins";` loads a module under a namespace (default = filename), so
members are only reachable prefixed: `mixins.set-font-size(…)`,
`variables.$color`. That is why the migrator rewrites every call — bare
`set-font-size(…)` does not compile under `@use`. The migrator deliberately keeps
explicit namespaces (not `as *`) — that is the recommended, collision-proof style.
