---
name: gulp-to-vite
description: >
  Migrate a Dockerized, Makefile-driven Drupal theme front build from Gulp to
  Vite. Use when the user mentions replacing Gulp with Vite, a "gulp to vite"
  migration, modernizing a Drupal theme build, dropping the gulp-* dependency
  tree, gulp-imagemin ARM/Alpine build pain, an `npm install` that fails on
  optipng-bin, or a Drupal theme whose SCSS/JS edits do not hot-reload. Covers the
  feasibility verdict, the plugin-to-disk (Arch B) approach that keeps
  *.libraries.yml untouched, ready-to-fork Vite plugins, the dev HMR wiring, the
  Drupal/Apache caching layers that must be disabled for HMR to work at all, and
  Docker/Makefile/CI changes. IMPORTANT: all build commands MUST go through
  Makefile/npm targets inside the node container, never run directly on the host.
---

# Gulp → Vite migration skill (Dockerized Drupal theme)

Migrate a Drupal theme front build from **Gulp** to **Vite**,
iso-functional and low-risk. Reference implementations: `sterimed` (Tailwind) and
`ginger-cebtp` (SASS + classic jQuery scripts — the case this skill is tuned for).

## Golden rule: everything goes through the container

The project is Dockerized + Makefile-driven. Run the build inside the `node`
service, never on the host — the host arch (esp. Apple Silicon/macOS) makes the
`imagemin-*` native binaries fail with `ENOEXEC`, which is **not** a code bug.

| Need | Command |
|---|---|
| Install deps | `make npm-install` (or `make npm c='install'`) |
| Dev server (watch + HMR) | `make npm-dev` |
| Production build | `make npm-build` |
| One-off verify build | `docker run --rm -v "$(pwd)":/var/www/html -w /var/www/html <project>-node:latest sh -c 'rm -rf node_modules && npm install && npm run build'` |

## Step 0 — Feasibility verdict (say this out loud first)

For a classic GM theme, **Vite's headline features (bundling, tree-shaking,
per-module HMR) buy almost nothing.** Check why before promising speed:

- Theme JS is usually **classic jQuery/`Drupal.behaviors` IIFEs** (no
  `import`/`export`). Gulp just terser-copies them 1:1. → grep the JS source; if
  there are zero `import`/`export`, do **not** bundle — copy files.
- Vendor libs (swiper, fancybox, owl, masonry…) are loaded **straight from
  `node_modules/` by `*.libraries.yml`**, never touched by Gulp. → keep that.
- CSS is SASS; Vite compiles SASS natively but so did gulp-sass. No win.
- HMR degrades to **full page reload** for non-module scripts — exactly what
  Gulp + BrowserSync already did. No regression, no gain.

**The real payoff is maintenance, not speed:** dropping the ~35-package `gulp-*`
tree (especially `gulp-imagemin`, whose Alpine/ARM native build often needs a
Dockerfile patch) and standardizing with the rest of the fleet. Frame the work
this way so expectations are correct.

### First check whether the Gulp build still installs at all

Before framing this as modernization, run a clean install in the container
(`rm -rf node_modules && npm install`). On some projects it **fails outright**:
`gulp-imagemin` → `optipng-bin` compiles fine with the Alpine toolchain, then its
post-install binary check fails, and **npm rolls back the whole install, leaving
`node_modules` with 0 entries**. Symptom: the theme's `css/` and `js/` are empty
and the site renders unstyled, while CI still passes (Debian/x86 images get a
working prebuilt binary).

When that is the case, say so plainly — the migration is not a nice-to-have, it
is **the fix for a broken local front build**, and the dependency blocking every
install is one the production build never even calls. Lead with that; it is a far
stronger justification than fleet uniformity.

It also means **there may be no runnable Gulp baseline to diff against**. Don't
stall trying to produce one: derive the expected output set from the deploy task
chain plus `*.libraries.yml` (Step 1) and verify against that instead.

## Step 1 — Investigate before touching anything

Verify each of these; they decide the approach and avoid nasty surprises:

