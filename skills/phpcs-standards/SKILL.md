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
  whether to add CI jobs (which branches, report-only vs gating). Fixes the
  whole tree one sniff / error shape at a time, uses Rector for the mechanical
  PHPStan type fixes, commits exactly three times (phpcbf, phpcs, phpstan),
  and records every behaviour-changing fix as a manual UAT step in the merge
  request. IMPORTANT: all commands MUST go through Makefile targets;
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
2. **Clear the phpcs violations** across the custom tree, without breaking the
   site.
3. **Clear the PHPStan errors** at the chosen level (`references/phpstan.md`).
4. **Add the CI jobs**: phpcs and phpstan in GitLab CI, with SonarQube report
   converters and the deploy adjustments they need
   (`references/ci-pipelines.md`).

> ⚠️ **This is not a cosmetic-only task.** On a real Drupal codebase, the
> `DrupalPractice` sniffs force dependency injection, method renames and
> `t()` routing — changes that *can* break behaviour. Those are applied, but
> **paired with a mandatory manual UAT entry** in the MR, naming the file and
> the change so the reviewer can find it in the diff. See
> `references/risky-sniffs-uat.md`.

## Token budget: keep the session lean

A standards pass is long and loop-heavy: every tool call re-reads the whole
conversation, so its cost grows with *turns × context size*, not with the
size of one output. A run on ginger-sofreco that chained the D11 campaign,
four review/MR rounds and this skill in one conversation reached 830 turns on
a 560k-token context. Rules:

- **Start from a clean conversation.** If the current one already carries
  another campaign (an upgrade, reviews, MRs), tell the user to `/clear` and
  re-invoke the skill before Step 1. Do not start the loop on a big context.
- **No subagent per module.** Each one reloads the skill, the references and
  the files. Work in the main session, one sniff / error shape across the
  whole tree (Steps 3 and 5).
- **Small outputs only.** Whole-tree runs use `--report=summary` or
  `--report=source`; a full report only on one path, piped through
  `| head -60`. PHPStan uses `--error-format=raw --no-progress` and is
  grouped (`references/phpstan.md` §4). `git diff --stat`, not `git diff`,
  unless a hunk is actually being reviewed.
- **Let the tools write the mechanical fixes.** phpcbf for style, Rector for
  types (Step 5). Hand edits are for what neither can do.
- **Re-run per category, not per edit.** One phpcs/PHPStan run after a whole
  category is fixed, not after each file.
- **Read a reference only when its step starts**, and only the section you
  need.

## Golden rule: everything goes through the Makefile

Never run `phpcs`, `phpcbf`, `phpstan`, `composer` or `drush` on the host.

| Need | Make target |
|---|---|
| Check standards | `make phpcs c='<args>'` |
| Autofix | `make phpcbf c='<args>'` |
| Static analysis | `make phpstan c='<args>'` |
| Type fixes | `make rector c='<args>'` |
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

## rector: Automated refactoring — make rector [c='<args>']
rector:
	$(EXEC_PHP) vendor/bin/rector process $(c)
