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

[Unreleased]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/JMAILLY/claude-migration-skills/releases/tag/v1.0.0
