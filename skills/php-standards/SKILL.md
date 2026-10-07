---
name: php-standards
description: >
  Orchestrate a PHP coding-standards campaign on a Dockerized, Makefile-driven
  PHP project (Drupal or PSR-12): asks the standard, severity, PHPStan level,
  CI and ticket once, sets up phpcs (drupal/coder, phpcs.xml, Makefile
  targets), then routes to three sub-skills that each own one commit and run
  in their own conversation — phpcbf (autofix pass), phpcs (hand fixes, risky
  DrupalPractice sniffs with UAT), phpstan (chosen level or max, Rector). It
  is stateless and re-entrant: re-invoke /php-standards after each /clear and
  it reads the repo state and resumes at the next pass. It owns the closing
  steps: the phpcs/phpstan GitLab CI jobs with SonarQube report converters,
  and the Draft MR with the UAT collected from the commit bodies. Use when the
  user wants custom code brought to zero phpcs/phpstan violations, mentions
  coding standards, "normes de codage", static analysis, a ruleset /
  phpcs.xml, phpcs/phpstan pipelines, sonar-project.properties, or invokes
  /php-standards. IMPORTANT: all commands MUST go through Makefile targets;
  one pass per conversation; the CI jobs need require-dev, so check whether
  the CI vendor/ ships before touching the composer job's --no-dev.
---

# PHP standards campaign — orchestrator

The campaign is three passes, each a sub-skill that produces exactly one
commit, plus the setup and two closing steps this skill owns:

| Pass | Owner | Commit |
|---|---|---|
| Setup + baseline | **this skill** (Steps 1–3) | folded into commit 1 |
| phpcbf autofix, `FAILED TO FIX` unblocking | **`phpcbf`** | 1 — `style(qa: #<ticket>): apply phpcbf autofixes` |
| phpcs hand fixes, risky sniffs → UAT | **`phpcs`** | 2 — `style(qa: #<ticket>): fix the remaining phpcs violations` |
| PHPStan at the chosen level, Rector | **`phpstan`** | 3 — `refactor(qa: #<ticket>): fix the phpstan errors at level <n>` |
| CI jobs (if asked) | **this skill** (Step 4) | amended into the last commit |
| Draft MR | **this skill** (Step 5) | — |

Follow the repo's commit format when it has one. Keep the words `phpcbf`,
`phpcs` and `phpstan` in the three subjects: Step 0 finds the passes by them.

## One pass per conversation

Every tool call re-reads the whole conversation, so cost grows with
*turns × context*. A ginger-sofreco run that chained a D11 campaign, reviews
and the whole standards pass in one conversation reached 830 turns on a
560k-token context. So:

- **Each pass ends by proposing `/clear`, then `/php-standards`.** A skill
  cannot clear the conversation itself; it stops and tells the user. It does
  not chain into the next pass unless the user declines the clear.
- **Nothing is lost by clearing**, because the state lives in the repo, not in
  the conversation (next section).
- The only chaining allowed: setup (Steps 1–3, cheap) flows straight into the
  `phpcbf` pass in the same conversation.
- If the current conversation already carries other work, tell the user to
  `/clear` and re-invoke before Step 1.

## Where the state lives

| What | Where |
|---|---|
| Standard, severity | `phpcs.xml` (`<rule ref>`, `warning-severity`) |
| PHPStan level | `phpstan.neon` once the `phpstan` pass created it; before that, the notes file |
| Ticket, PHPStan and CI answers, baselines, the pass in progress, UAT lines not yet committed | **`.git/php-standards.md`** — inside `.git/`, never committed, survives `/clear` |
| Final counts, non-mechanical hunks, UAT lines | the **body of each QA commit** — durable, read back by Step 5 |

Notes file format (created in Step 1; every sub-skill reads and updates it):

```markdown
# php-standards
ticket: 50018
standard: Drupal + DrupalPractice
severity: errors + warnings
phpstan: max            # or a level, or "no"
ci: release, master — report-only, sonar later   # or "no"
pass: phpcs             # the pass in progress, or "none"

## Baseline
phpcs: 1375 errors, 212 warnings in 64 files (before phpcbf)
phpstan: -

## UAT (not yet in a commit)
- gm_search/src/Form/SearchForm.php: search dependencies injected — /recherche?type=article → 1123 results
```

When a pass commits, its pending UAT lines move into the commit body and leave
this file. Commit bodies are written in English, like the code:

