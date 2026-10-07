---
name: phpcs
description: >
  Run the phpcs hand-fix pass of a PHP coding-standards campaign on a
  Dockerized, Makefile-driven project (Drupal or PSR-12): clear what phpcbf
  left, one sniff at a time across the whole custom tree, cosmetic first and
  the risky DrupalPractice sniffs last (dependency injection, method renames,
  t() routing), each behaviour-changing fix recorded as a manual UAT line;
  verify, and produce commit 2. Ends by proposing /clear then /php-standards
  for the next pass. Use when the user asks to fix the remaining phpcs
  violations, mentions a sniff, DrupalPractice, drupal/coder warnings, or
  when the php-standards orchestrator routes here. IMPORTANT: all commands
  MUST go through Makefile targets; the run is clean only when phpcs prints
  "No violations were found".
---

# phpcs pass → commit 2

Part of the `php-standards` campaign; that skill owns the setup, the
questions, the state file and the MR. This one writes commit 2: the hand
fixes for every violation phpcbf did not fix.

> ⚠️ **Not a cosmetic-only pass.** On Drupal, `DrupalPractice` forces
> dependency injection, method renames and `t()` routing — changes that *can*
> break behaviour. They are applied, each **paired with a UAT line** naming
> the file and the change.

## Start

```bash
cat .git/php-standards.md 2>/dev/null
git log --oneline -5
```

- **No `phpcs.xml`**: stop and invoke `php-standards`.
- **No notes file** (standalone use): ask only the ticket id and create
  `.git/php-standards.md` in the format of the `php-standards` skill.
- **No phpcbf commit and no prior phpcbf run**: run the `phpcbf` pass first;
  hand-fixing what phpcbf would fix wastes the session.
- **`pass: phpcs` with uncommitted changes**: a previous conversation was
  cleared mid-pass. Keep the working tree, read the pending UAT lines in the
  notes file, and resume from the current `--report=source`.
- Set `pass: phpcs`.

Everything goes through the Makefile, arguments through `c='…'`. The
severity is in `phpcs.xml`; do not add `-n`.

## Keep the context small

- `--report=source` or `--report=summary` on the whole tree; a full report
  only on one path, through `| head -60`.
- **One sniff across the whole tree at a time**, one re-run per sniff, never
  file by file mixing categories.
- No subagent per module: each one reloads the skill and the files.
- `git diff --stat`, not `git diff`, unless a hunk is under review.
- If the context still grows large mid-pass, write the pending UAT lines to
  the notes file and propose `/clear` + `/php-standards`: the pass resumes
  from the working tree.

## 1. What is left

```bash
make phpcs c='--report=source' | head -40
make phpcs c='--sniffs=<Sniff.Code> --report=summary'    # the files for one sniff
```

Map the list against `references/risky-sniffs-uat.md` and announce the risky
categories before starting.

## 2. Cosmetic sniffs first

Missing docblocks, then long lines, then naming in comments — each across the
whole tree, then one re-run. No UAT for these (the reference lists which
categories need none).

## 3. Risky sniffs last, one category at a time

Follow `references/risky-sniffs-uat.md` for each family: what it can break,
how to apply it safely, which UAT it demands.

**One risky category in one module = one UAT line**, appended to
`## UAT (not yet in a commit)` in the notes file **as soon as the fix is
made** — not at the end. Each line states:

- **the file and the change** (`gm_search/src/Form/SearchForm.php: search
  dependencies injected`), so the reviewer finds it in the diff;
- **the exact path a human clicks**, not "check the search works";
- **the expected result, with a number when there is one** ("1123 results",
  not "results appear").

## 4. Verify

Done when `make phpcs` prints `No violations were found`. Then:

```bash
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f" | grep -v '^No syntax errors'; done
exit
make cr
```

When the pass injected services, renamed methods or touched plugins, run the
`php-standards` skill's `references/verification.md` (service instantiation,
`::create()` on controllers and forms, `createInstance()` on plugins, one
real read per refactored service). Note what ran: the MR reports it.

## 5. Commit 2

```bash
git add web/modules/custom web/themes/custom
git diff --cached --stat | tail -3
```

Message (repo format if it has one; keep the word `phpcs`), with the pending
UAT lines moved from the notes file into the body:

```
style(qa: #<ticket>): fix the remaining phpcs violations

phpcs: <after phpcbf> -> 0 (<standard>, <severity>)
Verified: php -l, make cr, <n>/<n> services instantiated

UAT:
- gm_search/src/Form/SearchForm.php: search dependencies injected — /recherche?type=article → 1123 results
```

A late fix to commit 1 goes into it: `git commit --fixup=<sha>` then
`GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <sha>~1`.

## End: propose `/clear`

Update the notes file (`pass: none`, UAT section emptied), then stop and
print, without starting the next pass:

```
phpcs pass done — commit <sha>: <n> -> 0 violations, <k> UAT lines recorded in the commit body.
Next: the phpstan pass (or CI + MR if phpstan is "no"). Run /clear, then /php-standards.
```

Continue in this conversation only if the user declines the clear.

## Non-goals

- No `// phpcs:ignore` unless the user asks — and then with a reason on the
  same line.
- Do not loosen `phpcs.xml` to make a count go down. If a sniff is genuinely
  wrong for the project, say so and let the user decide.
- Do not mix in a functional change that no sniff asked for.