```

If the targets exist but hardcode no `$(c)`, add it — the whole fixing loop
below depends on being able to target one path or one sniff at a time.

**Never gate on phpcbf's exit code.** It is non-zero on perfectly successful
runs. The only reliable signal is a re-run of `phpcs`.

### 1.4 PHPStan

Dependencies, `phpstan.neon` template, and the PHPStan-1 ignore patterns
that silently match nothing under PHPStan 2: `references/phpstan.md` §1–3.

## Step 2 — Baseline

Take the inventory before touching anything, and keep it: it is what proves
progress and what the MR reports.

```bash
make phpcs c='--report=summary' | tail -5             # global totals
make phpcs c='--report=source'                        # violations grouped by sniff
make phpcs c='-n --report=source'                     # errors only
```

`--report=source` is the one that drives the plan: it tells you which sniffs
dominate, so you know up front whether this is a comment-formatting job or a
dependency-injection job. Cross-check it against
`references/risky-sniffs-uat.md` and announce the risky categories **before**
starting, not after.

## Step 3 — The fixing loop (whole tree)

The work is ordered by tool and by sniff, not by module: that is what gives
the three commits of Step 8.

### 3.1 phpcbf, once, on the whole tree → commit 1

```bash
make phpcbf | grep -E 'FAILED TO FIX|A TOTAL OF'
```

**A `FAILED TO FIX` line** means phpcbf wrote **nothing at all** for that
file — every fix it computed was discarded — while the footer still prints an
encouraging `A TOTAL OF N ERRORS WERE FIXED`. Trusting that footer is how 1375
violations hide behind a file that looks done. Unblock it with
`references/phpcbf-unblocking.md`, re-run phpcbf, and repeat until no
`FAILED TO FIX` line is left.

Then `php -l` (below) and **commit 1** with the phpcs tooling (Step 8). This
commit holds only what phpcbf wrote, plus the minimal unblocking edits: the
reviewer can skim it.

### 3.2 phpcs by hand, one sniff at a time → commit 2

```bash
make phpcs c='--report=source'                        # what is left, by sniff
make phpcs c='--sniffs=<Sniff.Code> --report=summary' # the files for one sniff
```

**Fix one sniff across the whole tree at a time, cosmetic first** (all missing
docblocks, then all long lines, then all naming), never file by file mixing
categories. Re-run phpcs once per sniff, not once per file.

**Risky categories last**, one at a time, following
`references/risky-sniffs-uat.md`. Each one produces a UAT entry (Step 4).

Done when `make phpcs` prints `No violations were found`; then `php -l`,
`make cr`, and **commit 2**.

### `php -l` on the touched files

```bash
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f" | grep -v '^No syntax errors'; done
exit
```

`php -l` is not optional: phpcbf and hand-editing docblocks both touch syntax,
and a parse error in a `.module` file takes the whole site down. Run it
before each commit, on the files the commit touches.

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

## Step 5 — The PHPStan pass → commit 3

Only once phpcs is clean and commit 2 is done. Follow `references/phpstan.md`:

1. **Baseline** grouped by message (§4), not by file. On Drupal at level
   `max`, untyped hook parameters and `mixed` values usually dominate
   (offset reads on `mixed` are ignored by the template `phpstan.neon`).
2. **Rector first** for the type shapes it can infer (missing return types,
   `void`, types read from strict returns or typed properties):
   `references/phpstan.md` §5.1. Dry-run, read the diff stat, apply, then
   `make phpcbf` — Rector prints new code in its own style — and re-run the
   PHPStan baseline. It usually removes the bulk of the "no return type"
   errors in one call instead of one hand edit per function.
3. **Fix one remaining error shape at a time** across all files, from the
   catalogue (§5).
   The catalogue says which fixes change runtime behaviour (`instanceof` and
   `is_array()` guards, arrays built locally). Each of those gets a UAT line,
   exactly as in Step 4.
4. **`.install` / update hooks get `@var` only.** They run during the deploy,
   on production. Rector skips them (§5.1).
5. **Re-run phpcs.** PHPStan fixes add `use` lines, `@var` tags and
   `@param`s, and DrupalPractice forbids `@param` on hook implementations, so
   use inline `@var` instead (§6).
6. `make phpstan` must end with `[OK] No errors`, and `make phpcs` must still
   be clean. Then Step 6 and **commit 3**: the PHPStan fixes, the Rector
   output, phpcs corrections they required, `phpstan.neon`, and the CI files
   when Step 7 ran.

## Step 6 — Verify before committing

A coding-standards branch on a codebase with no test suite is verified
empirically or not at all. `references/verification.md` gives the full
procedure (container compile, service instantiation, `::create()` on every
controller/form, `createInstance()` on every plugin, one real read per
refactored service, and the trap of modules absent from
`core.extension.yml`).

Minimum, before commit 2 and commit 3:

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

## Step 8 — Git: exactly three commits, one Draft MR

**Three commits, one per tool, in this order.** No per-module commits, no
separate tooling commit, no fix-up commits. A late fix goes into the commit
it belongs to: `git commit --amend` when that is the last one, otherwise
`git commit --fixup=<sha>` then
`GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <sha>~1`.

| # | Contents | Example message |
|---|---|---|
| 1 | phpcbf output (Step 3.1), the unblocking edits, `phpcs.xml`, the Makefile targets, `drupal/coder` in `composer.json`/`composer.lock`, `.gitignore` | `style(qa: #<ticket>): apply phpcbf autofixes` |
| 2 | hand fixes for phpcs (Step 3.2), risky ones included | `style(qa: #<ticket>): fix the remaining phpcs violations` |
| 3 | Rector output + PHPStan fixes (Step 5), `phpstan.neon`, `rector.php`, their dev dependencies, and the CI files when Step 7 ran | `refactor(qa: #<ticket>): fix the phpstan errors at level <n>` |

Commit 1 is mechanical and skimmable; commits 2 and 3 are where the review
happens. The risky fixes are not isolated in their own commits any more, so
each UAT line names the **file and the change** (`gm_search/src/Form/Foo.php:
search dependencies injected`) for the reviewer to find it in the diff.

Skip a commit only when its step had nothing to do (phpstan not asked, or
phpcbf found nothing), and say so. Follow the repo's commit format when it has
one (e.g. `chore(qa-#<ticket>) : …`) rather than the examples above.

- **If `gm:merge-request` is available**, use it for the branch, the push and
  the MR (it carries the team's conventions: branch `chore/<ticket>-phpcs`,
  Draft MR, French description, the self-hosted GitLab host). It commits once by
  default — here the three commits are already made, so let it only push and
  open the MR.
- **Otherwise**, plain git: branch off the integration branch, make the three
  commits, push, and open the MR with `glab` if authenticated.

Stage explicitly, never `git add -A`, and check with the stat, not the diff:

```bash
git add web/modules/custom web/themes/custom phpcs.xml Makefile …
git diff --cached --stat | tail -3
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
- [ ] Exactly three commits — phpcbf, phpcs, phpstan — nothing unrelated
      staged.
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
- Do not add PHP-CS-Fixer. phpcbf is already the fixer for the phpcs
  standard; PHP-CS-Fixer has no maintained Drupal rule set and its PSR-style
  output (indentation, braces, docblocks) is rewritten back by phpcbf, so it
  only adds a loop. On a PSR-12 project, phpcbf covers it too.
- Do not lower the PHPStan level, generate a `phpstan-baseline.neon`, add an
  `ignoreErrors` entry beyond the template's or a `@phpstan-ignore` for
  custom-code errors, or
  "repair" dead ignore patterns to make a count go down, unless the user asks.
- Do not add a SonarQube scanner job, make the QA jobs gating, or extend them
  to more branches than the user chose.
