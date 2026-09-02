# Deployable uninstall hooks for removed modules

**Rule: every module or theme removed from `composer.json` during the campaign
MUST get an update hook that uninstalls it.** Removing the code is only half the
job — without the hook, the change works locally (where you ran `make pmu`
before removing) and breaks on preprod/prod.

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

## Where the hooks live

In a project-owned custom module that is **installed on every environment** —
typically the global-config module (`<project>_global_config`), the one that
already carries the site's cross-cutting config. Use its `.install` file, and
number the hooks in a range that cannot collide with the module's real schema
(the projects here use `_update_100NN`).

Never put these hooks in the module being removed — its code is gone by then.

## The two traps that make the naive pattern useless

### Trap 1 — the code is already gone when the hook runs

Check the deploy sequence (`deploy.php`, task `drush:update` on GM projects). It
is:

```
composer install  →  cr  →  updatedb  →  config-import
```

`composer install` runs **first**. So by the time your hook executes during
`updatedb`, the module's code has already been deleted from disk. Locally the
opposite is true (you still have the code when you write and test the hook), which
is exactly why this bug ships unnoticed.

### Trap 2 — `ModuleInstaller::uninstall()` fails silently

When the extension is not on disk, `ModuleInstaller::uninstall()` does
`return FALSE` **without throwing and without logging**. The obvious
`moduleExists()` + `uninstall()` hook therefore does *nothing at all* in
production, reports success, and the config import breaks two steps later.

So the hook needs **two paths**: a proper uninstall when the code is present, and
a manual registry purge when it is not.

## Template — a two-path uninstall hook

```php
/**
 * Uninstalls the modules dropped during the Drupal 11 upgrade (Mantis #<ticket>).
 */
function <project>_global_config_update_10001(): void {
  // These modules were removed from composer.json, so their code no longer
  // exists on disk. On environments where they are still installed (preprod,
  // prod), Drupal keeps them listed in core.extension and system.schema while
  // being unable to load them, which breaks the configuration import.
  //
  // This hook runs during `drush updatedb`, i.e. BEFORE `drush config-import`
  // in the deploy sequence, so the modules are gone before the configuration
  // that no longer references them lands.
  $removed_modules = [
    'module_a',
    'module_b',
  ];

  $extension_config = \Drupal::configFactory()->getEditable('core.extension');
  $installed = $extension_config->get('module') ?? [];
  // Modules whose code is still discoverable on disk.
  $on_disk = \Drupal::service('extension.list.module')->getList();

  $to_uninstall = [];
  $to_purge = [];
  foreach ($removed_modules as $module) {
    // Not installed on this environment: nothing to do. Keeps the hook
    // idempotent and safe on local, where they were already uninstalled.
    if (!isset($installed[$module])) {
      continue;
    }
    if (isset($on_disk[$module])) {
      $to_uninstall[] = $module;
    }
    else {
      $to_purge[] = $module;
    }
  }

  // Preferred path: the code is still present, so uninstall properly and let
  // each module run its own hook_uninstall() and clean up its config.
  if ($to_uninstall) {
    \Drupal::service('module_installer')->uninstall($to_uninstall);
  }

  // Fallback path: the module is installed but its code is already gone, which
  // is what happens on a real deploy because `composer install` runs before
  // `updatedb`.
  if ($to_purge) {
    _<project>_global_config_purge_orphan_modules($to_purge);
  }
}
```

Notes that matter:

- **Order dependents first.** List a submodule before the module it depends on
  (`imageapi_optimize_resmushit` before `imageapi_optimize`).
- **Idempotent by construction.** The `isset($installed[$module])` guard makes the
  hook a no-op on environments where the module was already uninstalled — so the
  same hook is safe on local, preprod and prod.
- **One hook per logical batch**, with a docblock naming *why* those modules went
  away. Do not retro-edit a hook that has already run somewhere.

## Template — the reusable purge helper

Write this **once** per project and call it from every hook. Both the
"module removed from composer" and the "orphan left behind by a contrib bump"
cases use it.

```php
/**
 * Purges modules that are still installed but whose code is gone from disk.
 *
 * Drupal keeps such a module in core.extension and system.schema while being
 * unable to load it. That state makes ModuleInstaller refuse to install OR
 * uninstall anything at all ("The module <name> does not exist"), which blocks
 * both the configuration import and any later database update.
 *
 * hook_uninstall() cannot run, since there is no code left to run it. Only use
 * this for modules that own no database table.
 *
 * @param string[] $modules
 *   Machine names of the modules to purge.
 */
function _<project>_global_config_purge_orphan_modules(array $modules): void {
  $extension_config = \Drupal::configFactory()->getEditable('core.extension');
  $schema_store = \Drupal::keyValue('system.schema');
  $config_factory = \Drupal::configFactory();

  foreach ($modules as $module) {
    // Drop every config object owned by the module.
    foreach ($config_factory->listAll($module . '.') as $config_name) {
      $config_factory->getEditable($config_name)->delete();
    }
    $schema_store->delete($module);
    $extension_config->clear('module.' . $module);
  }
  $extension_config->save();

  // Forget the modules' post-update functions so Drupal does not try to
  // resolve them from code that no longer exists.
  $post_update_store = \Drupal::keyValue('post_update');
  $existing = $post_update_store->get('existing_updates', []);
  $remaining = array_values(array_filter(
    $existing,
    function (string $function) use ($modules): bool {
      foreach ($modules as $module) {
        if (str_starts_with($function, $module . '_post_update_')) {
          return FALSE;
        }
      }
      return TRUE;
    }
  ));
  if ($remaining !== $existing) {
    $post_update_store->set('existing_updates', $remaining);
  }
}
```

