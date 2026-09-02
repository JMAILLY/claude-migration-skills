---
name: d11
description: >
  Orchestrate the upgrade of a Dockerized, Makefile-driven Drupal 10 site to
  Drupal 11. Use when the user mentions a Drupal upgrade/migration, "D10 to
  D11", or wants the full campaign run in the correct order. Sequences three
  reusable sub-skills — php-docker-upgrade (PHP 8.4), php-deprecations-audit
  (upgrade_status/rector/phpstan), jquery-4-migration — around the D11-specific
  work it owns itself (module cleanup with deployable uninstall/purge update
  hooks, then a combined contrib + core bump + apply) and a per-step Git workflow
  (one Draft MR per step). IMPORTANT: fix deprecations BEFORE bumping core; pair
  every module removal with an uninstall hook so preprod/prod do not break on
  cim; all Drupal commands MUST go through Makefile targets.
---

# Drupal 10 → 11 Upgrade Orchestrator (Dockerized / Makefile project)

This skill **orchestrates** the upgrade: it owns the correct order, the Git
cascade, and the D11-specific steps, and it **delegates** the three
independently-reusable pieces to dedicated sub-skills:

| Delegated to | Covers | Step |
|---|---|---|
| **`php-docker-upgrade`** | PHP 8.4 in Docker | 2 |
| **`php-deprecations-audit`** | upgrade_status + rector + phpstan on custom code | 4 |
| **`jquery-4-migration`** | jQuery 3 → 4 in the theme | 5 |

Those sub-skills are usable on their own; here they run in sequence, wrapped in
the Git/MR protocol below. When you reach steps 2, 4 and 5, **invoke the named
sub-skill** and come back for the step's "Close" (MR) part.

## Golden rule: everything goes through the Makefile

This project is **Dockerized and driven by a Makefile**. All Drupal commands
run inside containers via `make`. **Never call `drush`, `composer`, `npm` or
`php` directly** on the host — always use a `make` target.

| Need | Make target |
|---|---|
| Generic Drush command | `make drush c='<cmd>'` |
| Clear cache | `make cr` |
| Generic Composer | `make composer c='<args>'` |
| Add a dependency | `make composer-require <pkg>` |
| Remove a dependency | `make composer-remove <pkg>` |
| Run DB updates | `make updb` |
| Export / import config | `make cex` / `make cim` |
| Enable / uninstall module | `make en <m>` / `make pmu <m>` |
| DB dump / import | `make db-export` / `make db-import <f>` |
| Static analysis / lint / fix | `make phpstan` / `make phpcs` / `make phpcbf` |
| Build theme assets | `make npm-build` (or `make gulp-deploy` only if the theme still uses Gulp) |
| Start / rebuild containers | `make up` / `make rebuild` / `make rebuild-no-cache` |
| Shell in PHP container | `make shell` |
| Admin one-time login link | `make uli uid=1` |

For commands that must run inside the container (rector, php -v…), use
`make shell` and execute from within.

> ⚠️ **`--` flags break `make`.** `make composer <pkg> --no-update` makes Make
> treat `--no-update` as an (invalid) option and abort. Always pass Composer
> flags **inside** `c='…'`: `make composer c='require <pkg> --no-update'`.