1. **What Gulp actually builds** — read `gulpfile.js` + root `package.json`
   `paths`. **Scope the port to the `deploy` task chain, not to the functions the
   gulpfile defines.** A 400-line gulpfile commonly runs only 3 steps; everything
   else is dead weight that must NOT be ported. Print the chain
   (`const deploy = gulp.series(…)`) and port exactly that.

   Classify every other function before deciding, because "defined" ≠ "works":
   - **unwired** — never referenced by an exported task (favicon, tarteaucitron).
   - **wired but crashes** — e.g. a task globbing `paths.sources.sass_custom`
     when that key doesn't exist in `paths`, so `gulp.src(undefined)` throws.
   - **wired but unbuildable** — its SCSS `@import`s a path that no longer
     exists (a sibling theme restructured). This is usually **why** it was left
     out of `deploy`. Porting it turns a green build red.
   - **not in deploy, output committed** — images/sprites. The committed files
     are the source of truth; a Vite imagemin plugin would rewrite hundreds of
     tracked files for nothing. Drop it.

   Rule of thumb: if `deploy` doesn't call it and its output is committed or
   unreferenced, **leave it out and say so in the verdict**. Reproducing a broken
   task faithfully is not iso-functional, it is just broken.
2. **JS style** — `grep -rlE '^\s*(import|export)\s|require\(' <theme>/src/js`.
   Empty ⇒ classic scripts ⇒ copy, don't bundle.
3. **`*.libraries.yml`** — count entries. Per-paragraph CSS/JS mapped 1:1 (dozens
   of fixed paths) ⇒ rewriting to `dist/` is high-churn ⇒ prefer Arch B.

   Also **list every theme-relative path it declares and check each one is
   actually produced** by the old build. Gulp typically globs `**/*.js` only, so a
   declared sibling asset like `js/libs/tablesaw/tablesaw.css` is **never emitted
   and 404s in production today**. Same for `.info.yml`
   `ckeditor5-stylesheets`, which often points at a path from a previous theme
   layout. Ask whether to fix these in scope; they are one-line fixes (copy extra
   extensions / correct the path) and the migration is the natural moment. This
   list is also your verification target in Step 4.
