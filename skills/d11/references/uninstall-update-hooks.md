# Deployable uninstall hooks for removed modules

**Rule: every module or theme removed from `composer.json` that is still
installed on preprod or prod MUST get an update hook that removes it.**
Removing the code is only half the job — without the hook, the change works
locally (where you ran `make pmu` before removing) and breaks on preprod/prod.

`references/contrib-and-cleanup.md` covers the *local, one-off* `drush eval`
purge. This file covers the *deployable* counterpart: what has to be committed so
the other environments converge on their own.

## Why it is required

`composer remove` deletes the **code**. It does not touch the **database**.
Preprod and prod still list the module in `core.extension` and `system.schema`
while being unable to load it. That state breaks the deploy in two ways:

1. **`cim` fails.** The exported `core.extension` no longer lists the module, so
   the config importer tries to uninstall it — and cannot, since there is no code
   to uninstall.
2. **A single orphan blocks *every* module install.** `ModuleInstaller::install()`
   rebuilds the module filename list from `core.extension` and calls `getPath()`
   on every entry it cannot resolve, so it throws
   `The module <name> does not exist.` This aborts unrelated work, including
   **core's own update hooks** (a real case: `search_update_11402`, which installs
   `search_node`, aborted the whole `updatedb` run because of an unrelated
   orphan).

## Step 1 — decide which modules need a hook at all

**No hook for a module no environment has installed.** If the module is absent
from `config/sync/core.extension.yml` *on the integration branch* and `cim` runs
on every deploy, the config import already keeps it uninstalled everywhere: a
hook would have nothing to catch and only adds an untested destructive path.
A reviewer will (rightly) ask for it to be deleted.

```bash
# Installed according to the config the environments import:
git show <integration-branch>:config/sync/core.extension.yml | grep -nE '^  (<module_a>|<module_b>):'
# Confirm on preprod and prod (read-only):
drush pml --status=enabled --type=module
```