> ⚠️ **Newlines break `make` too — keep every `c='…'` on ONE line.** Make runs
> each recipe line in its own `/bin/sh -c`, so a multi-line `c='eval "…"'` is cut
> at the first newline and fails with
> ``sh: -c: line 0: unexpected EOF while looking for matching `"'``. Long PHP
> snippets in this skill are therefore written as one (long) line — do not
> reformat them for readability. For anything genuinely long, `make shell` and run
> `drush eval` from inside the container instead.

> 💡 **PHP 8.4 deprecation noise.** From step 2 onward, contrib code triggers
> PHP 8.4 "implicitly marking parameter … as nullable" notices that Drupal
> prints on **every** `drush` / `composer` call, drowning real output. Filter
> while parsing: `… 2>&1 | grep -viE "Deprecated:|Implicitly marking"`. They
> clear as contrib is bumped to its D11 release (or patched) in step 6 — a clean
> `make cr` with **0** deprecation lines is a good end-state signal.

## Operation order (IMPORTANT)

**Key rule: fix deprecations BEFORE bumping core.**
Upgrade Status and drupal-rector detect and fix APIs "deprecated in D10, removed
in D11" **only while the site is still running Drupal 10**. If you bump core to
D11 first, those APIs are already gone: Upgrade Status switches to targeting
Drupal **12** ("deprecated in D11, removed in D12") and the D11 fix list becomes
unreachable. Custom code must be made "D11-ready" while still on D10.

Correct order:

1. **Backup** (db-export, cex, files)
2. **PHP 8.4** (Docker) → sub-skill `php-docker-upgrade` — technical prerequisite
3. **Cleanup**: remove unused modules/themes → `references/contrib-and-cleanup.md`,
   each removal paired with an uninstall hook → `references/uninstall-update-hooks.md`
4. **Audit + fix custom PHP deprecations — ON D10** → sub-skill `php-deprecations-audit`
5. **jQuery 4 theme migration — ON D10** → sub-skill `jquery-4-migration`
6. **Contrib + Drupal 11 core bump in ONE Composer transaction, then apply**
   (updb, cim/cex, build) + **verify** — only once steps 3–5 are done

> Loop: fix custom code / jQuery / contrib until Upgrade Status shows 0 D11
> errors, THEN do the combined bump.
>
> **Why contrib and core are ONE step (not two):** a two-phase approach — bump
> contrib on D10, then core — usually hits an *unsolvable intermediate state*,
> because most D11-ready contrib releases require `drupal/core:^11` (they dropped
> D10 support), so `composer require` fails while core is still `^10`, and the
> reverse fails too. Raising core **and** all blocking contrib in a single
> `composer update --with-all-dependencies` lets Composer resolve the whole graph
> at once. Steps 2–5 already made the code D11-ready on D10, so the golden rule
> still holds.

---

## Git workflow: cascading branches + one Draft MR per step

Each major upgrade step produces **its own branch and its own Draft MR**, all
tied to the **same Mantis ticket**.

> **The `gm:merge-request` / `gm:review` skills are optional.** Check the
> available-skills list at the start of the session and adapt:
>
> - **If `gm:merge-request` is available**, delegate branch/commit/MR creation
>   to it — it carries the team's conventions (branch `fix/<ticket>-<slug>`,
>   commit `type(scope: #<ticket>): …`, the self-hosted GitLab host, MR as
>   Draft). Likewise use `gm:review` for the per-step review.
> - **If it is NOT available**, ask the user once how to close each step:
>   **(a)** run the git workflow manually following the conventions in this
>   section (branch → surgical commit → push, then open the MR with `glab` if
>   authenticated), or **(b)** skip branching/MR entirely and just apply each
>   step's changes on the current branch. Remember the choice for the session.
>
> The conventions below (branch names, cascade, staging discipline) apply either
> way — only *who* performs the commit/MR changes.

### Cascading branches (IMPORTANT)

Each branch is created from the previous step's branch, **not from `develop`**.
Without this, the final bump does not include the fixes from steps 3–5 and the
same errors resurface during the bump.

```
develop
  └─ fix/<ticket>-php84-docker
       └─ fix/<ticket>-cleanup-modules
            └─ fix/<ticket>-deprecations-custom
                 └─ fix/<ticket>-jquery4
                      └─ feat/<ticket>-core-d11   (contrib + core bump, combined)
```

**Starting each step:**
```bash
git checkout fix/<ticket>-previous-step   # base = previous step's branch
git checkout -b fix/<ticket>-this-step
```

**Branch convention** (per-step slug, shared ticket):