4. **Icon font** — do NOT assume `gulp-iconfont` is vestigial; check whether it is
   in the **deploy chain**. When it is live, it has no Vite equivalent, and it is
   the single hardest part of the port. Three options, offer them explicitly:
   - **freeze as static (usually best)** — keep the committed `_fonticon.scss` and
     `icons-*.woff/woff2` and drop the task, plus an opt-in
     `npm run icons` script for the rare regeneration. Icons change rarely, and
     the old task minted a new timestamped font on **every** build, so dozens of
     `icons-<timestamp>.*` files are typically already committed.
   - **port it** — `svgicons2svgfont` + `svg2ttf` + `ttf2woff` + `ttf2woff2`, plus
     something to replace `gulp-consolidate` for the Twig→SCSS template (reuse the
     project's existing `twig` dep to keep output shape identical).
   - **keep Gulp only for it** — undercuts the payoff; last resort.

   Whichever is chosen, note that the generated `_fonticon.scss` is a **live SASS
   input** (`@use`d by `theme.scss`/`_mixins.scss`), not an output — never delete
   it. Also flag the ordering bug these gulpfiles usually have: `fonticon` runs
   *after* `compileSass` in the series, so a regenerated font only takes effect on
   the *next* build.
5. **Two npm projects** — the root `package.json` holds the build tooling, but
   `*.libraries.yml` paths like `node_modules/<pkg>/…` resolve **relative to the
   theme**, so the theme has its own `package.json` + `node_modules`. Confirm both
   installs happen; a Makefile `npm-install` that only covers the root leaves
   every vendor library 404.
6. **Hand-maintained outputs** — is `css/ckeditor.css` (or similar) committed but
   NOT generated from any SCSS source (`git ls-files <theme>/css`)? If so, Vite
   must never clobber it (`emptyOutDir:false`, write only real entries).
   Conversely, if `css/` and `js/` are fully `.gitignore`d and empty, there is
   nothing to protect — confirm before adding `emptyOutDir` gymnastics.
7. **Favicon** — if Gulp uses `gulp-real-favicon` (remote API) but the favicon
   markup in `html.html.twig` is **hardcoded** and `favicons.json` is unused at
   runtime, **drop favicon from the build**; the committed PNG/ico stay as
   static assets. Confirm the twig consumer before deleting.
8. **Fonts / tarteaucitron / other statics** — if not in any Gulp task and not
   `.gitignore`d, they're committed statics; leave them.
9. **`.gitignore`** — which outputs are ignored vs force-committed? Force-committed
   build artifacts (`sprites.svg`, admin `dist/theme.css`) will show as modified
   after any build; keep them **out of the migration commit** (revert to HEAD).
10. **Docker/Makefile/CI** — the `node` service env (`THEME_FOLDER`, `HOME_URL`,
    exposed port), existing `npm-*` Makefile targets (often pre-scaffolded), and
    the CI job that runs `gulp deploy` (its artifact paths must stay identical).
11. **How the project loads `.env`** — this decides how the dev gate reads
    `APP_ENV`, and getting it wrong makes the HMR client silently never attach
    (or, worse, attach in prod). `grep -n dotenv composer.json` and read
    `load.environment.php`:
    - **`vlucas/phpdotenv`** — `Dotenv::createImmutable(__DIR__)->safeLoad()`
      populates `$_ENV` and `$_SERVER` only; **`getenv()` returns `FALSE`**. Read
      `$_ENV`.
    - **`symfony/dotenv`** (what `drupal/dotenv` pulls in) —
      `(new Dotenv())->usePutenv(TRUE)->bootEnv(DRUPAL_ROOT . '/../.env')` also
      `putenv()`s, so `$_ENV`, `$_SERVER` and `getenv()` all agree. Read
      `getenv()` — it is the shortest and the only one that survives a missing
      `variables_order=E`.
    - **neither** — the value exists only because the compose `environment:` block
      passes it, which reaches PHP only with `clear_env = no` in PHP-FPM's
      `www.conf` (`$_ENV`/`$_SERVER` additionally need `E` in `variables_order`).
    A `base.settings.php` that guards on `$_ENV['APP_ENV']` tells you which source
    the project already trusts; align with it instead of inventing a fallback
    chain. Confirm empirically in the **web** context, not just the CLI:
    `docker compose exec -T --user www-data php php -r 'var_dump(getenv("APP_ENV"), $_ENV["APP_ENV"] ?? NULL, ini_get("variables_order"));'`
    then `curl -ksS https://<project>.dev.localhost/ | grep -c '@vite/client'`.
12. **Drupal-side caching** — `drush config:get system.performance`. If
    `css.preprocess`/`js.preprocess` are `true` or `cache.page.max_age` is
    non-zero, **HMR cannot work** no matter how correct the Vite side is. See the
    caching chain in Step 3.6; budget for it, it is the single most likely reason
    the user reports "it doesn't hot-reload".

## Step 2 — Choose the architecture

| | **Arch A — sterimed-faithful (`dist/`)** | **Arch B — plugin-to-disk (RECOMMENDED)** |
|---|---|---|
| CSS/JS | Rollup entrypoints → `dist/` | Plugins compile/copy → **legacy** `css/ js/ images/` |
| `*.libraries.yml` | rewrite ~all paths to `dist/…` | **untouched** |
| `.info.yml ckeditor_stylesheets`, Twig | rewrite | untouched |
| Drupal wiring | `hook_library_info_alter` + `hot-replacement` swap per asset | one dev-only `@vite/client` inject |
| HMR | true per-module (for modules) | full page reload (== old BrowserSync) |
| Churn / risk | high | low — invisible migration |

**For classic-script SASS themes, pick Arch B.** It keeps every library path,
info.yml and Twig reference untouched — the migration is invisible to Drupal.
Only pick Arch A if the goal is fleet-wide `dist/` uniformity and you accept the
churn.

## Step 3 — Implement Arch B

See **`references/arch-b-implementation.md`** for the complete, verified,
copy-pasteable code (package.json, vite.config.mjs, the 4 plugins, the Drupal
dev wiring, Docker/Makefile/CI edits). The shape:

1. **`package.json`** — drop every `gulp-*` + `browser-sync`/`pump`/`require-dir`;
   add `vite sass esbuild postcss postcss-pxtorem imagemin
   imagemin-{gifsicle,mozjpeg,optipng,svgo} cheerio fast-glob` (plus
   `@vitejs/plugin-basic-ssl` **only for TLS Option A**, see step 4). Set
   `"type": "module"`; scripts `dev: vite`, `build: vite build`. Delete `gulpfile.js`.
2. **`vite.config.mjs`** — dev server (`basicSsl()` for TLS Option A, or plain
   HTTP behind Traefik for Option B; the theme's exposed port, `usePolling`,
   `wss` HMR); a `live-reload-templates` plugin full-reloading on
   `.twig/.theme/.php/.inc/.yml`; and a **no-op virtual entry + `build.write:false`**
   so `vite build` fires the plugins without a real entrypoint (classic JS can't
   be a Rollup input).
3. **`plugins/`** (fork from sterimed, parametrized, output to LEGACY paths):
   - `vite-sass` — `style.scss` → `css/style.css`; `fast-glob` the per-paragraph
     SCSS (ignore `_*`) → `css/theme/…`; also admin `theme.scss` → `styles/dist`.
     Apply `postcss-pxtorem` **inside the plugin** (plugins bypass Vite's CSS
     pipeline, so `postcss.config` is not auto-applied).
   - `vite-copy-js` — recursive walk of `src/js`, esbuild-minify each file → `js/`,
     structure preserved.
   - `vite-imagemin` — `fast-glob` `src/images` (ignore `sprites/**`) → `images/`.
   - `vite-icon-sprite` — cheerio, one `<symbol id="<file>">` per SVG, strip
     `fill|stroke`, keep `viewBox` → `images/sprites.svg`.
   Every plugin runs its work in `buildStart` **and** `handleHotUpdate` (then
   `server.ws.send({type:'full-reload'})`) — that dual write is what lets Drupal
   serve fresh on-disk files in dev without any library swap.
4. **Dev HMR wiring (Arch B minimal)** — a `hot-replacement` library loading
   `@vite/client` (`type: external`, `attributes: {type: module}`), attached
   **only in local** via `THEME_page_attachments_alter()` gated on a strict
   `APP_ENV === 'local'`, read from the source Step 1.11 identified. The strict
   comparison is what makes it fail closed — absent (`FALSE`), empty and
   `prod`/`preprod` all resolve to no attach — so **one authoritative source is
   enough; do not write a `$_ENV ?? getenv()` fallback chain.** Keeps prod
   byte-identical. If the theme already implements that hook (grep —
   GM themes loading `theme/*.inc` often do), **merge into it**; a second copy
   fatals with `Cannot redeclare function`. **Pick the dev-server TLS mode with
   the user** (see references, "TLS & HMR: pick one"): *Option A* — `basic-ssl`
   on `https://localhost:<port>` (simplest, but an untrusted-cert warning to
   accept, re-triggered on every `npm install`); *Option B* — route the dev
   server through the shared Traefik on `https://<project>-vite.dev.localhost`
   so it reuses the trusted mkcert `*.dev.localhost` cert (no prompt, survives
   reinstalls). Default to A unless the cert warning bothers them.
5. **Docker / Makefile / CI** — node service runs/exposes Vite; drop dead
   BrowserSync env/labels; `install`/`init` and the CI build job run `npm run
   build` instead of `gulp deploy` (**artifact paths unchanged**). Point stale
   `npm-*` targets at the real scripts; remove `gulp*` targets.
6. **Break the Drupal caching chain — Arch B does not hot-reload without it.**
   This is mandatory, not optional. The plugins rewrite `css/theme.css` on disk
   correctly and Vite fires `full-reload`, yet the browser still shows the old
   styles because **three independent layers** cache in front of the file. All
   three must go, and each fails silently:

   | Layer | Why it defeats HMR | Fix |
   |---|---|---|
   | `system.performance` `css.preprocess` / `js.preprocess` | Drupal serves `sites/default/files/css/css_<hash>.css`; the hash derives from the asset **list**, not contents, so recompiling never invalidates the aggregate | `$config['system.performance']['css']['preprocess'] = FALSE;` (and `js`) |
   | `system.performance` `cache.page.max_age` (often 21600) | anonymous responses carry a multi-hour `Cache-Control`, so the browser reuses whole pages | `$config['system.performance']['cache']['page']['max_age'] = 0;` |
   | Drupal's `.htaccess` | sets `max-age=31536000` + `Expires` +1 year on theme assets; the asset URL only changes on a cache rebuild, so the browser replays its cached copy | dev-only `LocationMatch` in the apache vhost (below) |

   Put the two `$config` lines in the project's **shared local settings** file (a
   tracked `base.settings.php` or equivalent), not in a personal `settings.php`,
   so the whole team gets them. They are settings-level overrides, so `config/sync`
   is untouched and production keeps aggregation and page caching on.

   ```apache
   # docker/apache/vhost.conf — dev only, scoped to theme assets
   <LocationMatch "^/themes/custom/[^/]+/(css|js|images)/">
       Header set Cache-Control "no-store, no-cache, must-revalidate"
       Header unset Expires
       Header unset ETag
       FileETag None
   </LocationMatch>
   ```

   Requires `headers_module` (already enabled in the reference apache image).
   `vhost.conf` is `COPY`ed into the image, **not** bind-mounted, so it needs
   `docker compose build apache` + a recreate — and teammates need `make rebuild`
   to pick it up. Mention that explicitly; otherwise it works for you and for
   nobody else.

   Verify by checking headers, not by eyeballing the page:

   ```bash
   curl -ksSI https://<project>.dev.localhost/themes/custom/<theme>/css/theme.css \
     | grep -iE 'cache-control|expires'      # want: no-store, no-cache; no Expires
   curl -ksSI https://<project>.dev.localhost/core/misc/drupal.js \
     | grep -i cache-control                 # want: still max-age=31536000 (rule is scoped)
   curl -ksS https://<project>.dev.localhost/ \
     | grep -oE '/themes/custom/<theme>/css/[a-z.]+\.css'   # want the raw file, not css_<hash>.css
   ```

   Note the browser may still hold a year-long cached copy from **before** the
   fix: tell the user to hard-reload once (Cmd+Shift+R).

