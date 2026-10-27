# claude-migration-skills

A [Claude Code](https://claude.com/claude-code) plugin: a pack of skills for
**migrating and modernizing web projects** — the Drupal 10 → 11 upgrade, the PHP
runtime bump, the frontend build, the stylesheets, and the coding standards —
and for **building a Drupal site** from a specification document and a Figma
mockup, one small reviewed unit at a time.

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
| [`drupal-scaffold`](skills/drupal-scaffold) | **Drupal** | Hands the scaffold files (`.htaccess`, `index.php`, `robots.txt`…) back to `core-composer-scaffold`: untracks and gitignores them, moves customizations into `scaffold/*-prepend.txt`, makes branch-only `.htaccess` edits (prod redirects, firewall, force-www) safe on every environment, and replaces a committed preprod `.htpasswd` with a `preprod-auth` CI job. |
| [`php-deprecations-audit`](skills/php-deprecations-audit) | **Drupal** | Audits and fixes deprecated APIs in custom code with `upgrade_status` + `drupal-rector` + PHPStan, looping until zero. Replayable for the next major. |
| [`gulp-to-vite`](skills/gulp-to-vite) | **Drupal** (theme) | Gulp → Vite build migration that leaves `*.libraries.yml` untouched, with the dev HMR wiring and the Drupal/Apache caches that must be off for it to work. |
| [`jquery-4-migration`](skills/jquery-4-migration) | **Drupal** (theme) — jQuery knowledge is generic | jQuery 3 → 4 (as shipped by Drupal 11): removed APIs, native replacements, and a scoped local polyfill for third-party libs that are not ready. |
| [`php-standards`](skills/php-standards) | **PHP** — any framework | Orchestrator for a coding-standards campaign: asks the standard (**Drupal + DrupalPractice, or PSR-12**), the severity, the PHPStan level, CI and the ticket once, sets up phpcs, then routes to the three passes below — one commit each, one conversation each. Re-entrant: re-invoke it after each `/clear`, it reads the repo state and resumes. Owns the phpcs/phpstan GitLab CI jobs (SonarQube report converters, no dev dependencies shipped) and the Draft MR, whose UAT is rebuilt from the commit bodies. |
| [`phpcbf`](skills/phpcbf) | **PHP** — any framework | Pass 1: one phpcbf run over the custom tree, unblocks every silent `FAILED TO FIX` file. Commit 1. |
| [`phpcs`](skills/phpcs) | **PHP** — any framework | Pass 2: hand fixes one sniff at a time, risky `DrupalPractice` sniffs last, each behaviour-changing fix recorded as a manual UAT step. Commit 2. |
| [`phpstan`](skills/phpstan) | **PHP** — any framework | Pass 3: PHPStan at `max` or a chosen level, Rector for the inferable types, one error shape at a time, UAT for runtime-changing guards. Commit 3. |
| [`drupal-build`](skills/drupal-build) | **Drupal** (Tailwind 4 starter) | Orchestrator for building a site from a specification document (CDC) and a Figma file: stateless and re-entrant, it reads the local `.build/` memory, recomputes every status from git and `glab`, offers the units whose dependencies are met, and routes to the three skills below. One unit per conversation, one branch and one Draft MR per unit. |
| [`drupal-build-intake`](skills/drupal-build-intake) | **Drupal** | Phase 0: reads the CDC in full and inventories Figma once, builds the `REQ-xxx` matrix, the CDC/Figma gap list and the blocking questions, then the build plan (units, dependency graph, order, branches) and the `.build/` files. No code. |
| [`drupal-build-foundations`](skills/drupal-build-foundations) | **Drupal** (Tailwind 4) | Phase 1: the whole style guide as `@theme` tokens (with an AA contrast report), base Twig components in every state, editor styles, the local-only `gm_demo` module (fixtures, `/styleguide`, three deployment locks) and the test tooling (PHPUnit, Playwright, axe, visual regression). |
| [`drupal-build-unit`](skills/drupal-build-unit) | **Drupal** | One unit (header, footer, recurring element, paragraph type, taxonomy, content type): brief tied to the REQs, Figma by node id, implementation, full self-verification on every delivered unit, RGAA then review, Playwright captures uploaded to the Draft MR, local UAT. |
| [`drupal-rgaa`](skills/drupal-rgaa) | **Drupal** | RGAA verdict on the real rendering, with a frozen call contract. Initial version: RGAA 4.1 criteria per component category while the Drupal checklist is built. |
| [`php-docker-upgrade`](skills/php-docker-upgrade) | **PHP** — any framework | Bumps the PHP version of the containers (8.4, 8.5, later) — target version is a parameter — and updates the Composer platform pin. |
| [`sass-migrator`](skills/sass-migrator) | **SCSS** — any stack | Migrates off deprecated Dart Sass syntax (`@import` → `@use`/`@forward`, division, `strict-unary`, `mixed-decls`) with a harness that proves the compiled CSS is unchanged, selector by selector and in cascade order. |

**Drupal-only** skills read `core.extension.yml`, run Drush, or manipulate
Drupal config; they will not do anything useful elsewhere.
**PHP / SCSS** skills only need the Docker + Makefile setup — `php-standards`
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

## Building a site from a CDC and a Figma

`drupal-build` turns a specification document (the source of truth) and a
Figma mockup (with its style guide) into a working site, delivered in small
units, each on its own branch with a Draft MR to `develop`:

0. **Intake** → `drupal-build-intake`: the full CDC and the Figma inventory
   are read **once**, into a requirement matrix and one brief per unit.
1. **Foundations** → `drupal-build-foundations`: design system, demo module,
   test tooling.
2. **Units** → `drupal-build-unit`, in dependency order: header, footer,
   recurring elements, media types, one MR per paragraph type, taxonomies,
   content types, third-party integrations.

The build always starts from the starter; an existing site can serve as a
source of blocks to port. Multisite (one theme, one database per site) and
client-customisable colours (a `palette` vocabulary turned into CSS custom
properties) are asked about in the intake.

The source hierarchy is **CDC > Figma > a reasoned proposal**, every
deviation recorded. The build memory lives in a local, uncommitted `.build/`
folder split into small files, so each session loads only the current unit's
brief and the **Contract** of its dependencies. Run `/drupal-build`, build one
unit, `/clear`, run it again.

It needs the Figma MCP, the Chrome extension for the visual comparison, and
`glab`. It assumes the agency's Drupal starter conventions (`gm_router`,
`Gm*` entity classes, `includes/*.inc` theme hooks, Tailwind 4) and falls back
to plain Drupal where one is missing.

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
/drupal-scaffold         # scaffold files under composer control (+ prepends, preprod auth CI)
/jquery-4-migration      # jQuery 3 → 4
/gulp-to-vite            # Gulp → Vite front build
/sass-migrator           # SCSS modernization
/php-standards           # coding-standards campaign: setup, then routes to the passes (+ CI jobs, MR)
/phpcbf                  # pass 1: phpcbf autofix
/phpcs                   # pass 2: phpcs hand fixes + UAT
/phpstan                 # pass 3: PHPStan at max or a chosen level
/drupal-build            # site build from a CDC + Figma: shows progress, routes to the next unit
/drupal-rgaa             # RGAA check of a rendered page or component
```

They also trigger on plain description — "migrate the theme to jQuery 4", "clean
up the coding standards", "upgrade this site to Drupal 11".

## Optional integrations

The skills detect these and degrade gracefully when they are missing:

- **`gm:merge-request` / `gm:review`** — in-house skills carrying a team's
  branch/commit/MR conventions. When present, the migration skills delegate the
  Git workflow to them; otherwise they fall back to plain git, or skip the MR.
  They ask once and remember the choice.
- **`gm:security`**: an in-house dependency and infrastructure audit. `d11` runs
  it after the core bump, then folds its package-update fixes into the step's MR.
  Without it, `d11` runs `composer audit`, `npm audit` and the image check
  itself.
- **`glab`**, authenticated against your GitLab host, for creating the merge
  requests.
- **`gm:drupal` / `gm:ticket`**: in-house Drupal and brief conventions;
  `drupal-build-unit` loads `gm:drupal` for the backend and shapes its plans
  like a `gm:ticket` brief.
- **Figma MCP** and **Claude in Chrome**: required by the `drupal-build`
  family (reading the mockup, comparing the rendering).

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