```
style(qa: #50018): fix the remaining phpcs violations

phpcs: 1375 errors, 212 warnings -> 0 (Drupal + DrupalPractice, errors + warnings)

UAT:
- gm_search/src/Form/SearchForm.php: search dependencies injected — /recherche?type=article → 1123 results
```

## Golden rule: everything goes through the Makefile

Never run `phpcs`, `phpcbf`, `phpstan`, `rector`, `composer` or `drush` on the
host: `make phpcs c='<args>'`, `make phpcbf c='<args>'`,
`make phpstan c='<args>'`, `make rector c='<args>'`,
`make composer-require <pkg> --dev`, `make cr`, `make shell`.

Many Makefiles end with a catch-all (`%:` / `@:`) that **swallows positional
arguments**: always pass them through the variable (`c='…'`). Check which
variable the targets read — if they take `ARGS=`, `c='…'` is silently dropped
and the run covers the whole tree.

## Step 0 — Where are we?

```bash
cat .git/php-standards.md 2>/dev/null
git log --oneline <integration-branch>..HEAD
git status --short | grep -v '^??' | head
ls phpcs.xml phpstan.neon 2>/dev/null
```

| State | Next |
|---|---|
| No notes file, no `phpcs.xml` | Steps 1–3, then invoke **`phpcbf`** in this conversation |
| `pass:` names a pass and there are uncommitted changes | that pass was interrupted: invoke its sub-skill, it resumes |
| No `phpcbf` commit | invoke **`phpcbf`** |
| `phpcbf` commit, no `phpcs` commit | invoke **`phpcs`** |
| `phpcs` commit, `phpstan:` is not `no`, no `phpstan` commit | invoke **`phpstan`** |
| Every wanted pass committed | Step 4 (if `ci:` is not `no`), then Step 5 |

A `phpcs.xml` without a notes file (tooling from an earlier campaign): run
Step 1 for the questions it does not settle, skip Step 2's existing items,
then route.

Say in one line which state you found and what runs next.

## Step 1 — Ask once, write it down

Ask these together, in one message, skipping what the request or an existing
`phpcs.xml` / `phpstan.neon` already settles (say which you took as settled):

1. **Standard** — `Drupal` + `DrupalPractice` (needs `drupal/coder`; the
   practice sniffs carry the behaviour-touching fixes), `Drupal` only, or
   `PSR-12`.
2. **Severity** — errors only (the usual first pass and CI gate), or errors +
   warnings (the complete pass; on Drupal the warnings are mostly
   `DrupalPractice`, so most of the UAT risk).
3. **PHPStan?** No, or which level. `max` is the agency template and is
   reachable on a small custom codebase; propose 5–6 on a large legacy one.
4. **CI jobs?** No, or which branches (usually the deploy branches only),
   report-only (`|| true`, the agency template) or gating, SonarQube scanner
   now or later.
5. **Ticket id**, for the commits and the MR.

Write the answers to `.git/php-standards.md`, with `pass: phpcbf`.

## Step 2 — Set up or verify the phpcs toolchain

Check each item; create only what is missing; report what already existed.
PHPStan's own setup belongs to the `phpstan` pass.

**Dependencies.**

```bash
make composer-require drupal/coder --dev               # Drupal (pulls phpcs + slevomat)
make composer-require squizlabs/php_codesniffer --dev  # PSR-12 only
```

`composer.json` must allow the installer plugin, or the standards register
nowhere:

```json
"config": { "allow-plugins": { "dealerdirect/phpcodesniffer-composer-installer": true } }
```

Proof that the standard is usable: `make shell`, then `vendor/bin/phpcs -i`
lists `Drupal`, `DrupalPractice` (or `PSR12`).

**`phpcs.xml` at the repo root** — authored code only. Contrib, vendor,
`node_modules`, built and minified assets are excluded, or the baseline is
meaningless and phpcbf rewrites generated files:

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

- Adjust `<file>` to the real custom paths (some projects use
  `web/modules/<client>/`).
- **Errors only**: add `<arg name="warning-severity" value="0"/>`. The
  severity then lives in the ruleset: every `make phpcs` / `make phpcbf` and
  the CI jobs apply it, and no command needs `-n`.
- Add `.phpcs-cache` to `.gitignore`.

**Makefile targets**, reading `$(c)`:

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

If the targets exist without `$(c)`, add it.

## Step 3 — Baseline, then hand over to `phpcbf`

```bash
make phpcs c='--report=summary' | tail -5
make phpcs c='--report=source' | head -40
```