## Step 4 — Verify (do not skip)

- **Build in the container** (not the host): a clean `npm install && npm run
  build` in `<project>-node:latest` must print every plugin's success line
  (images only if you kept that plugin). Local macOS `ENOEXEC` on imagemin is
  host-arch only.
- **Inspect outputs**: `css/style.css` compressed + `font-size:*rem` (pxtorem
  applied); the expected count of per-paragraph CSS; minified single-line JS with
  structure preserved; a valid `sprites.svg`; hand-maintained CSS (ckeditor)
  untouched (`git status`).
- **Every declared asset resolves** — the strongest single check. Loop the
  theme-relative paths from `*.libraries.yml` (+ `.info.yml`
  `ckeditor5-stylesheets`) and assert each file now exists on disk:

  ```bash
  T=web/themes/custom/<theme>
  grep -oE "^\s+(css/|js/|styles/)[^:]+" $T/<theme>.libraries.yml | tr -d ' ' | sort -u |
    while read -r p; do [ -f "$T/$p" ] && echo "OK  $p" || echo "MISSING $p"; done
  ```

  This catches both migration regressions and the pre-existing 404s from Step 1.3.
- **PHP**: `php -l` + `phpcs --standard=Drupal,DrupalPractice` on the dev-wiring
  `.inc`.
