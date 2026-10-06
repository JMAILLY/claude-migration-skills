# Changelog

All notable changes to this plugin are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

What each bump means for a **skill pack**:

- **MAJOR** — a skill is removed or renamed, or a procedure changes in a way
  that invalidates a migration already in progress.
- **MINOR** — a new skill, or new capability in an existing one.
- **PATCH** — corrections, clarifications, new failure modes documented; no
  change to what a skill is for.

## [Unreleased]

## [1.4.0] — 2026-10-06

### Added

- `sass-migrator`: order-aware verification. `strict.mjs` requires the same
  rule sequence and declarations and flags reordered interacting properties
  (shorthand/longhand, `font`/`line-height`, `inset`/sides), which the
  last-wins `cssdiff.mjs` cannot see. The harness also gains `compile.mjs`
  (every entrypoint, all warnings tallied by type with `verbose: true`),
  `culprits.mjs` (mixed-decls sites by causing include) and `hook.mjs`.
- `sass-migrator`: the `@content` slot for mixins that emit declarations and
  nested rules, so callers that override one of their properties keep the
  original cascade order.
- `sass-migrator`: new failure modes from the ginger-sofreco run — nested
  `@import` turned into `meta.load-css()` (extends do not reach it), mixins
  defined twice across files (pre-scan included), lost contextual `@extend`
  cross-products, migrator-unnamespaced default arguments, `max()` shims
  bound to an unrelated module, the `if-function` migrator on an older Sass
  pin, and zsh word-splitting of the entrypoint list.

### Changed

- `sass-migrator`: `& {}` is no longer recommended for mixed-decls
  collisions. It lands after the mixin's `@media` and overrides it at that
  breakpoint.
- `sass-migrator`: a `MISSING RULE` is no longer assumed benign. A
  `<context> <extender>` mirroring a `<context> .target` override is a lost
  contextual override.
- `sass-migrator`: `reorder.mjs` only carries plain declarations (an
  `@include` in the run could emit nested rules), and both CSS parsers keep
  a last declaration written without `;`.

## [1.3.2] — 2026-10-05

### Changed

- `phpcs-standards`: the template `phpstan.neon` ignores
  `offsetAccess.nonOffsetAccessible`. Nested offset reads on render arrays
  and hook parameters no longer get an inline `@var array{…}` that only
  restates the Drupal structure; a `@var` or a guard is still owed where
  the value feeds a typed function, a `foreach` or a method call. Projects
  set up with 1.3.0 or 1.3.1 get a one-pass cleanup procedure.

## [1.3.1] — 2026-10-05

### Changed

- `phpcs-standards`: the CI QA jobs now reuse the existing composer job
  (without `--no-dev`) when the server rebuilds `vendor/` with
  `composer install --no-dev`, which is the agency's Deployer default. A
  separate `composer_qa` install is kept only for pipelines whose CI
  `vendor/` ships. The contrib directories are excluded from the deploy
  upload in that case.

## [1.3.0] — 2026-10-05

### Added

- **`phpcs-standards`** now covers PHPStan as well as phpcs. Step 0 asks for the
  level. `references/phpstan.md` has the dependencies, a `phpstan.neon`
  template and the fix catalogue for level `max` on Drupal code (typed hooks,
  inline `@var` array shapes, `instanceof` / `is_array()` guards, `.install`
  files annotated only), with which fixes change runtime behaviour and need a
  UAT line. It also covers the conflicts with DrupalPractice.
- **`phpcs-standards`** can add the phpcs and phpstan GitLab CI jobs with their
  SonarQube report converters (`references/ci-pipelines.md`). That includes a
  separate `composer_qa` install, because the deploy install is `--no-dev`,
  the Deployer excludes for the QA files, and an optional scanner job. Step 0
  asks for the branches, report-only vs gating, and Sonar now or later.

### Documented

- The agency `phpstan.neon` ignore patterns for hooks were written for
  PHPStan 1 ("no typehint specified"). Under PHPStan 2 they match nothing,
  and `reportUnmatchedIgnoredErrors: false` hides that.
- The template jobs run the tools with `|| true`, so they never fail on a
  violation. `sonar-project.properties` without a scanner job sends nothing to
  SonarQube. A scanner job in the same stage as the QA jobs never receives
  their reports.
- Makefile targets that read `ARGS=` silently drop `c='…'`.

## [1.2.1] — 2026-09-30

### Fixed

Every item below was a finding in the review of the agena3000 migration MRs
(Lando → Docker, Gulp → Vite) and traced back to a template in these skills.