The four things that must be cleaned — miss one and the symptom comes back later:

| What | Where | If skipped |
|---|---|---|
| Registration | `core.extension` → `module.<name>` | `cim` and every module install fail |
| Schema version | `system.schema` key-value | "missing from your site" on `updb`, drush may not boot |
| Owned config | every object matching `listAll('<name>.')` | orphan config objects, `cim` diff noise |
| Post-updates | `post_update` key-value → `existing_updates` | Drupal resolves `<name>_post_update_*` from missing code |

> ⚠️ **The purge path cannot run `hook_uninstall()`.** Anything the module would
> have cleaned up itself is left behind — most importantly its **database
> tables**. Only purge modules that own no table (config-only modules, which is
> the common case for the ones dropped in a D11 campaign). If a removed module
> *does* own tables, either drop them explicitly in the hook, or split the change
> across two deploys: deploy 1 keeps the code in `composer.json` and only
> uninstalls it via a plain `module_installer->uninstall()` hook, deploy 2 removes
> the code.

## Themes are different (and easier)

`ThemeInstaller::uninstall()` works fine with the code already gone — it only
logs `missing from the file system` and proceeds. So a theme needs **no manual
purge**, just a guarded call:

```php
/**
 * Switches the admin theme from <old> to <new> (Mantis #<ticket>).
 */
function <project>_global_config_update_10002(): void {
  $theme_installer = \Drupal::service('theme_installer');
  $installed = \Drupal::config('core.extension')->get('theme') ?? [];

  // Install the replacement here rather than leaving it to the config import,
  // so it is already present when a module whose install requirements demand it
  // arrives (e.g. gin_toolbar requires the gin theme).
  if (!isset($installed['<new_theme>'])) {
    $theme_installer->install(['<new_theme>']);
  }

  $removed_themes = ['<old_theme>'];
  $to_uninstall = array_values(array_filter(
    $removed_themes,
    fn (string $theme): bool => isset($installed[$theme])
  ));

  if ($to_uninstall) {
    $theme_installer->uninstall($to_uninstall);
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
  $dependencies = [];

  // search_update_11402() installs the search_node module, and it is the only
  // pending update that installs one. A single module still registered in
  // core.extension but missing from disk aborts it with
  // "The module <name> does not exist.".
  //
  // Depending on the LAST purging update is enough, since a module's own
  // updates always run in ascending order. Keep this number in sync when a new
  // orphan-purging update is added, or that update will run after
  // search_update_11402 and the abort comes back.
  $dependencies['search'][11402] = ['<project>_global_config' => 10006];

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
installed schema while shipping no `hook_update_N` at all (real case:
`module_filter` 6.0.0 declares `9404`, site sits at `9403`, no hooks). Drupal then
refuses to update the module and reports a permanent
`the installed version is too old` requirements error.

Setting `system.schema` to the expected number makes the error go away but
**skips whatever the removed update did**. Instead:

1. Download the last release that still had the update.
2. Read the removed `hook_update_N` body.
3. Replay exactly that in your own hook, then set the schema number.

```php
/**
 * Closes the <module> schema gap introduced by the <old> to <new> bump.
 */
function <project>_global_config_update_10004(): void {
  // <module> <new> declares hook_update_last_removed() = 9404 but ships no
  // hook_update_N, while this site sits at schema 9403. Rather than blindly
  // forcing the number, this replays exactly what the removed update did: read
  // from <module> 5.0.5, <module>_update_9404() set
  // <module>.settings:descriptions_show to FALSE, and nothing else.
  $schema_store = \Drupal::keyValue('system.schema');
  $installed_schema = $schema_store->get('<module>');

  if ($installed_schema === NULL || $installed_schema >= 9404) {
    // Not installed here, or already up to date.
    return;
  }

  \Drupal::configFactory()
    ->getEditable('<module>.settings')
    ->set('descriptions_show', FALSE)
    ->save();

  $schema_store->set('<module>', 9404);
}
```

> Skip any removed update whose effect you are deliberately undoing elsewhere —
> e.g. an update that *installed* a module you are purging in the same run.

## Verify before committing

Local `updb` proves almost nothing here, because locally the code is still on
disk and only the *preferred* path runs. To exercise the purge path:

```bash
# 1) Snapshot, so you can replay the hook as many times as needed.
make db-export

# 2) Reproduce the deploy state: DB from before the removal, code from after.
make db-import _dumps/<pre-removal-dump>.sql.gz

# 3) Confirm the orphans are really orphans (installed, not on disk).
#    One line only: make runs each recipe line in its own sh, so a wrapped
#    c='eval "..."' is truncated at the newline and fails on unexpected EOF.
make drush c='eval "print_r(array_values(array_diff(array_keys(\Drupal::config(\"core.extension\")->get(\"module\")), array_keys(\Drupal::service(\"extension.list.module\")->getList()))));"'

# 4) Run the real deploy order.
make updb
make cim
make cr
```

Checklist for the MR:

- [ ] Every module removed from `composer.json` in the diff appears in a hook.
- [ ] Dependents listed before their dependencies.
- [ ] Each purged module owns no database table (or its tables are handled).
- [ ] `hook_update_dependencies()` points at the **last** purging hook.
- [ ] `updb` then `cim` run clean on a pre-removal database dump.
- [ ] The orphan diff above returns an empty array afterwards.