| Step | Base | Branch |
|---|---|---|
| PHP 8.4 (Docker) | `develop` | `fix/<ticket>-php84-docker` |
| Module cleanup | previous step | `fix/<ticket>-cleanup-modules` |
| Custom PHP deprecations | previous step | `fix/<ticket>-deprecations-custom` |
| jQuery 4 (theme) | previous step | `fix/<ticket>-jquery4` |
| Contrib + D11 core bump | previous step | `feat/<ticket>-core-d11` |

**Branch base rule:** the **first branch** (PHP 8.4) starts from an up-to-date
`develop`; every subsequent branch starts from the previous step's branch.

### Closing each step (MR protocol)

Every step ends the same way — don't repeat the reasoning per step. Adapt to
what's available (see the note above):

1. **Review** — if `gm:review` is available, run it on the step's modified files
   and put its verdict in the MR's "Verification" section. Otherwise do a brief
   manual self-review of the diff (`/code-review` or a read-through).
2. **Commit + MR** — if `gm:merge-request` is available, invoke it with ticket
   `<ticket>` (captured in step 0). Otherwise fall back to the workflow the user
   chose when gm was found absent:
   - **Manual**: stage **only this step's files** (surgical staging), commit as
     `type(scope: #<ticket>): …`, push the branch, and — if `glab` is
     authenticated — open a **Draft** MR targeting the previous step's branch
     (step 2 → `develop`); if `glab` is absent, push and hand the user the
     branch name to open the MR themselves.
   - **Skip**: keep the step's changes on the current branch and move on.
3. If an MR is opened it stays **Draft**: never mark Ready / merge without
   explicit user approval.

> Running Drupal (`updb`/`cr`, or just browsing) regenerates a few
> tracked-but-runtime files — e.g. `web/sites/default/files/.htaccess` and
> compiled translation JS aggregates. They reappear as "modified" after almost
> every command; `git restore` them before each surgical commit so they never
> leak into an MR.

Below, each step's **▸ Close:** line gives only what differs: the commit scope
and any extra "Verification" content.

---

## Step 0 — Start the environment & capture the ticket

```bash
make up
make drush c='status'
```

**Ask the user for the Mantis ticket number right now** (once only) — it will
be reused for all branches and MRs in the session. If the user already provided
it in their request, use it. Store it as `<ticket>` (e.g. `12345`) for branch
names and commit messages delegated to gm.

## Step 1 — Backup

```bash
make db-export
make cex           # freeze current config (rollback point)
tar -czf files_backup_$(date +%Y%m%d).tar.gz web/sites/default/files/
```

Git-commit the saved state before continuing.

## Step 2 — PHP 8.4 upgrade (Docker) → sub-skill `php-docker-upgrade`

> 🌿 Branch: `git checkout develop && git pull`, then work on
> `fix/<ticket>-php84-docker`.

Recent Drupal 11 requires **PHP 8.4**. This is a technical prerequisite done
BEFORE any other operation.

**Invoke the `php-docker-upgrade` sub-skill with target PHP version 8.4.** It
locates the PHP image, bumps 8.3 → 8.4, runs `make rebuild`, verifies `php -v`,
and reinstalls dependencies.

> ▸ **Close** (see MR protocol): commit Dockerfile + composer.json (if
> `platform.php` changed). Bump the CI runner image too if it pins PHP/node
> (e.g. `php-8.1-node-20` → `php-8.4-node-22`). Target `develop`.

## Step 3 — Cleanup: unused modules & themes (ON D10)

> 🌿 Branch: from `fix/<ticket>-php84-docker` → `fix/<ticket>-cleanup-modules`.

Clean up now, while still on D10: less code to audit and fix later. See
**`references/contrib-and-cleanup.md`** (section "Unused modules & themes").

```bash
make drush c='pml --type=module --status=disabled'   # candidates
make pmu <unused_module>
make composer-remove drupal/<unused_module>
make cex
```

### Pair EVERY removal with an uninstall hook (IMPORTANT)

The `make pmu` above only cleans **your local** database. Preprod and prod still
list the module in `core.extension` and `system.schema` while its code is gone —
which breaks `cim` and, worse, makes *every* later module install throw
`The module <name> does not exist.`