Only the modules that come back here get a hook. Typical survivors in a D11
campaign: the contribs with **no D11 release** that were installed and used
(AdvAgg, Maintenance 200…), and the orphans the bump itself creates
(§ Order the purge before core's own updates).

## Step 2 — prefer two deploys when the code can stay

If the module still has a release compatible with the **current** core, do not
purge anything: split the removal across two deploys.

1. **Deploy 1** — keep the code in `composer.json`, ship an uninstall hook.
   `hook_uninstall()` runs and the module cleans up its own tables and config.
2. **Deploy 2** — remove it from `composer.json`.

```php
/**
 * Uninstalls <module_a> and <module_b>, unused since <reason> (#<ticket>).
 */
function <project>_global_config_update_10001(): void {
  $modules = ['<module_a_submodule>', '<module_a>', '<module_b>'];
  $installed = \Drupal::config('core.extension')->get('module');
  $modules = array_values(array_filter($modules, fn (string $module): bool => isset($installed[$module])));

  // FALSE: never uninstall a module we keep just because it depends on one of
  // these; fail loudly instead.
  if ($modules && !\Drupal::service('module_installer')->uninstall($modules, FALSE)) {
    throw new \RuntimeException('Failed to uninstall: ' . implode(', ', $modules));
  }
}
```

- **`$uninstall_dependents = FALSE`** and a checked return value: the default
  `TRUE` silently uninstalls every kept module that depends on one of these, and
  `uninstall()` returns `FALSE` without throwing.
- **List exact machine names**, sub-modules before their parent. Never match by
  prefix (`<project>_`): `orphans_media_` also matches the custom
  `orphans_media_gm`, `ckeditor_` matches `ckeditor5_*`.

## Step 3 — the purge, when the code cannot stay

A module with **no release for the new core** has to leave in the same deploy
as the core bump. On deploy its code is gone before `updatedb` runs, and
`ModuleInstaller::uninstall()` cannot help:

- the deploy order is `composer install` → `updatedb` → `config-import`, so the
  code is already deleted when the hook runs (locally it is still there, which
  is why this ships unnoticed);
- with the code missing, `ModuleInstaller::uninstall()` does `return FALSE`
  **without throwing and without logging**.

So the hook removes the module from the registry by hand. **Write it for those
exact modules, with every leftover named explicitly** — no generic
`listAll('<module>.')` helper: it misses config owned by *another* module that
depends on the removed one, and deletes things nobody reviewed.

Build the lists from the pre-removal state:

```bash
# Config objects the MR deletes from config/sync (the module's own AND the
# config of other modules that depends on it):
git diff --name-status <integration-branch>...HEAD -- config/ | grep '^D'
# Cross-check dependents on the integration branch:
git grep -lE '^\s+- <module>$' <integration-branch> -- config/sync
# Tables: hook_schema() tables, plus cache bins created on the fly.
make drush c='sqlq "SHOW TABLES LIKE \"%<module>%\""'
```

If a dependent is a **field storage, a display or a view** (the module provides
a field type, widget or formatter), stop: the purge cannot fix those entities.
Keep the code for one more deploy (Step 2) or migrate the fields first.

```php
/**
 * Removes <module_a> and <module_b>, which have no D11 release (#<ticket>).
 */
function <project>_global_config_update_10002(): void {
  // Their code is removed with the core bump, so composer install deletes it
  // before updatedb: ModuleInstaller::uninstall() cannot run without it.
  // Neither declares a schema: only their config, their entries in
  // core.extension and system.schema, and the <module_a> cache bin are left.
  $modules = ['<module_a>', '<module_b>'];
  $configs = [
    '<module_a>.settings',
    '<module_b>.settings',
    'ultimate_cron.job.<module_a>_cron',
  ];

  $config_factory = \Drupal::configFactory();
  foreach ($configs as $config_name) {
    $config_factory->getEditable($config_name)->delete();
  }

  $extension_config = $config_factory->getEditable('core.extension');
  foreach ($modules as $module) {
    $extension_config->clear('module.' . $module);
    \Drupal::keyValue('system.schema')->delete($module);
  }
  $extension_config->save();

  \Drupal::database()->schema()->dropTable('cache_<module_a>');
}
```

What must be cleaned, and what need not be:

| What | Where | If skipped |
|---|---|---|
| Registration | `core.extension` → `module.<name>` | `cim` and every module install fail |
| Schema version | `system.schema` key-value | "missing from your site" on `updb`, drush may not boot |
| Config | the explicit list above, dependents included | orphan config, `PluginNotFoundException` for dependents |
| Tables | `hook_schema()` tables + `cache_<bin>` | orphan tables |
| Post-updates | `post_update` → `existing_updates` | nothing: extra entries are ignored, leave them |

Each operation is idempotent (deleting a missing config, key or table is a
no-op), so the hook needs no "already done" guard and no uninstall branch for
local, where `make pmu` already ran.

## Where the hooks live

In a project-owned custom module that is **installed on every environment** —
typically the global-config module (`<project>_global_config`), the one that
already carries the site's cross-cutting config. Use its `.install` file, and
number the hooks in a range that cannot collide with the module's real schema
(the projects here use `_update_100NN`). Never put them in the module being
removed, nor in an unrelated feature module.

**One hook per logical batch**, with a docblock naming *why* those modules went
away. Do not retro-edit a hook that has already run somewhere. Deleting a hook
that never ran anywhere is fine, and the remaining numbers need not be shifted.

## Themes are different (and easier)

`ThemeInstaller::uninstall()` works fine with the code already gone — it only
logs `missing from the file system` and proceeds. So a theme needs **no manual
purge**, just a guarded call:

```php
/**
 * Switches the admin theme from <old> to <new> (Mantis #<ticket>).
 */
function <project>_global_config_update_10003(): void {
  $theme_installer = \Drupal::service('theme_installer');
  $installed = \Drupal::config('core.extension')->get('theme') ?? [];

  // Install the replacement here rather than leaving it to the config import,
  // so it is already present when a module whose install requirements demand it
  // arrives (e.g. gin_toolbar requires the gin theme).
  if (!isset($installed['<new_theme>'])) {
    $theme_installer->install(['<new_theme>']);
  }
  if (isset($installed['<old_theme>'])) {
    $theme_installer->uninstall(['<old_theme>']);
  }
}
```

> Removing a base theme also drops whatever *it* depended on. Uninstall those too
> (dropping `adminimal_theme` also orphaned `seven`, still installed though
> unused).

## Order the purge before core's own updates

An orphan blocks `ModuleInstaller::install()`, so it can abort a **core** update
hook that installs a module. Module weight is not a reliable ordering; state the
dependency explicitly:

```php
/**
 * Implements hook_update_dependencies().
 */
function <project>_global_config_update_dependencies(): array {
  // search_update_11402() installs search_node: a module still registered in
  // core.extension but missing from disk aborts it with "The module <name>
  // does not exist.". Depend on the LAST purging update.
  $dependencies['search'][11402] = ['<project>_global_config' => 10002];
  return $dependencies;
}
```

Find which pending core update installs a module before assuming the number:

```bash
make drush c='updatedb:status'
grep -rn "moduleInstaller\|module_installer" web/core/modules/*/*.install \
  web/core/modules/*/*.post_update.php
```

## Don't blindly force a contrib schema number

A contrib major can declare `hook_update_last_removed()` **above** the site's
installed schema while shipping no `hook_update_N` at all (real cases:
`module_filter` 6.0.0 declares `9404`, site at `9403`; Honeypot 2.2 declares
`8104`, site at `8102`). Drupal then refuses to update the module and reports a
permanent `the installed version is too old` requirements error.

Setting `system.schema` to the expected number makes the error go away but
**skips whatever the removed update did**. Instead:

1. Download the last release that still had the update.
2. Read the removed `hook_update_N` bodies.
3. Replay exactly that in your own hook, then set the schema number. Leave out
   what cannot apply on this site (e.g. a Tour cache clear when Tour is not
   installed) and say so in the comment rather than guarding it in code.

```php
/**
 * Closes the Honeypot schema gap (8102 to 8104) (#<ticket>).
 */
function <project>_global_config_update_10004(): void {
  // Honeypot 2.2 declares hook_update_last_removed() = 8104 but ships no
  // hook_update_N, while this site sits at 8102. Replay what the removed
  // updates did, read from Honeypot 2.1.4: honeypot_update_8103() added the
  // hostname index on {honeypot_user}; honeypot_update_8104() only cleared the
  // Tour tip cache, and Tour is not installed here.
  $schema_store = \Drupal::keyValue('system.schema');
  if ($schema_store->get('honeypot') >= 8104) {
    return;
  }

  $database_schema = \Drupal::database()->schema();
  if (!$database_schema->indexExists('honeypot_user', 'hostname')) {
    \Drupal::moduleHandler()->loadInclude('honeypot', 'install');
    $database_schema->addIndex('honeypot_user', 'hostname', ['hostname'], honeypot_schema()['honeypot_user']);
  }

  $schema_store->set('honeypot', 8104);
}
```

## Verify before committing

`updb` on your current local database proves nothing: it was already cleaned by
`make pmu` or by an earlier run. Replay the deploy on a database from **before**
the removal, with the code from **after**:

```bash
# 1) Snapshot the current database.
make db-export

# 2) Pick the pre-removal dump: the one still holding the removed modules.
for f in _dumps/*.sql.gz; do echo "$f $(gzcat "$f" | grep -c "'<module_a>.settings'")"; done

# 3) Import it. Under the new core, `make db-import` can die in its `sql-drop`
#    bootstrap (e.g. "Unknown column 'alias'" on the router table); the dump
#    carries its own DROP TABLE statements, so pipe it in directly.
gunzip -c _dumps/<pre-removal-dump>.sql.gz \
  | docker compose <compose-args> exec -T --user www-data php vendor/bin/drush sql-cli

# 4) Check the starting state. `drush sqlq` does not apply the table prefix:
#    SHOW TABLES LIKE "%key_value" gives the real name.
make drush c='sqlq "SELECT name, CAST(value AS CHAR) FROM <prefix>key_value WHERE collection=\"system.schema\" AND name IN (\"<module_a>\",\"<module_b>\")"'

# 5) Run the real deploy order.
make deploy-local   # or: make updb, make cim, make updb, make cr
```

Then check, on that replayed database:

- the hooks appear in the `updb` output, and `system.schema` holds the new
  number for the hooks' module;
- the listed config, the `core.extension` entries and the tables are gone;
- `drush cst` reports no difference and the second `updb` has nothing pending;
- `drush core:requirements --severity=2` shows nothing the hooks caused;
- the orphan diff returns an empty array (one line only: make runs each recipe
  line in its own sh, so a wrapped `c='eval "..."'` fails on unexpected EOF):

```bash
make drush c='eval "print_r(array_values(array_diff(array_keys(\Drupal::config(\"core.extension\")->get(\"module\")), array_keys(\Drupal::service(\"extension.list.module\")->getList()))));"'
```

Checklist for the MR:

- [ ] Each hooked module is in the integration branch's `core.extension.yml`
      (or confirmed enabled on preprod/prod); the others have no hook.
- [ ] Modules with a release for the current core go through two deploys
      (`uninstall($modules, FALSE)`, return checked), not a purge.
- [ ] Purge hooks name every module, config object (dependents included) and
      table explicitly; no prefix matching, no generic helper.
- [ ] No field storage, display or view depends on a purged module.
- [ ] `hook_update_dependencies()` points at the **last** purging hook, if a
      pending core update installs a module.
- [ ] The deploy order replayed clean on a pre-removal database dump.