- **`lando-to-docker`** — `xdebug.ini` was mounted over
  `docker-php-ext-xdebug.ini`, replacing the `zend_extension` line written by
  `install-php-extensions`: Xdebug never loaded. Now mounted as
  `zz-xdebug.ini`, and the php service always carries
  `extra_hosts: host.docker.internal:host-gateway` (Linux hosts).
- **`lando-to-docker`** — `make db-import` tested `-n` before `sql-drop`, so a
  typo in the path wiped the local DB. Now `test -f`.
- **`lando-to-docker`** — `make init` regenerated `HASH_SALT` on every run
  (invalidating sessions and `uli` links). Now generated only when empty, with a
  portable `sed -i.bak` instead of the uname branch; `init` no longer runs `up`
  twice.
- **`lando-to-docker`** — the catch-all `%:` no-op swallowed mistyped targets
  (`make updv` exited 0). It now only swallows the positional words.
- **`lando-to-docker`** — Mailpit was documented as catching all mail while the
  transport lives in the imported DB, so local sends went through the real
  transport. `drupal-glue.md` now overrides every symfony_mailer transport (and
  covers the smtp module / `php_mail`), and the verification requires a real
  send observed in Mailpit.
- **`lando-to-docker`** — the extension installer is pinned instead of
  `releases/latest`; redundant `build-essential` and the entrypoint DB wait
  loop (duplicate of `service_healthy`) removed; `error_reporting = E_ALL` in
  dev; the mysql driver namespace is `Drupal\mysql\Driver\Database\mysql`.
- **`lando-to-docker`** / **`gulp-to-vite`** — the Vite dev server shipped with
  `cors: true`, `root: 'web'` and a port published on `0.0.0.0`: the raw
  docroot (`settings.php`, `.env`) was readable from the LAN and from any
  visited site. CORS is now limited to `HOME_URL`, `server.fs.deny` covers
  PHP/YAML/env files, and Option B publishes no port (Option A binds
  `127.0.0.1`). `watch.ignored` now excludes core and contrib.
- **`gulp-to-vite`** — the manifest fallback became dead code once the manifest
  was retired, and docs/`CLAUDE.md` kept claiming a "top-level globals"
  invariant the IIFE had removed. `vendor-libs-to-libraries.md` now requires
  removing both in the same diff.
- **`gulp-to-vite`** — a sharp variant of the images plugin with lossless PNG
  (never `palette: true`, which quantises to 256 colours); the sprite plugin
  skips icons without a `viewBox` instead of writing `viewBox="undefined"`; the
  sass plugin no longer silences `legacy-js-api`, which `compile()` never emits.
- **`lando-to-docker`** / **`gulp-to-vite`** — Verify steps now test the failure
  paths above (mistyped target, missing dump, `init` twice, `php -m`, dev-server
  exposure, image quantisation, stale docs) and the house coding rules (return
  types, JSDoc) before the MR.

## [1.2.0] — 2026-09-09

### Added

