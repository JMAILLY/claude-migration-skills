---
name: phpcs-standards
description: >
  Set up or verify PHP_CodeSniffer and PHPStan on a Dockerized, Makefile-driven
  PHP project (Drupal or PSR-12), bring the custom code to zero violations, and
  optionally add the phpcs/phpstan GitLab CI jobs with their SonarQube report
  converters. Use when the user mentions phpcs, phpcbf, phpstan, coding
  standards, "normes de codage", static analysis, drupal/coder,
  DrupalPractice, PSR-12, a sniff, a ruleset / phpcs.xml / phpstan.neon,
  "FAILED TO FIX", "Cannot access offset on mixed", phpcs/phpstan pipelines,
  sonar-project.properties, or wants the custom modules cleaned up before a
  review or a major upgrade. Asks which standard (Drupal vs PSR-12), which
  severity (errors only vs errors + warnings), which PHPStan level, and
  whether to add CI jobs (which branches, report-only vs gating). Fixes module
  by module and records every behaviour-changing fix as a manual UAT step in
  the merge request. IMPORTANT: all commands MUST go through Makefile targets;
  phpcbf can discard every fix for a file silently, so a run is only clean
  when phpcs prints "No violations were found"; the CI jobs need
  require-dev, so check whether the CI vendor/ ships before touching the
  composer job's --no-dev.
---

# PHP_CodeSniffer + PHPStan: set up, clear the custom code, wire the CI

Four jobs in one skill. Each one can be asked for on its own:

1. **Set up / verify** the toolchain (dependencies, `phpcs.xml`,
   `phpstan.neon`, Makefile targets) so `make phpcs`, `make phpcbf` and
   `make phpstan` are trustworthy.
2. **Clear the phpcs violations** module by module, without breaking the site.
3. **Clear the PHPStan errors** at the chosen level (`references/phpstan.md`).
4. **Add the CI jobs**: phpcs and phpstan in GitLab CI, with SonarQube report
   converters and the deploy adjustments they need
   (`references/ci-pipelines.md`).

> ⚠️ **This is not a cosmetic-only task.** On a real Drupal codebase, the
> `DrupalPractice` sniffs force dependency injection, method renames and
> `t()` routing — changes that *can* break behaviour. Those are applied, but
> **isolated in their own commit and paired with a mandatory manual UAT entry**
> in the MR. See `references/risky-sniffs-uat.md`.

## Golden rule: everything goes through the Makefile

Never run `phpcs`, `phpcbf`, `phpstan`, `composer` or `drush` on the host.

| Need | Make target |
|---|---|
| Check standards | `make phpcs c='<args>'` |
| Autofix | `make phpcbf c='<args>'` |
| Static analysis | `make phpstan c='<args>'` |
| Add a dev dependency | `make composer-require <pkg> --dev` |
| Generic Drush command | `make drush c='<cmd>'` |
| Clear caches | `make cr` |
| Shell in the PHP container | `make shell` |

Many Makefiles end with a catch-all (`%:` / `@:`) that **swallows positional
arguments**. So always pass phpcs arguments through a variable — `make phpcs
c='web/modules/custom/foo'` — never `make phpcs web/modules/custom/foo`.
Check which variable the existing targets read: if they take `ARGS=`, then
`c='…'` is silently dropped and the run covers the whole tree.

## Step 0 — Ask before running anything

Ask these together, in one message, and remember the answers for the session:

1. **Which standard?**
   - `Drupal` + `DrupalPractice` (needs `drupal/coder`) — the full Drupal set;
     `DrupalPractice` is the one that surfaces the risky, behaviour-touching
     findings.
   - `Drupal` only — style and comments, no practice sniffs.
   - `PSR-12` — non-Drupal projects, or a deliberately lighter bar.
2. **Which severity?**
   - **Errors only** (`-n`) — the usual first pass, and the usual CI gate.
   - **Errors + warnings** — the complete pass. Say plainly that warnings on a
     Drupal codebase are dominated by `DrupalPractice` and therefore carry most
     of the UAT risk.
3. **PHPStan too, and at which level?** `max` is the agency template and is
   reachable on a small custom codebase; propose 5–6 on a large legacy one
   (`references/phpstan.md` §2).
4. **CI jobs?** If yes: which branches (usually the deploy branches only), and
   report-only (`|| true`, the agency template) or gating. SonarQube scanner
   now or later (`references/ci-pipelines.md` §0).