Write the totals under `## Baseline` in the notes file. Cross-check the
`--report=source` list against the `phpcs` skill's
`references/risky-sniffs-uat.md` and **announce the risky categories now**, so
the user knows up front whether this is a comment-formatting job or a
dependency-injection job.

Then invoke **`phpcbf`** in this conversation. The tooling from Step 2 goes
into its commit.

## Step 4 — CI jobs (only if `ci:` is not `no`)

Follow `references/ci-pipelines.md`, using the answers in the notes file
(its §0 is already answered). The points that break a naive copy:

- **The QA jobs need `require-dev`; check whether the CI `vendor/` ships.**
  When the server rebuilds it (Deployer `deploy:vendors` with
  `composer install --no-dev`, the agency default), drop `--no-dev` from the
  existing composer job and reuse it; exclude the contrib directories it now
  carries from the upload. Only when the CI `vendor/` runs in production, keep
  `--no-dev` there and add a separate `composer_qa` job the deploy never
  depends on.
- **`|| true` means the jobs never fail on a violation.** Asked "will they
  pass?", the honest answer is "yes, and they cannot fail on violations",
  plus the counts from a local run of the job scripts.
- **`sonar-project.properties` alone does nothing.** A scanner job has to run,
  in a later stage than the QA jobs and depending on them.
- **Exclude the QA files from the deploy upload** (Deployer `upload_options`,
  anchored `--exclude=/…`), and add `/qa-reports/` to `.gitignore`.
- **Prove it locally**: run each job's script lines in the php container,
  parse the YAML, and `php -l` the `deploy.php`. The jobs have not run on
  GitLab until the first pipeline on a matching branch: add that as a UAT line.

Amend the CI files into the **last** QA commit (`git commit --amend`), adding
a `CI:` line and the CI UAT line to its body. If that commit was already
pushed, ask before amending.

## Step 5 — The Draft MR

Rebuild the MR from the commits, not from memory:

```bash
git log --format='%h %s%n%b' <integration-branch>..HEAD
```

- **If `gm:merge-request` is available**, use it for the push and the MR (the
  team's conventions: branch `chore/<ticket>-phpcs`, Draft MR, French
  description, the self-hosted GitLab host). The commits are already made: it
  only pushes and opens the MR.
- **Otherwise**, push and open the Draft MR with `glab` if authenticated.

The MR description follows the team template, in the language the team
writes its MRs in (French below; code and commits stay English):

- **`### UAT manuelle`**: every `UAT:` line from the commit bodies, as a
  checklist, translated, none dropped, each naming the file and the change so
  the reviewer finds it in the diff.
- **`## Vérification`**: the checks that actually ran, with the before/after
  counts from the commit bodies (format: `references/verification.md`, last
  section). When the local site does not boot, say so and do not present the
  UAT as optional.

```markdown
### UAT manuelle
- [ ] `gm_search/src/Form/SearchForm.php` (dépendances injectées) : /recherche?type=article → 1123 résultats
- [ ] Pipeline GitLab : premier pipeline sur `release` → jobs `phpcs` et `phpstan` verts, rapports dans les artefacts
```

Then delete `.git/php-standards.md`: the campaign is over.

## Definition of done

- [ ] Standard, severity, PHPStan level, CI and ticket were **asked**, once.
- [ ] `vendor/bin/phpcs -i` lists the chosen standard; `phpcs.xml` scopes only
      authored code and carries the severity.
- [ ] One commit per pass — phpcbf, phpcs, phpstan (if asked) — each with its
      counts and UAT lines in the body; nothing unrelated staged.
- [ ] `make phpcs` prints `No violations were found`; `make phpstan` ends with
      `[OK] No errors` at the chosen level (if asked); `make cr` succeeds.
- [ ] CI, if asked: production `vendor/` stays `--no-dev`, QA files excluded
      from the upload, every job script ran in the container.
- [ ] The MR is a **Draft**, with every UAT line under `### UAT manuelle`;
      UAT and "mark Ready" are the user's to do.

## Non-goals

- Do not reformat contrib, vendor, core, or generated assets.
- Do not loosen `phpcs.xml` (excluding a sniff, dropping `DrupalPractice`) to
  make a count go down. If a sniff is genuinely wrong for the project, say so
  and let the user decide.
- Do not add PHP-CS-Fixer: no maintained Drupal rule set, and phpcbf rewrites
  its output back, so it only adds a loop.
- Do not add a SonarQube scanner job, make the QA jobs gating, or extend them
  to more branches than the user chose.
- Do not run two passes in one conversation unless the user declines the
  `/clear`.