- **`gulp-to-vite`** — `references/vendor-libs-to-libraries.md`, the follow-up
  that retires a root concat manifest (`site.json`'s `jsFiles`) in favour of real
  `*.libraries.yml` entries served from the theme's own `node_modules`. It covers
  the second `package.json` the theme needs — library paths resolve relative to
  the defining extension, so the repo-root `node_modules` is unreachable — load
  order coming from `weight` rather than YAML order and verified against the
  served HTML, and the deployment rule that hinges on one character: an
  unanchored `--exclude=node_modules` also skips the theme's copy and 404s every
  library in production, with the `rsync --dry-run` commands that prove it.
- **`gulp-to-vite`** — the jQuery `noConflict` trap. Dropping a theme's bundled
  jQuery for `core/jquery` looks like a free win because it removes a real double
  load, but core runs `jQuery.noConflict()` in `core/misc/drupal.init.js` and
  deletes `window.$`, which the bundled copy was re-creating afterwards. That side
  effect is load-bearing; removing it throws `$ is not a function` on the first
  line of the theme bundle. Includes the three pre-flight greps to run before
  wrapping the file in `(function ($) { … })(jQuery)`, since the wrapper also
  scopes every top-level name.
- **`gulp-to-vite`** — what the approach exposes and what it costs, both stated
  up front: a theme's `node_modules` sits inside the docroot, so npm metadata
  becomes publicly readable (`package.json`, READMEs and `.map` files all answer
  200) and lets anyone enumerate library versions against known CVEs — Drupal's
  `.htaccess` blocks `composer.json`, not `package.json`, so the rule is added —
  and 8.1 MB / 511 files for five libraries, 3.2 MB of it a jQuery pulled in
  transitively and never served.
- **`gulp-to-vite`** — step 1 now classifies the two classic-JS shapes, because
  per-file copy and concat manifest need different plugins, and tells you to give
  the concat plugin a fallback so deleting the manifest later is a no-op.
- **`gulp-to-vite`** — two new gotchas: a plugin that writes the file type it
  watches rebuilds forever, since the Arch B outputs live inside Vite's root, so
  `server.watch.ignored` must exclude them *and* each plugin must ignore its own
  output; and `ps | grep -c` self-matches and reports a live dev server as dead,
  which is how you end up handing the user a `Port already in use`.

## [1.1.0] — 2026-09-02

### Added

- **`jquery-4-migration`** — a **compatibility gate** that must be walked before
  any polyfill is written. The npm registry is not the source of truth: a
  package frozen for years there can have a live repository whose jQuery-4 fix
  ships as a git tag only, so the skill now walks registry → tags/releases →
  default-branch HEAD → active forks, audits the candidate file itself with the
  token scan instead of trusting its changelog, and requires the "no compatible
  version exists" verdict to be written into the merge request with its evidence.
- **`jquery-4-migration`** — how to vendor a library from a git tag: why the
  asset stays first-party rather than served from a CDN (privacy, aggregation,
  cache partitioning, mutable refs), pinning to a tag or commit SHA, the
  provenance header every vendored file carries, diffing the current copy
  against its own upstream release to detect a local patch before swapping, and
  updating every shipped copy including an unreferenced minified twin.

### Fixed

- **`jquery-4-migration`** said `$.isEmptyObject` and `$.proxy` were "still
  present but watch for removal", which read as a reason to shim them. They are
  shipped by jQuery 4.0.0 — `$.proxy` deprecated, not removed — alongside
  `$.uniqueSort`. A library calling only these needs no shim at all.

## [1.0.1] — 2026-09-02

### Fixed

- **Installation instructions** assumed a local clone (`/plugin marketplace add
  ./`), which is the contributor path, not the user path. The README now leads
  with `/plugin marketplace add JMAILLY/claude-migration-skills` and keeps the
  `directory`-source clone as a separate "working on the skills" section.
- **`phpcs-standards`** said the manual-UAT entries go in the MR "in French".
  They go in whatever language the team writes its merge requests in; the
  French examples are labelled as such.

## [1.0.0] — 2026-09-02

First public release. Eight skills for migrating and modernizing web projects
that are Dockerized and driven by a `Makefile`.

### Added

- **`lando-to-docker`** (Drupal) — local dev from Lando to Docker Compose + a
  `Makefile`: Traefik on `*.dev.localhost`, PHP-FPM + Apache, MariaDB, Redis,
  Adminer, Mailpit. Single-site and multisite. Produces the `Makefile` the rest
  of the pack depends on.
- **`d11`** (Drupal) — orchestrator for the Drupal 10 → 11 upgrade: the safe
  step order, cascading branches with one Draft MR per step, module cleanup with
  deployable uninstall update hooks, contrib bump, core bump and apply.
- **`php-deprecations-audit`** (Drupal) — deprecated-API audit and fixes with
  `upgrade_status`, `drupal-rector` and PHPStan, looped until zero. Must run
  while core is still on the old major.
- **`gulp-to-vite`** (Drupal theme) — Gulp → Vite build migration that leaves
  `*.libraries.yml` untouched, with the dev HMR wiring and the Drupal/Apache
  caching layers that have to be off for HMR to work.
- **`jquery-4-migration`** (Drupal theme) — jQuery 3 → 4: removed APIs, native
  replacements, and a scoped local polyfill for third-party libraries that are
  not ready.
- **`phpcs-standards`** (any PHP framework) — PHP_CodeSniffer setup or
  verification, then a zero-violation pass over the custom code. Asks which
  standard (Drupal + DrupalPractice, or PSR-12) and which severity; works around
  phpcbf's silent `FAILED TO FIX`; records every behaviour-changing fix as a
  manual UAT step in the merge request.
- **`php-docker-upgrade`** (any PHP framework) — PHP version bump of the
  containers, target version as a parameter, plus the Composer platform pin.
- **`sass-migrator`** (any stack) — migration off deprecated Dart Sass syntax
  with a harness that proves the compiled CSS is byte-identical.

[Unreleased]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.3.1...HEAD
[1.3.1]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/JMAILLY/claude-migration-skills/releases/tag/v1.0.0