5. **Ticket id** (Mantis/Jira), if the work is to be committed — needed for the
   commit messages and the MR.

Skip the questions the user already answered in the request ("fix the errors
and warnings" answers the severity), or that an existing `phpcs.xml` /
`phpstan.neon` already settles, and say which ones you took as settled. Do not
guess the rest. The severity choice changes every command below:
append `-n` to every `phpcs`/`phpcbf` invocation when the answer is errors only.

## Step 1 — Set up or verify the toolchain

Check each item; create only what is missing. Report what already existed.

### 1.1 Dependencies

```bash
# Drupal standards (pulls squizlabs/php_codesniffer + slevomat)
make composer-require drupal/coder --dev
# PSR-12 only
make composer-require squizlabs/php_codesniffer --dev
```

`composer.json` must allow the installer plugin, or the standards register
nowhere and `phpcs -i` will not list them:

```json
"config": { "allow-plugins": { "dealerdirect/phpcodesniffer-composer-installer": true } }
```

Verify inside the container — this is the only proof the standard is usable:

```bash
make shell
vendor/bin/phpcs -i     # must list Drupal, DrupalPractice (or PSR12)
```

### 1.2 `phpcs.xml` at the repo root

Only the project's **own** code is in scope. Contrib, vendor, `node_modules`,
built assets and minified files are not authored here and must be excluded —
otherwise the baseline is meaningless and phpcbf will rewrite generated files.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ruleset name="<project>">
  <description>PHP CodeSniffer configuration for the project's custom PHP.</description>

  <arg name="extensions" value="php,module,inc,install,test,profile,theme"/>
  <arg name="report" value="full"/>
  <arg name="report-width" value="220"/>
  <arg name="cache" value=".phpcs-cache"/>
  <arg value="p"/>

  <ini name="memory_limit" value="1G"/>

  <!-- Authored code only. -->
  <file>./scripts</file>
  <file>./web/modules/custom</file>
  <file>./web/themes/custom</file>

  <exclude-pattern>./vendor</exclude-pattern>
  <exclude-pattern>.*/node_modules/.*</exclude-pattern>
  <exclude-pattern>./web/themes/custom/*/js/dist/.*</exclude-pattern>
  <exclude-pattern>*.min.css</exclude-pattern>
  <exclude-pattern>*.min.js</exclude-pattern>

  <rule ref="Drupal"/>
  <rule ref="DrupalPractice"/>
</ruleset>
```

Adjust `<file>` to the real custom paths — some projects namespace them
(`web/modules/<client>/`, not `web/modules/custom/`); check before copying.
Add `.phpcs-cache` to `.gitignore`.

### 1.3 Makefile targets

```make
## phpcs: Coding standards check — make phpcs [c='<args>']
phpcs:
	$(EXEC_PHP) vendor/bin/phpcs $(c)

## phpcbf: Coding standards autofix — make phpcbf [c='<args>']
phpcbf:
	$(EXEC_PHP) vendor/bin/phpcbf $(c)

## phpstan: Static analysis — make phpstan [c='<args>']
phpstan:
	$(EXEC_PHP) vendor/bin/phpstan analyse --memory-limit=1G $(c)
```

If the targets exist but hardcode no `$(c)`, add it — the whole fixing loop
below depends on being able to target one path or one sniff at a time.

**Never gate on phpcbf's exit code.** It is non-zero on perfectly successful
runs. The only reliable signal is a re-run of `phpcs`.

### 1.4 PHPStan

Dependencies, `phpstan.neon` template, and the PHPStan-1 ignore patterns
that silently match nothing under PHPStan 2: `references/phpstan.md` §1–3.

## Step 2 — Baseline, per module

Take the inventory before touching anything, and keep it: it is what proves
progress and what the MR reports.

```bash
make phpcs c='--report=summary'                       # global, per file
make phpcs c='--report=source'                        # violations grouped by sniff
make phpcs c='-n --report=summary'                    # errors only
make phpcs c='web/modules/custom/<module>'            # one module
```

`--report=source` is the one that drives the plan: it tells you which sniffs
dominate, so you know up front whether this is a comment-formatting job or a
dependency-injection job. Cross-check it against
`references/risky-sniffs-uat.md` and announce the risky categories **before**
starting, not after.

Then order the work: **one module at a time**, smallest first, so the first
commits are easy to review and the loop is proven before it meets the hard
modules.

## Step 3 — The fixing loop (per module)

For each module, in this order. Do not move to the next module until the
current one prints `No violations were found`.

```bash
# 1. Autofix
make phpcbf c='web/modules/custom/<module>'
```

**2. Read the output table, not the summary.** A line

```
FAILED TO FIX  web/modules/custom/<module>/src/Foo.php
```

means phpcbf wrote **nothing at all** for that file — every fix it computed was
discarded — while the footer still prints an encouraging
`A TOTAL OF N ERRORS WERE FIXED`. Trusting that footer is how 1375 violations
hide behind a file that looks done. Unblock it with
`references/phpcbf-unblocking.md`, then re-run.

```bash
# 3. What is left for a human
make phpcs c='web/modules/custom/<module>'
```

**4. Fix by hand, cosmetic first**, one category across the whole module at a
time (all missing docblocks, then all long lines, then all naming) — never
file-by-file mixing categories. It keeps the diff reviewable and it keeps the
commit honest.

**5. Risky categories last**, one at a time, following
`references/risky-sniffs-uat.md`. Each one produces a UAT entry (Step 4).

```bash
# 6. Prove it
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f"; done
exit
make phpcs c='web/modules/custom/<module>'   # must print: No violations were found
```

`php -l` is not optional: phpcbf and hand-editing docblocks both touch syntax,
and a parse error in a `.module` file takes the whole site down.

**7. Commit the module** (Step 8).

## Step 4 — Behaviour-changing fixes → a UAT entry, every time

The moment a fix does anything other than move whitespace or text inside a
comment, it needs a manual test written down. The rule is mechanical: **one
risky fix category in one module = one UAT line**.

Keep a running list during the session (a scratch note, not a repo file — the
UAT lives in the MR and nowhere else). Each entry states:

- **the module and what changed** (`my_search` — search dependencies
  injected),
- **the exact path a human clicks**, not "check the search works",
- **the expected result, with a number when there is one** ("1123 rows", not
  "results appear").

`references/risky-sniffs-uat.md` maps each sniff family to what it can break
and to the UAT it demands. Use it as the checklist; do not invent the mapping.

## Step 5 — The PHPStan pass

Only once phpcs is clean. Follow `references/phpstan.md`:

1. **Baseline** grouped by message (§4), not by file. On Drupal at level
   `max`, untyped hook parameters and `mixed` offsets usually dominate.
2. **Fix one error shape at a time** across all files, from the catalogue (§5).
   The catalogue says which fixes change runtime behaviour (`instanceof` and
   `is_array()` guards, arrays built locally). Each of those gets a UAT line,
   exactly as in Step 4.
3. **`.install` / update hooks get `@var` only.** They run during the deploy,
   on production.
4. **Re-run phpcs.** PHPStan fixes add `use` lines, `@var` tags and
   `@param`s, and DrupalPractice forbids `@param` on hook implementations, so
   use inline `@var` instead (§6).
5. `make phpstan` must end with `[OK] No errors`, and `make phpcs` must still
   be clean.

## Step 6 — Verify before committing

A coding-standards branch on a codebase with no test suite is verified
empirically or not at all. `references/verification.md` gives the full
procedure (container compile, service instantiation, `::create()` on every
controller/form, `createInstance()` on every plugin, one real read per
refactored service, and the trap of modules absent from
`core.extension.yml`).

Minimum, after every module that had a risky fix:

```bash
make cr        # proves the container still compiles
```

## Step 7 — CI jobs (only if asked in Step 0)

Follow `references/ci-pipelines.md`. The points that break a naive copy:

- **The QA jobs need `require-dev`; check whether the CI `vendor/` ships.**
  When the server rebuilds it (Deployer `deploy:vendors` with
  `composer install --no-dev`, the agency default), drop `--no-dev` from the
  existing composer job and reuse it; exclude the contrib directories it now
  carries from the upload. Only when the CI `vendor/` runs in production, keep
  `--no-dev` there and add a separate `composer_qa` job the deploy never
  depends on.
- **`|| true` means the jobs never fail on a violation.** Say so when asked
  "will they pass?". The honest answer is "yes, and they cannot fail on
  violations", plus the actual counts from a local run of the job scripts.
- **`sonar-project.properties` alone does nothing.** A scanner job has to run,
  in a later stage than the QA jobs and depending on them.
- **Exclude the QA files from the deploy upload** (Deployer `upload_options`,
  anchored `--exclude=/…`), and add `/qa-reports/` to `.gitignore`.
- **Prove it locally**: run each job's script lines in the php container,
  parse the YAML, and `php -l` the `deploy.php`. The jobs have not run on
  GitLab until the first pipeline on a matching branch; that goes in the UAT.

## Step 8 — Git: one commit per module, one Draft MR

**One commit per module**, so the reviewer can read the branch module by module
and so a regression can be bisected to a single module.

```
style(<module>: #<ticket>): coding standards
refactor(<module>: #<ticket>): inject the <x> dependencies
```

Use `style(...)` when the module needed only cosmetic fixes, and split the
risky work into its own `refactor(...)` / `fix(...)` commit for that module —
that separation is what makes the UAT entry reviewable against a diff.

The tooling goes in **its own commit, first**: `phpcs.xml`, `phpstan.neon`,
the Makefile targets, and, when Step 7 ran, the CI jobs, converters,
`sonar-project.properties`, `.gitignore` and the deploy excludes. Follow the
repo's commit format when it has one (e.g. `chore(qa-#<ticket>) : …`) rather
than the examples above.

- **If `gm:merge-request` is available**, use it for the branch, the push and
  the MR (it carries the team's conventions: branch `chore/<ticket>-phpcs`,
  Draft MR, French description, the self-hosted GitLab host). It commits once by
  default — here you commit per module yourself, then let it push and open the
  MR.
- **Otherwise**, plain git: branch off the integration branch, commit per
  module, push, and open the MR with `glab` if authenticated.

Stage explicitly, never `git add -A`:

```bash
git add web/modules/custom/<module>
git diff --cached --name-only    # must contain only that module
```

The MR description follows the team template; the collected UAT entries go
under its **`### UAT manuelle`** heading, as a checklist — every risky fix from
Step 4, none dropped. Write them in **the language the team writes its MRs in**
(French in the examples below; the code and the commits stay English):

```markdown
### UAT manuelle
- [ ] Recherche : /recherche?type=article → 1123 résultats, facette "Récents" active
- [ ] Export CSV (action groupée) : sélectionner 3 nœuds → Exporter → fichier non vide
- [ ] Panier : ajouter un élément, recharger la page, l'élément est toujours là
```

Under **`## Vérification`**, state the empirical checks that actually ran
(`make phpcs` clean on N modules, `make phpstan` clean at level N, `php -l`,
`make cr`, the instantiation script, the CI job scripts run locally), with
the before/after counts for both tools. When the local site does not boot,
say so under `## Vérification` and do not present the UAT as optional.

## Definition of done

- [ ] The standard and the severity were **asked**, not assumed.
- [ ] `vendor/bin/phpcs -i` lists the chosen standard.
- [ ] `phpcs.xml` scopes only authored code; `make phpcs c='<args>'` works.
- [ ] `make phpcs` prints **`No violations were found`** at the chosen severity
      — no `FAILED TO FIX` line anywhere in the last phpcbf run.
- [ ] `php -l` clean on every touched file.
- [ ] PHPStan, if asked: `make phpstan` ends with `[OK] No errors` at the
      chosen level, and phpcs is still clean afterwards.
- [ ] CI, if asked: what runs in production is installed `--no-dev` (by the
      server, or by a CI job the QA install does not touch). The QA files are
      excluded from the deploy upload, and every job script ran in the
      container.
- [ ] `make cr` succeeds.
- [ ] One commit per module; nothing unrelated staged.
- [ ] Every behaviour-changing fix has a UAT line in the MR's
      `### UAT manuelle`, with a concrete path and an expected result.
- [ ] The MR is a **Draft**; UAT and "mark Ready" are the user's to do.

## Non-goals

- Do not reformat contrib, vendor, core, or generated assets.
- Do not "fix" a violation by adding `// phpcs:ignore` unless the user asks —
  and if they do, the ignore carries a reason on the same line.
- Do not loosen `phpcs.xml` (excluding a sniff, dropping `DrupalPractice`) to
  make a count go down. If a sniff is genuinely wrong for this project, say so
  and let the user decide.
- Do not mix a standards pass with a functional change that no sniff asked for.
- Do not lower the PHPStan level, generate a `phpstan-baseline.neon`, add an
  `ignoreErrors` entry or a `@phpstan-ignore` for custom-code errors, or
  "repair" dead ignore patterns to make a count go down, unless the user asks.
- Do not add a SonarQube scanner job, make the QA jobs gating, or extend them
  to more branches than the user chose.