- **Prod-safety**: confirm the dev client resolves to load **only** for
  `APP_ENV=local` — test `local`/`prod`/`preprod`/**empty**/**genuinely absent**.
  Test the absent case with `env -u APP_ENV php -r …`: overriding the superglobal
  alone is not enough, because the container's real env still leaks in through
  `getenv()` and makes an "unset" test falsely pass. Empty and absent must both
  resolve to *no attach*; see the references for the exact snippet.
- **The gate fires on a real request**, not just in the CLI: `curl -ksS
  https://<project>.dev.localhost/ | grep -c '@vite/client'` must return 1
  locally. A CLI `php -r` check passes even when the FPM worker sees no
  environment at all (`clear_env`), so it proves nothing on its own.
- **Clean diff**: no regenerated build artifact committed (`git checkout HEAD --`
  the force-committed ones; they're often silently *staged*).
- **Manual UAT** (needs the stack up): `make npm-dev`, accept the self-signed cert
  for `https://localhost:<port>` once (Option A only), confirm SCSS/JS/Twig edits
  auto-reload; visual diff; smoke-test the jQuery libs
  (swiper/fancybox/owl/masonry/mmenu); then deploy to preprod and check the CI
  build.
- **Hand the dev server back**: if you started one to verify, **kill it before
  telling the user to run `make npm-dev`** — `strictPort:true` means yours holds
  the port and theirs dies with `Port <port> is already in use`. Also revert any
  probe edit you made to a SCSS/JS file to test recompilation, and re-run
  `npm run build` so the on-disk output matches the committed sources.
- **When the user says "it doesn't hot-reload", diagnose in this order** — do not
  start by suspecting the Vite config:
  1. Is the dev server actually running, and does `@vite/client` return 200?
  2. Did the change reach the compiled file **on disk**? (`grep` the output.) If
     yes, the plugins are fine and the problem is downstream — go to 3.
  3. The Drupal/Apache caching chain (Step 3.6). This is almost always it.
  4. Only then look at the HMR websocket (`hmr.host`/`clientPort`/`protocol`).

  If the page contains **no `@vite/client` tag at all**, none of the above
  applies — the `APP_ENV` gate is reading an empty source (Step 1.11).

## Gotchas (learned the hard way)

- **imagemin ENOEXEC** on macOS/host arch is not a bug — verify in the container,
  whose Dockerfile compiles `imagemin-*` from source for ARM/Alpine. Do **not**
  trust another project's `-node` container as a reference: it may hold an x86
  prebuilt binary that fails under Rosetta.
- **imagemin can fail even IN a correctly-provisioned container.** `optipng-bin`
  compiles from source successfully, then its post-install `--version` check fails
  and **npm rolls back the entire install** (`node_modules` ends with 0 entries —
  not a partial install, nothing). Don't read this as "the toolchain is wrong" and
  start patching the Dockerfile: if `deploy` never called imagemin and the images
  are committed, **the answer is to drop the dependency**, which the migration does
  anyway. Confirm with `ls node_modules | wc -l` after a failed install.
- **Host dev-server port collides across GM projects** (each `-node` may publish
  the same port) → only one dev server at a time; `strictPort:true` fails loudly.
  That includes *your own* verification server (see Step 4).
- **`getenv('APP_ENV')` and `$_ENV['APP_ENV']` are not interchangeable.** With
  `vlucas/phpdotenv`'s `createImmutable()->safeLoad()` the `.env` values land in
  `$_ENV`/`$_SERVER` and `getenv()` stays `FALSE`, so a `getenv()`-based gate
  never attaches the client and you spend an afternoon in the Vite config. Two
  clean answers, in order of preference: (a) migrate `load.environment.php` to
  `symfony/dotenv` with `usePutenv(TRUE)` — `composer require drupal/dotenv`,
  then `(new Dotenv())->usePutenv(TRUE)->bootEnv(DRUPAL_ROOT . '/../.env')` —
  after which all three sources agree and the gate is a one-liner; or (b) leave
  the loader alone and read `$_ENV` only. What you must **not** do is paper over
  it with a `$_ENV['APP_ENV'] ?? getenv('APP_ENV') ?: ''` chain: it hides which
  source is authoritative, and the fail-closed property came from the strict
  `=== 'local'` all along, not from the fallback. `DRUPAL_ROOT` is safe to use in
  `load.environment.php` even though it runs from Composer's `autoload.files`:
  `drupal/core` declares `includes/bootstrap.inc` in *its* `autoload.files`, and
  dependencies' files are loaded before the root package's.
- **Force-committed build outputs get staged** by tooling and reappear in the
  diff; reset them to HEAD (`git checkout HEAD -- …`) before committing.
- **`gulp-iconfont` / `gulp-real-favicon`** are often present in deps but either
  unwired or replaceable by keeping the committed static output — check before
  porting; don't rebuild what nobody generates anymore. But **verify** rather than
  assume: when `fonticon` *is* in the deploy chain its output `_fonticon.scss` is a
  live SASS input and removing it breaks compilation (Step 1.4).
- **A task left out of `deploy` is usually broken, not forgotten.** Before
  "restoring" it under Vite, compile it once: SCSS that `@import`s a sibling
  theme's old path will fail, and you will have turned a green build red for no
  functional gain. Match `deploy`, and report the breakage as a separate ticket.
- **Opt-in scripts you add but never execute are untested** — say so explicitly
  rather than implying coverage (e.g. an `npm run icons` replacement you wrote but
  had no icon change to run it against).
- Pre-existing SASS deprecations (`slash-div`, etc.) surface under Vite too —
  they were there under Gulp; note them, don't fix in-scope.

## Deliverables

One focused branch + Draft MR. If the `gm:merge-request` skill is available,
delegate branch/commit/MR to it; otherwise do a plain branch → commit → push
(open the MR with `glab` if authenticated, else hand the user the branch name),
or skip the MR and commit on the current branch — ask the user which. Commit
only migration files; **exclude regenerated build artifacts**. Estimate
~1–1.5 day iso-functional incl. UAT.
