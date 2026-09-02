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

[Unreleased]: https://github.com/JMAILLY/claude-migration-skills/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/JMAILLY/claude-migration-skills/releases/tag/v1.0.0