So each module or theme dropped from `composer.json` needs an **update hook** in
a project-owned, always-installed module (typically `<project>_global_config`),
committed in the same MR as the removal.

Two facts make the obvious hook a silent no-op in production, so read
**`references/uninstall-update-hooks.md`** before writing one:

- the deploy order is `composer install` → `cr` → `updatedb` → `config-import`,
  so **the code is already deleted** when your hook runs;
- `ModuleInstaller::uninstall()` then returns `FALSE` **silently** — no throw, no
  log. The hook needs a second path that purges the registry by hand.

The reference file carries the two-path hook template, the reusable purge helper,
the theme variant (easier — `ThemeInstaller` copes with missing code), and how to
verify the purge path against a pre-removal database dump.

### D11 compatibility in info.yml files

Update `core_version_requirement` in **all** `.info.yml` files for custom
modules, features, and themes right now — without this, `updb` in the combined
bump (step 6) will list all custom modules as "D11.x incompatible" and block.

```bash
# Check what needs updating
grep -rl "core_version_requirement" modules/custom/ modules/features/ themes/custom/

# Update in one pass
find modules/custom/ modules/features/ themes/custom/ -name "*.info.yml" \
  | xargs grep -l "core_version_requirement" \
  | while read f; do
      sed -i 's/core_version_requirement: \^8 || \^9 || \^10$/core_version_requirement: ^8 || ^9 || ^10 || ^11/' "$f"
    done

# Verify the result
grep -r "core_version_requirement" modules/custom/ themes/custom/ | head -5
```

> ⚠️ The `sed` above only matches the exact constraint `^8 || ^9 || ^10`. Any
> `.info.yml` with a different format (e.g. `^9 || ^10`, or a single `^10`) is
> left untouched — manually check every file the verify `grep` still shows
> without `^11`.

> ▸ **Close** (see MR protocol): commit the removed code + updated `.info.yml`
> files + the uninstall hooks (`<project>_global_config.install`) + config export
> (`config/`).

## Step 4 — Audit + fix custom PHP deprecations (ON D10) → sub-skill `php-deprecations-audit`

> 🌿 Branch: from `fix/<ticket>-cleanup-modules` → `fix/<ticket>-deprecations-custom`.

**Pivotal step — must be done BEFORE touching core.** Upgrade Status only
surfaces "removed in D11" APIs while the installed core is still D10.

**Invoke the `php-deprecations-audit` sub-skill.** It installs upgrade_status,
scans, applies rector + phpstan + manual fixes (incl. PHP 8.4 implicitly-nullable
params), and **loops the scan until 0 D11 errors**. Custom modules live under
`web/modules/custom`. Do not move to the next step before this reaches 0.

> Note: leave the audit `--dev` deps (`upgrade_status`, `drupal-rector`)
> installed for now — they are removed at the very end of the combined bump
> (step 6), not here. `upgrade_status` is also reused there to inventory
> contrib D11-readiness before the bump.

> ▸ **Close** (see MR protocol): commit `web/modules/custom` only — NOT
> `upgrade_status`/`drupal-rector`. Add `upgrade_status:analyze` output (0 D11
> errors) + `make phpstan` to "Verification".

## Step 5 — jQuery 4 theme migration (ON D10) → sub-skill `jquery-4-migration`

> 🌿 Branch: from `fix/<ticket>-deprecations-custom` → `fix/<ticket>-jquery4`.

Also do this while still on D10, to decouple bug sources. Code migrated to
native APIs stays fully functional under D10's jQuery 3.x + polyfill, so you can
migrate and test safely before the bump.

**Invoke the `jquery-4-migration` sub-skill.** It scans custom + third-party JS,
converts to native APIs, rebuilds (`make npm-build` + `make gulp-deploy`),
handles not-yet-compatible libraries with a scoped local polyfill, and removes
the legacy polyfill once usages are zero.

