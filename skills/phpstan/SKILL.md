---
name: phpstan
description: >
  Run the PHPStan pass of a PHP coding-standards campaign on a Dockerized,
  Makefile-driven project (Drupal or plain PHP): set up phpstan /
  phpstan-drupal and phpstan.neon at the chosen level (max by default, or a
  level the user picks), baseline grouped by error shape, Rector first for
  the inferable types, then one error shape at a time across the whole custom
  tree, each runtime-changing fix recorded as a manual UAT line; re-check
  phpcs and produce commit 3. Ends by proposing /clear then /php-standards for
  CI + MR. Use when the user asks for PHPStan / static analysis at a level,
  mentions "Cannot access offset on mixed", "no return type specified",
  phpstan.neon, Rector type fixes, or when the php-standards orchestrator
  routes here. Not the deprecation audit before a core bump
  (php-deprecations-audit). IMPORTANT: all commands MUST go through Makefile
  targets; no baseline file or ignore to make the count go down.
---

# PHPStan pass → commit 3

Part of the `php-standards` campaign; that skill owns the questions, the
state file, CI and the MR. This one writes commit 3. The details — setup,
`phpstan.neon` template, fix catalogue, Rector, phpcs conflicts — are in
`references/phpstan.md`; read only the section the current step names.

## Start

```bash
cat .git/php-standards.md 2>/dev/null
make phpcs c='--report=summary' | tail -3
```

- **phpcs not clean**: run the `phpcs` pass first. PHPStan fixes add
  docblocks and types that phpcs then re-checks; doing both at once mixes the
  commits.
- **The level**: `phpstan.neon` if it exists, else `phpstan:` in the notes
  file, else ask — `max` (the agency template, reachable on a small custom
  codebase) or a level (5–6 on a large legacy one). Standalone use without a
  notes file: ask the level and the ticket, create the file in the format of
  the `php-standards` skill.
- **`pass: phpstan` with uncommitted changes**: a previous conversation was
  cleared mid-pass. Keep the working tree and resume from the current
  baseline.
- Set `pass: phpstan`.

Everything goes through the Makefile, arguments through `c='…'`.

## Keep the context small

- Always `--error-format=raw --no-progress`, grouped by message (§4); never
  the default table output on the whole tree.
- **One error shape across all files at a time**, one re-run per shape.
- Rector writes the mechanical types; hand edits are for what it cannot do.
- If the context still grows large mid-pass, write the pending UAT lines to
  the notes file and propose `/clear` + `/php-standards`.

## 1. Setup (§1–3)

Dependencies (on Drupal, `drupal/core-dev` usually brings them), the
extension installer allowed in `composer.json`, `phpstan.neon` from the
template at the chosen level, the `make phpstan` target. Check for PHPStan-1
ignore patterns that silently match nothing under PHPStan 2.

## 2. Baseline (§4)

```bash
make phpstan c='--error-format=raw --no-progress' | sed 's/:.*:/ /' | sort | uniq -c | sort -rn | head
```

Write the total under `## Baseline` in the notes file.

## 3. Rector first (§5.1)

Dry-run, read the diff stat, apply, then `make phpcbf` (Rector prints code in
its own style), then re-run the baseline. It usually removes the bulk of the
"no return type" errors in one call. Rector skips `.install` files.

## 4. One error shape at a time (§5)

From the catalogue. Its **"Runtime change" column** decides whether a UAT
line is owed (`instanceof` / `is_array()` guards, arrays built locally, a
`count()` on config that may never have been saved). Append each UAT line to
the notes file **as soon as the fix is made**: file and change, exact path to
click, expected result with a number.

**`.install` / update hooks get `@var` only**: they run during the deploy, on
production.

## 5. phpcs again (§6)

PHPStan fixes add `use` lines, `@var` tags and `@param`s; DrupalPractice
forbids `@param` on hook implementations, so use inline `@var`. Both tools
must be clean on the same tree.

## 6. Verify (§7)

```bash
make phpstan c='--no-progress'          # [OK] No errors
make phpcs                              # No violations were found
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f" | grep -v '^No syntax errors'; done
exit
make cr
```

A `?Type` return on a function that can fall off its end is a `TypeError`
that `php -l` does not catch: the catalogue's `hook_help()` row. When guards
or types touched services, controllers or plugins, run the `php-standards`
skill's `references/verification.md`.

## 7. Commit 3

```bash
git add web/modules/custom web/themes/custom phpstan.neon rector.php composer.json composer.lock Makefile
git diff --cached --stat | tail -3
```

Message (repo format if it has one; keep the word `phpstan`), with the
pending UAT lines moved from the notes file into the body:

```
refactor(qa: #<ticket>): fix the phpstan errors at level <n>

phpstan: <before> -> 0 at level <n> (<after Rector> after Rector)
phpcs: still 0
Verified: php -l, make cr

UAT:
- foo/foo.module: count() on unsaved config guarded — fresh install, /admin/foo with no config saved → page renders, empty list
```

A late fix to an earlier QA commit goes into it: `git commit --fixup=<sha>`
then `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <sha>~1`.

## End: propose `/clear`

Update the notes file (`pass: none`, UAT section emptied, phpstan baseline
kept), then stop and print:

```
phpstan pass done — commit <sha>: <before> -> 0 at level <n>, <k> UAT lines recorded in the commit body.
Next: CI jobs (if asked) and the Draft MR. Run /clear, then /php-standards.
```

Continue in this conversation only if the user declines the clear.

## Non-goals

- Do not lower the level, generate a `phpstan-baseline.neon`, add an
  `ignoreErrors` entry beyond the template's or a `@phpstan-ignore` for
  custom-code errors, or "repair" dead ignore patterns to make a count go
  down, unless the user asks.
- No guard or restructuring in `.install` / update hooks.
- Do not mix in a functional change that no error asked for.
