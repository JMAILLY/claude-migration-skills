# claude-migration-skills

A [Claude Code](https://claude.com/claude-code) plugin: a pack of skills for
**migrating and modernizing web projects** — the Drupal 10 → 11 upgrade, the PHP
runtime bump, the frontend build, the stylesheets, and the coding standards.

Each skill encodes a procedure that has been run on real projects, including the
failure modes that are not in the official docs: the fixer that silently
discards its own work, the polyfill you must keep before you can remove it, the
caching layers that make HMR look broken.

## Prerequisite: Docker + a Makefile

**Every skill here assumes the project is Dockerized and driven by a
`Makefile`**, and every command they run goes through a `make` target
(`make drush c='…'`, `make phpcs`, `make npm-build`) rather than the host. That
is the one hard requirement.

If your project has no such setup — or is still on Lando — run
**`lando-to-docker`** first: it produces exactly the environment the others
expect.

## The skills

| Skill | Scope | What it does |
|---|---|---|
| [`lando-to-docker`](skills/lando-to-docker) | **Drupal** | Local dev from Lando → Docker Compose + Makefile (Traefik on `*.dev.localhost`, PHP-FPM + Apache, MariaDB, Redis, Adminer, Mailpit). Single-site or multisite. Produces the `Makefile` the rest of the pack depends on. |
| [`d11`](skills/d11) | **Drupal** | Orchestrator for Drupal 10 → 11: owns the safe order, the cascading branches, and the D11-specific work (module cleanup with deployable uninstall hooks, contrib bump, core bump + apply). Delegates to three sub-skills below. |
| [`php-deprecations-audit`](skills/php-deprecations-audit) | **Drupal** | Audits and fixes deprecated APIs in custom code with `upgrade_status` + `drupal-rector` + PHPStan, looping until zero. Replayable for the next major. |
| [`gulp-to-vite`](skills/gulp-to-vite) | **Drupal** (theme) | Gulp → Vite build migration that leaves `*.libraries.yml` untouched, with the dev HMR wiring and the Drupal/Apache caches that must be off for it to work. |
| [`jquery-4-migration`](skills/jquery-4-migration) | **Drupal** (theme) — jQuery knowledge is generic | jQuery 3 → 4 (as shipped by Drupal 11): removed APIs, native replacements, and a scoped local polyfill for third-party libs that are not ready. |
| [`phpcs-standards`](skills/phpcs-standards) | **PHP** — any framework | Sets up or verifies PHP_CodeSniffer, then clears custom code to zero violations. **Asks which standard: Drupal + DrupalPractice, or PSR-12.** Handles phpcbf's silent `FAILED TO FIX`, and turns every behaviour-changing fix into a manual UAT step in the merge request. |
| [`php-docker-upgrade`](skills/php-docker-upgrade) | **PHP** — any framework | Bumps the PHP version of the containers (8.4, 8.5, later) — target version is a parameter — and updates the Composer platform pin. |
| [`sass-migrator`](skills/sass-migrator) | **SCSS** — any stack | Migrates off deprecated Dart Sass syntax (`@import` → `@use`/`@forward`, division, `strict-unary`, `mixed-decls`) with a harness that proves the compiled CSS is byte-identical. |

**Drupal-only** skills read `core.extension.yml`, run Drush, or manipulate
Drupal config; they will not do anything useful elsewhere.
**PHP / SCSS** skills only need the Docker + Makefile setup — `phpcs-standards`
explicitly asks whether to apply the Drupal standard or PSR-12, and
`sass-migrator` never looks at the framework at all.

## The Drupal 10 → 11 upgrade

`d11` runs the steps in the only order that works, invoking the reusable
sub-skills at the right moment:

1. **PHP 8.4** in Docker → `php-docker-upgrade`
2. Backup (`make db-export`, `make cex`)
3. Cleanup of unused modules/themes — **still on D10**
4. **PHP/Drupal deprecations** in custom code → `php-deprecations-audit` — **still on D10**
5. **jQuery 3 → 4** in the theme → `jquery-4-migration` — **still on D10**
6. Contrib modules to their D11-ready versions
7. Drupal 11 core bump + apply (`make updb`, `make cim`, build)

> Deprecations are fixed **before** the core bump on purpose: Upgrade Status and
> rector derive their target from the *installed* core, so on D10 they surface
> "removed in D11". Once core is on D11 they switch to the D12 target and the
> D11 correction list becomes unreachable.

Each major step produces its own branch and its own Draft merge request, all
sharing the same tracker ticket (asked once, at the start).

Every module removal is paired with a **deployable uninstall update hook** —
deleting a module from `composer.json` is not enough; staging and production
still have it installed, and `cim` will fail there.

## Installation

From any Claude Code session:

```
/plugin marketplace add JMAILLY/claude-migration-skills
/plugin install claude-migration-skills@migration-marketplace
/reload-plugins
```

Check it took — `claude-migration-skills` should be listed:

```
/plugin
```

The plugin installs at **user scope**, so the skills are available in every
project.

### Working on the skills themselves

To edit the skills and have the changes apply with no reinstall, register your
clone as a `directory` marketplace instead:

```
git clone https://github.com/JMAILLY/claude-migration-skills.git
cd claude-migration-skills
/plugin marketplace add ./
/plugin install claude-migration-skills@migration-marketplace
```

A `directory` source reads the files in place; a `github` source works from a
cached checkout that only refreshes on update.

## Usage

Run Claude Code **at the project root**, then invoke a skill:

```
/lando-to-docker         # set up the Docker Compose + Makefile dev environment
/d11                     # Drupal 10 → 11, full orchestration
/php-docker-upgrade      # PHP bump in Docker
/php-deprecations-audit  # custom-code deprecations audit
/jquery-4-migration      # jQuery 3 → 4
/gulp-to-vite            # Gulp → Vite front build
/sass-migrator           # SCSS modernization
/phpcs-standards         # phpcs/phpcbf setup + zero-violation pass
```

They also trigger on plain description — "migrate the theme to jQuery 4", "clean
up the coding standards", "upgrade this site to Drupal 11".

## Optional integrations

The skills detect these and degrade gracefully when they are missing:

- **`gm:merge-request` / `gm:review`** — in-house skills carrying a team's
  branch/commit/MR conventions. When present, the migration skills delegate the
  Git workflow to them; otherwise they fall back to plain git, or skip the MR.
  They ask once and remember the choice.
- **`glab`**, authenticated against your GitLab host, for creating the merge
  requests.

Nothing in the pack requires GitLab; the Git workflow can be skipped entirely.

## Conventions used throughout

- **Never run a command on the host.** `composer`, `drush`, `npm`, `phpcs` and
  `php` all run inside their container, through a `make` target. The skills say
  so in bold, repeatedly, because it is the single most common way these
  procedures go wrong.
- **Nothing is verified by reading a tool's summary line.** phpcbf claims
  successes it discarded; `composer update` claims a version it did not install.
  Each skill states the empirical check that actually proves the step.
- **Behaviour-changing work is isolated and tested by hand.** A refactor that no
  test suite covers gets its own commit and an explicit manual-UAT entry in the
  MR.

## Versioning and releases

Releases follow [Semantic Versioning](https://semver.org/). For a skill pack
that means: **MAJOR** when a skill is removed or renamed, or when a procedure
changes in a way that invalidates a migration already in progress; **MINOR** for
a new skill or a new capability; **PATCH** for corrections and newly documented
failure modes.

Every release is tagged `vX.Y.Z` and described in [CHANGELOG.md](CHANGELOG.md).
The version in `.claude-plugin/plugin.json`, the one in
`.claude-plugin/marketplace.json` and the tag are kept in sync — bump all three
in the release commit.

## Uninstall

```bash
/plugin uninstall claude-migration-skills@migration-marketplace
```

## License

[MIT](LICENSE).
