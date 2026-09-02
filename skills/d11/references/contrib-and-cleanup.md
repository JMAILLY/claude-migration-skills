# D11 upgrade: module cleanup & contrib/bump troubleshooting

Orchestration details that stay with the `d11` skill (they are specific to the
D10 → D11 campaign, not to a reusable audit). Deprecation auditing itself lives
in the `php-deprecations-audit` skill.

> **Scope.** Everything below is a **local, one-off** fix you run by hand to
> unblock your own environment. None of it reaches preprod or prod. For each
> module you remove or purge here, the deploy also needs a committed **update
> hook** — see **`uninstall-update-hooks.md`**.

## Unused modules & themes to remove (step 3, on D10)

Clean up BEFORE the upgrade — less code to migrate:

```bash
# Enabled non-core modules
make drush c='pml --type=module --status=enabled --no-core'

# Installed but disabled modules (removal candidates)
make drush c='pml --type=module --status=disabled'

# Themes
make drush c='pml --type=theme'
```

For each unused module:

```bash
make pmu <module>                    # uninstall cleanly (DB)
make composer-remove drupal/<module> # remove code
```

For an unused theme: uninstall via the UI or
`make drush c='theme:uninstall <theme>'`, then remove its files.

Always run `make cex` afterwards to lock the state in config, then commit.

> ⚠️ `make pmu` cleans **your** database only. Every module removed from
> `composer.json` also needs an uninstall hook so preprod/prod converge — see
> **`uninstall-update-hooks.md`**.

## Orphaned modules in `core.extension` after a package update

When a contrib package **removes a sub-module between releases** (e.g. `webform`
dropping `webform_location_geocomplete` in 6.3.x), the module stays declared in
`core.extension` and `system.schema`. Drush fails to start.

**Symptom:**

```
The following module is missing from the file system: webform_location_geocomplete
```

**Diagnose** — modules in DB with no file on disk:

```bash
make drush c='eval "print_r(array_diff(array_keys(\Drupal::keyValue(\"system.schema\")->getAll()), array_keys(\Drupal::moduleHandler()->getModuleList())));"'

> ⚠️ Keep it on **one line**. Make runs each recipe line in a separate
> `/bin/sh -c`, so a multi-line `c='eval "…"'` is truncated at the first newline
> and dies with ``unexpected EOF while looking for matching `"'``.
```

**Fix** (replace `<module>`):

```bash
make drush c='eval "\$ext = \Drupal::configFactory()->getEditable(\"core.extension\"); \$ext->clear(\"module.<module>\")->save(); \Drupal::keyValue(\"system.schema\")->delete(\"<module>\"); echo \"<module> purged\n\";"'
```

Then `make cr` and confirm Drupal boots cleanly.

> This `eval` is the throwaway version of the purge. The deployable one — which
> also clears the module's config objects and its `post_update` entries, and
> orders itself before core's updates — is in **`uninstall-update-hooks.md`**.

## Schema gaps in contrib modules (`updb` blocked)

When intermediate update hooks were **removed upstream** between two releases
(e.g. honeypot: DB at 8102, module ships at 8104 without hooks 8103/8104),
`make updb` fails or blocks on a missing update.

**Symptom:**

```
Module honeypot has an entry in the system.schema key/value storage, but is missing from your site.
```

or `updb` reporting a version gap with no available hook.

**Identify the target version:**

```bash
# Current DB version
make drush c='eval "echo \Drupal::keyValue(\"system.schema\")->get(\"<module>\");"'

# Version expected by the module (.install file)
grep "function <module>_update_" web/modules/contrib/<module>/<module>.install | tail -5
```

**Force the schema version** (replace `<module>` and `<version>`):

```bash
make drush c='eval "\Drupal::keyValue(\"system.schema\")->set(\"<module>\", <version>);"'
make updb
```

> ⚠️ Only force if the intermediate hooks were genuinely removed upstream (verify
> in the module's `.install`) and the gap is a version-only jump with no actual
> missing data migration. When in doubt, check the module's changelog.

> ⚠️ **Forcing skips whatever the removed update did.** If it did something real
> (`module_filter_update_9404()` set `module_filter.settings:descriptions_show`
> to FALSE), download the last release that still shipped the hook, read its
> body, and **replay it** before setting the number — in a committed update hook,
> not an `eval`, since preprod and prod have the same gap. See
> **`uninstall-update-hooks.md`** § Don't blindly force a contrib schema number.
