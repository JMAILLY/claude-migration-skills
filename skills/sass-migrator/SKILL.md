---
name: sass-migrator
description: >
  Migrate a Dockerized, Makefile-driven Drupal theme's SCSS off deprecated Dart
  Sass syntax with sass-migrator, and clear the deprecation warnings at the
  source. Use when the user mentions sass-migrator, migrating @import to
  @use/@forward, the Sass module system, or Dart Sass deprecation warnings
  (mixed-decls, slash-div / division, strict-unary, legacy color functions).
  Covers the migrator run order, the fixes the migrator can NOT do (cross-file
  @extend, CSS max()/min() shims, mixed-decls source fixes), and a compiled-CSS
  non-regression harness that proves the output is unchanged. IMPORTANT: all
  builds MUST go through Makefile/npm targets inside the node container, never
  on the host.
---

# SCSS modernization with sass-migrator (Dockerized Drupal theme)

Migrate a Drupal theme's SCSS off the deprecated bits of Dart
Sass (`@import`, `/` division, ambiguous unary minus, `mixed-decls`) and clear
every warning **without changing a single byte of the computed CSS**. Reference
run: `akena.com` (theme `frontend`, 120 `.scss` files, ~500 rules).

This skill pairs with `gulp-to-vite` — do the Gulp→Vite migration first (it gives
you `make npm-build`), then this to modernize the SCSS the new build compiles.

## Golden rule: everything goes through the container

Dockerized + Makefile-driven. Compile inside the `node` service, never on the
host — the host `sass` CLI often pulls a broken `@parcel/watcher` on Apple
Silicon (`No prebuild ... darwin-arm64`), which is **not** a code bug.

| Need | Command |
|---|---|
| Production build (warning count) | `make npm-build` |
| One entrypoint, ALL warnings (verbose) | `docker compose … exec -T node npx sass --verbose --no-source-map <in>.scss <out>.css` |
| Run a migrator | `npx sass-migrator <migrator> --migrate-deps <entry>.scss …` (host is fine — it only rewrites source) |

`make npm-build` only prints the **first 5** warnings per deprecation then
`WARNING: N repetitive deprecation warnings omitted`. To see the full list use a
verbose `npx sass` compile in the container.

## Order of operations

1. **module** — `@import` → `@use`/`@forward` + namespacing.
2. **division** — `/` → `math.div()` / multiplication.
3. **strict-unary** — disambiguate `$a -$b`.
4. **mixed-decls** — no migrator exists; fix at the source (see below).

Always `--migrate-deps` and always pass **every entrypoint at once** (e.g.
`style.scss ckeditor.scss mail.scss`) so shared partials migrate consistently.

### Full migrator catalog

`sass-migrator help` lists all of them. Run `--dry-run` for each on the target;
apply only the ones that report changes. The three above are the usual core; the
rest are situational but worth a dry-run pass so nothing is missed:

| Migrator | Fixes | When to run |
|---|---|---|
| `module` | `@import` → `@use`/`@forward` + namespacing | **Core.** Always first. |
| `division` | `/` → `math.div()` / multiplication | **Core.** After module. |
| `strict-unary` | ambiguous `$a -$b` → `$a - $b` | **Core.** After division. |
| `calc-interpolation` | removes `#{…}` interpolation inside `calc()`/`clamp()`/`min()`/`max()` | If the theme builds calc strings with interpolation (Dart Sass now parses calc natively). |
| `color` | legacy color functions (`darken()`, `lighten()`, `red()`…) → `color.adjust`/`color.channel` | If a `color-functions` deprecation shows up (common in older themes / admin themes). |
| `if-function` | legacy `if()` → the new CSS-style `if()` | Rare; only if the code uses the old `if()` function form. |
| `namespace` | rename `@use` namespaces (`--rename`) | Cosmetic — only if you want shorter/renamed namespaces after `module` (e.g. `mixins` → `mx`). Not a deprecation fix. |

Dry-run sweep to see which actually apply:
```bash
for m in module division strict-unary calc-interpolation color if-function; do
  echo "== $m =="; npx sass-migrator $m --migrate-deps --dry-run <entries…> 2>&1 | tail -n +2 | head
done
```
`namespace` is intentionally omitted from the sweep — it's opt-in and needs
`--rename`, it won't self-detect anything.

## Step 0 — Dry-run + scope

```bash
npx sass-migrator module --migrate-deps --dry-run <entries…>   # lists files it will touch, exit 0 = parses OK
```

- A partial that only **defines** members (a mixin/variable file) and references
  nothing else is left **untouched** — that is correct, not a miss.
- If the user says "ignore file X, it errors" — dry-run first anyway. The module
  migrator usually parses files the user thinks are broken; only genuinely
  unparseable files fail, and then you exclude them by temporarily commenting
  their `@import` line, migrating, then porting that one line by hand.

## Step 1 — Run the three migrators

```bash
npx sass-migrator module        --migrate-deps <entries…>
npx sass-migrator division      --migrate-deps <entries…>
npx sass-migrator strict-unary  --migrate-deps <entries…>
```

Note: piping migrator output through a filter can swallow it and leave the files
migrated with a later "Nothing to migrate!" — check `git diff`, not stdout.

## Step 2 — Fix what the migrator gets WRONG or SKIPS

The build will still fail/warn after Step 1. These are the recurring ones:

### 2a. `math.max()` / `math.min()` on CSS functions — build ERROR

The module migrator namespaces every `max(`/`min(` to `math.max`/`math.min`,
which **breaks** CSS usages like `max(44px, env(safe-area-inset-right))`
(`env() is not a number`). The migrator also **emits shim functions** at the top
of the file:

```scss
@function max($numbers...) { @return m#{a}x(#{$numbers}) }   // literal CSS max()
@function min($numbers...) { @return m#{i}n(#{$numbers}) }
```

Fix: revert the `math.max(`/`math.min(` call sites back to plain `max(`/`min(`
(they then resolve to the shims → literal CSS), and drop the now-unused
`@use "sass:math"` if nothing else needs it. Keep the shims — they preserve
`@supports (padding: max(0px))` (a plain `max(0px)` would fold to `0px`).

### 2b. Cross-file `@extend .class` — build ERROR ("target selector not found")

Under `@import` everything shared one global scope, so `@extend .title1` found
`.title1` anywhere. Under modules, an `@extend` only sees selectors in the
**current file and the modules it `@use`s/`@forward`s**. The migrator does NOT
add these (it can't map a bare class to a module).

Fix: in each file that `@extend`s a class defined elsewhere, add a `@use` of the
defining module. The namespace is irrelevant for `@extend` (it targets a plain
selector), you just need the module loaded:

```bash
# find every active cross-file @extend, then locate each target's canonical def:
grep -rn '@extend \.' --include='*.scss' . | grep -v '//'
grep -rnE '^\s{0,2}\.<class>\b' --include='*.scss' .   # per class
```

Add `@use "<path-to-defining-partial>";` to the extending file. Watch for
circular `@use` (build tells you). `@extend` reaching a class that lives in the
same entrypoint chain still needs the *file* loaded by the *extending* file.

## Step 3 — mixed-decls (no migrator; fix at the source)

### Root cause
A **declaration after a nested rule** in the same style rule. In these themes it
is almost always a mixin that emits a nested rule placed *mid-declaration-list*:
- `set-font-size()` → `rfs()` emits a `@media`
- `fit-crop-element()` → emits an `@supports`
- any `@include breakpoint(...) { … }` block

Every plain declaration that follows such an include (in the caller) warns.

### Two safe fixes — pick per collision
1. **Reorder** the offending `@include` to the **end** of its bare-declaration
   run (before nested children). Output-identical *because current Dart Sass
   hoists declarations above nested rules* — **but only when the include emits
   no property the caller re-declares afterward**. `fit-crop-element` sets
   `max-width: none` / `width` / `height`; a caller `max-width: 118px` after it
   would flip to `none` if you move the include. Reordering is safe for
   `set-font-size` in practice, dangerous for `fit-crop-element`.
2. **`& {}` wrap** the trailing declarations (order-preserving, cascade-safe):
   ```scss
   img { @include mixins.fit-crop-element(); & { max-width: 118px; } }
   ```
   Use wherever a reorder would change a last-wins collision, and to fix
   declarations that trail a **child selector** (not an include).

Also fix mixin **internals**: e.g. move `set-font-size`'s trailing
`line-height`/`letter-spacing` *above* its `@include rfs()` so the mixin itself
is clean. Wrap the leading decls of `make-btn-with-bg-*` mixins in `& {}` so they
survive being `@include`d after a `@media`.

### Scale
There are typically **100+** sites. Automate the reorder (a line-based script
that moves `@include set-font-size/fit-crop-element` past the following
same-indent declaration run) — see `references/verification-harness.md`, which
ships the reorder + verification scripts. **Never trust the reorder blind** —
verify with Step 4.

## Step 4 — Prove zero regression (do NOT skip)

Reordering can silently flip a cascade collision. Prove the computed CSS is
unchanged, per selector:

1. **Golden** = compile the pre-migration source (the index/`git show :` version,
   still on `@import`) in the container.
2. **Final** = compile your migrated source.
3. Compare **computed style per individual selector**: strip comments, parse
   each rule, expand comma-groups into individual selectors, merge same-context
   blocks last-wins, ignore selector-list *order*. **Zero value differences** =
   safe. The full parser/differ is in `references/verification-harness.md`.

Interpretation:
- A `SEMANTIC DIFF` on a property value = a real regression → fix (usually a
  `fit-crop`/collision case → switch that site to `& {}`).
- `MISSING RULE` for long multi-context selectors = `@extend` cross-product
  **redundancy** that the module system dropped; benign as long as the short
  covering selector is still present with the same declarations (grep to
  confirm). This is expected when moving off `@import`.

Then confirm the warning counts are zero:
```bash
docker compose … exec -T node npx sass --verbose … | grep -c DEPRECATION   # per entrypoint → 0
```

## Step 5 — Out of scope

- **Unused/other entrypoints** (e.g. a `backend` admin theme still on `@import`,
  or an entry the user says is unused): don't migrate. If the user disables it in
  `vite.config`, revert any stray edits you made there so the diff stays scoped.
- Residual `@import` / `color-functions` deprecations outside the target theme
  are for a separate pass (the `color` migrator handles legacy color functions).

## Step 6 — Git workflow

Ask the user which **target branch** the MR should go into (it often stacks on
in-flight work such as the `gulp-to-vite` or a global-refactor branch rather than
`develop`), then hand the whole branch/commit/push/MR flow to the
**`merge-request`** skill.

## Namespacing note (for the human)

`@use "…/mixins";` loads a module under a namespace (default = filename), so
members are only reachable prefixed: `mixins.set-font-size(…)`,
`variables.$color`. That is why the migrator rewrites every call — bare
`set-font-size(…)` does not compile under `@use`. The migrator deliberately keeps
explicit namespaces (not `as *`) — that is the recommended, collision-proof style.