> ▸ **Close** (see MR protocol): commit migrated JS (`src/js`), built assets if
> versioned, cleaned `.libraries.yml`, the generated
> `jquery.deprecated.functions.js` (or the deleted legacy polyfill once usages
> are zero). Manual UAT (modals, sliders, AJAX) in "Verification".

## Step 6 — Contrib + Drupal 11 core bump (single Composer transaction) + apply

> 🌿 Branch: from `fix/<ticket>-jquery4` → `feat/<ticket>-core-d11`. Contrib
> readiness, the core bump, AND its application (updb/cim/build) all go into
> **one branch/MR** — they are inseparable (see "Why contrib and core are ONE
> step" in Operation order).

Only now, once custom code is fixed (step 4), JS migrated (step 5) and cleanup
done (step 3).

### Diagnose ALL blockers up front (avoid iteration)

Get the full picture **before** touching any constraint, so you bump everything
in one pass instead of discovering blockers one failed `composer update` at a
time:

```bash
# 1) Composer-level blockers: every installed package requiring core <= 10.
#    Use a CONCRETE D11 version (not a range) — it yields a clean, complete list
#    where the resolver error only ever names the first conflict.
make composer c='why-not drupal/core 11.4.4'

# 2) Contrib D11-readiness report (upgrade_status is still installed from step 4):
make drush c='upgrade_status:analyze --all'
#    or per module: make drush c='upgrade_status:analyze <module>'
```

Read the `drupal/<module> <ver> requires drupal/core (…)` lines from `why-not`:
any without `^11` is a blocker to bump; watch for **partial pins** like
`^11 <11.2` (e.g. gin/gin_toolbar) that need a newer release. `core-recommended`'s
own vendored deps (symfony, guzzle…) are noise — `--with-all-dependencies`
updates them. The `upgrade_status` report cross-checks which contrib has a D11
release vs still needs a patch/fork, so you decide bump-vs-remove-vs-patch for
every module in one go.

### Check the project's own autoloaded PHP

Beyond contrib, the project's OWN PHP that Composer autoloads (the `classmap` /
`files` in `composer.json` `autoload` — typically `scripts/composer/*.php`) can
reference APIs removed or dropped for D11 and **fatal the `post-install-cmd`**.
Common offenders seen on GM projects:

- `Webmozart\PathUtil\Path` (abandoned; may leave the dependency graph) →
  `Symfony\Component\Filesystem\Path`
- `DrupalFinder\DrupalFinder` + `->locateRoot()` → `DrupalFinderComposerRuntime`
- old settings rewriting → `Drupal\Core\Site\SettingsEditor`

Diff these files against a fresh `drupal-composer/drupal-project` D11 template and
port them; `php -l` each after editing.

### Handle removed-core modules & contrib with no D11 release

Check what is **enabled** first — only *enabled* removed-core modules orphan at
`updb` (`make drush c='pml --status=enabled'`).

| Module | In D11 | Action (only if relevant) |
|---|---|---|
| `ckeditor` (CKEditor 4) | replaced by `ckeditor5` in core | if a text format still uses CKE4: `make en ckeditor5` (before updb); then `make pmu ckeditor` + composer remove. Verify: `make drush c='config:get editor.editor.<format> editor'` → `ckeditor5` |
| `quickedit`, `rdf`, `tour`, `color` (core) | removed / moved to contrib | if enabled: `make pmu <m>`, or install the contrib version; else nothing to do |
| `contribute` | 5.x betas pin `drupal/core ~8.0` | `make pmu contribute` + composer remove |
| any contrib with **no D11 release** | — | if unused (e.g. an optimize backend with no pipeline configured): **uninstall + remove**; if needed: dev/beta branch → fork → alternative → custom patch (`cweagans/composer-patches`) |

> A high version number does not guarantee D11 support for beta/rc releases —
> always confirm against the `why-not` / `upgrade_status` output.

> ⚠️ **composer-patches gotchas** (when patching a module — e.g. a one-line PHP
> 8.4 nullable fix on a contrib with no fixed release):
> - `composer.patches.json` is only read if it is **wired** via
>   `extra.patches-file` (or patches are inline in `extra.patches`). A stray
>   `composer.patches.json` with no wiring is **silently ignored** — the patch
>   never applies. Check/add `"patches-file": "composer.patches.json"` in
>   `extra`, and drop obsolete patches (a stale D10 core patch will fail on D11
>   and abort the install with `composer-exit-on-patch-failure`).
> - Do **not** apply/re-apply a patch with `composer reinstall <pkg>`: with
>   patches it can delete the module dir and then fail ("Package is not
>   installed"), leaving it missing. Use `composer install` (it re-applies), or
>   `remove` + `require`.

### Bump everything in ONE `composer update`

```bash
# Let Composer resolve past the installed core's own security advisories
make composer c='config -- policy.advisories.block false'

# Core + scaffold + drush + the DEV core package.
# NOTE: core-dev ^10 ALSO pins core to 10 — bump it too or the resolve fails.
make composer c='require drupal/core-recommended:^11.0 drupal/core-composer-scaffold:^11.0 drupal/core-dev:^11 drush/drush:^13 --no-update'

# Every blocking contrib from the diagnose step, at its D11 release
# (major bump where the current major has no D11 release)
make composer c='require drupal/<mod_a>:^X drupal/<mod_b>:^Y … --no-update'

# Uninstall (on D10, so hook_uninstall runs) THEN drop the incompatible/unused ones
# NB: this cleans YOUR database only -- add an uninstall hook for each one
# (references/uninstall-update-hooks.md), or preprod/prod break on cim.
make drush c='pmu <removed_a> <removed_b> --yes'
make composer c='remove drupal/<removed_a> drupal/<removed_b> --no-update'

# Resolve the whole graph in one transaction
make composer c='update --with-all-dependencies'
```

> ⚠️ **allow-plugins**: core 11 pulls the `symfony/runtime` Composer plugin,
> blocked by default — the run aborts on it after resolving. Allow it, then
> finish the install:
> ```bash
> make composer c='config allow-plugins.symfony/runtime true'
> make composer c='install'
> ```

> If `composer update` still conflicts, its error names the next blocker — bump
> that constraint and re-run (rare when the diagnose step was thorough). For an
> orphaned sub-module or a `updb` schema gap, see
> **`references/contrib-and-cleanup.md`** (§ Orphaned modules, § Schema gaps).

### Purge the orphans the bump itself created

A contrib major that **drops a dependency** leaves modules installed with no code
— nobody removed them, Composer did. Real case: `module_filter` 4.1.1 required
`jquery_ui_autocomplete` (pulling `jquery_ui` + `jquery_ui_menu`) and its own
update installed it; `module_filter` 6.0.0 dropped the dependency, so all three
lost their code while staying in `core.extension`.

These are **not cosmetic**: one such orphan aborted core's own
`search_update_11402` (it installs `search_node`) and with it the entire `updatedb`
run. List them right after the bump, before running `updb`:

```bash
make composer c='install'   # code now matches composer.lock
make drush c='eval "print_r(array_values(array_diff(array_keys(\Drupal::config(\"core.extension\")->get(\"module\")), array_keys(\Drupal::service(\"extension.list.module\")->getList()))));"'
```

Everything that comes back needs a purge hook **and** a
`hook_update_dependencies()` entry ordering it before the core update that
installs a module — see **`references/uninstall-update-hooks.md`**
(§ Order the purge before core's own updates). Same file for a contrib that
declares `hook_update_last_removed()` above your schema while shipping no
`hook_update_N` (§ Don't blindly force a contrib schema number).

### Apply

> ⚠️ **Order matters**: after the Composer bump, code is D11 but the DB schema
> is still D10. `make cr` fails with a missing-column error. Run `make updb`
> **before** `make cr`.

```bash
# Maintenance mode
make drush c='state:set system.maintenance_mode 1 --input-format=integer'

# DB updates (BEFORE cr — schema is not yet D11)
make updb

# Cache rebuild (now that schema is up to date)
make cr

# Rebuild frontend
make npm-build
make gulp-deploy      # only if the theme build uses it

# Exit maintenance mode
make drush c='state:set system.maintenance_mode 0 --input-format=integer'
make cr
```

> **`make cim`?** Only if the project is **config-first** (a git-tracked
> `config/sync` is the source of truth). If config lives in the DB and
> `config_sync_directory` is just a backup, **skip `cim`** — it would re-import
> the pre-bump snapshot and revert `updb`'s config changes — and run `make cex`
> instead to refresh the backup to the new D11 state.

### Final cleanup

Remove the audit `--dev` dependencies that are no longer needed:

```bash
make pmu upgrade_status
make composer c='remove drupal/upgrade_status palantirnet/drupal-rector'
make cex
```

> ⚠️ If `make composer-remove` fails with "Removal failed, still present" for
> packages in `require-dev`, workaround: remove the entries directly in
> `composer.json`, then run `make composer c='update'`.

### Sync the exported config to the git-tracked directory

`make cex` exports to the path defined by `$settings['config_sync_directory']`
in `settings.php` / `settings.local.php`.

**Identify the real export path:**

```bash
# Option 1 — read settings.php directly on the host
grep "config_sync_directory" sites/default/settings.php sites/default/settings.local.php 2>/dev/null

# Option 2 — ask Drupal via drush
make drush c='eval "echo \Drupal\Core\Site\Settings::get(\"config_sync_directory\");"'
```

**If the export path differs from the git-tracked config dir**, ask the user for
the correct path, then rsync between the two locations.

### Verify

```bash
make drush c='status'                                  # must show Drupal 11.x
make drush c='core:requirements --severity=1'          # no ERRORS (warnings OK)
make drush c='cr'                                       # expect 0 deprecation warnings
make drush c='watchdog:show --count=50 --severity=3'    # severity NAME is localized — use the number (3 = Error)
make drush c='cron'
make translate
```

### Manual tests

- [ ] Homepage loads (`https://<project>.dev.localhost`) + each domain/theme level
- [ ] Admin login: `make uli uid=1` (note: a gin 4→5 bump is a major admin-theme change)
- [ ] Content creation/editing (CKEditor 5), forms, search
- [ ] Theme JS interactions (modals, sliders, AJAX) — jQuery-4 plugins work
      in-browser, 0 console errors
- [ ] Cron runs clean, logs are error-free
- [ ] CI pipeline green on the new PHP-8.4 image

> ▸ **Close** (see MR protocol): commit `composer.json` + `composer.lock`
> (+ `patches/` + `composer.patches.json` if a module was patched) + the
> uninstall/purge hooks for everything dropped or orphaned here + the
> regenerated D11 scaffold files + `config/` if git-tracked. Target
> `fix/<ticket>-jquery4`. "Verification" = `drush status` (11.x) +
> `core:requirements` + `cr` with 0 deprecations; "Manual UAT" = tests above.
> Stays **Draft** until the user validates UAT.

---

## Rollback

```bash
git checkout composer.json composer.lock config/
make composer c='install'
make db-import _dumps/<last-dump>.sql.gz
make cim
make cr
```

> Because each major step has its own branch/Draft MR, a rollback can also be
> targeted: simply don't merge (or close) the failing MR rather than reverting
> everything. Steps done on D10 (custom, jQuery) remain valid even if the
> combined bump (step 6) is postponed.

---

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `composer update` fails on platform | Container PHP < 8.4 | Step 2 — sub-skill `php-docker-upgrade` |
| `composer update` blocked on advisories | Installed core has security advisories | `composer config -- "policy.advisories.block" false` |
| `composer update` conflict, contrib requires core `^10` | A contrib (or `core-dev` ^10) still pins core to 10 | Bump every blocker found by `why-not drupal/core <v>` in the SAME transaction; don't forget `core-dev:^11` |
| `symfony/runtime … blocked by your allow-plugins config` | Core 11 pulls the `symfony/runtime` Composer plugin | `composer config allow-plugins.symfony/runtime true`, then `composer install` |
| `post-install-cmd` fatals (`Class … not found`, `Webmozart\PathUtil`) | Project's `scripts/composer/*.php` use APIs dropped for D11 | Update to `Symfony\…\Path` / `DrupalFinderComposerRuntime` / `SettingsEditor` — Step 6 "Check the project's own autoloaded PHP" |
| Patch in `composer.patches.json` silently not applied | File not wired | Add `extra.patches-file: composer.patches.json` (or inline `extra.patches`) |
| `composer reinstall <pkg>` deleted the module then failed | composer-patches + `reinstall` quirk | `composer install` to recover/re-apply; never `reinstall` a patched package |
| `make composer … --no-update` prints Make usage/errors | Make eats `--flags` as its own options | Pass flags inside `c='…'` |
| `Class not found` after upgrade | Cache stale | `make cr` |
| `make cr` fails after Composer bump | DB schema still D10, code already D11 | Run `make updb` first |
| `make cim` reverts D11 config / "empty import" | Config is DB-authoritative, `config/sync` is a stale/relocated backup | Skip `cim`, run `cex`; or read the real path from settings.php and rsync |
| DB schema errors | `updb` not run | `make updb` |
| Module auto-disabled | D11 incompatible | Find alternative / apply patch |
| JS broken (`$.trim`/`$.type is not a function`) | jQuery 4 removed the API | Step 5 — sub-skill `jquery-4-migration` (extend the scoped shim) |
| Theme broken | Classy/Stable base | Migrate to Starterkit |
| `deprecated function` PHP | Custom code not migrated | Step 4 — sub-skill `php-deprecations-audit` |
| Custom modules listed "D11.x incompatible" | `core_version_requirement` not updated | Step 3 — `sed` over all `.info.yml` files |
| `updb` reports orphan module (e.g. `tour`) | Module removed from core, still in `system.schema` | Purge — see `references/contrib-and-cleanup.md` § Orphaned modules |
| `updb` blocked on contrib schema gap (e.g. honeypot 8102→8104) | Intermediate hooks removed upstream | Replay the removed update, then set the schema — `references/uninstall-update-hooks.md` § Don't blindly force |
| Drush fails to start after a package update | Sub-module removed from package still in `core.extension` | Purge stale module — see `references/contrib-and-cleanup.md` § Orphaned modules |
| `cim` fails on preprod/prod for a module removed locally | Removal was never paired with an uninstall hook | `references/uninstall-update-hooks.md` — add the two-path hook |
| Uninstall hook "succeeded" but the module is still installed in prod | `ModuleInstaller::uninstall()` returns FALSE silently when the code is gone (it always is, on deploy) | Add the manual purge path — `references/uninstall-update-hooks.md` |
| A core update aborts with `The module <x> does not exist.` | An unrelated orphan blocks `ModuleInstaller::install()` | Purge the orphan + `hook_update_dependencies()` to order it first — `references/uninstall-update-hooks.md` |

---

## Reference files

- `references/contrib-and-cleanup.md` — module cleanup, orphaned modules, schema gaps (local, one-off fixes)
- `references/uninstall-update-hooks.md` — the deployable counterpart: update hooks that uninstall/purge removed modules before `cim` runs on preprod/prod

## Sub-skills (usable standalone too)

- `php-docker-upgrade` — PHP version bump in Docker (step 2)
- `php-deprecations-audit` — upgrade_status/rector/phpstan on custom code (step 4)
- `jquery-4-migration` — jQuery 3 → 4 theme migration (step 5)

## External resources

- Official guide: https://www.drupal.org/docs/upgrading-drupal/drupal-10-to-drupal-11
- Breaking changes: https://www.drupal.org/list-changes/drupal/published?to_branch=11.x
- Upgrade Status: https://www.drupal.org/project/upgrade_status
