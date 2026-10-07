---
name: phpcbf
description: >
  Run the phpcbf autofix pass of a PHP coding-standards campaign on a
  Dockerized, Makefile-driven project (Drupal or PSR-12): one phpcbf run over
  the whole custom tree, unblock every "FAILED TO FIX" file (section banners,
  commented-out code, one sniff at a time), php -l, and produce commit 1 with
  the phpcs tooling. Ends by proposing /clear then /php-standards for the next
  pass. Use when the user asks for the phpcbf / autofix pass, mentions
  "FAILED TO FIX" or phpcbf discarding fixes, or when the php-standards
  orchestrator routes here. IMPORTANT: all commands MUST go through Makefile
  targets; phpcbf's exit code and its "A TOTAL OF N ERRORS WERE FIXED" footer
  prove nothing — only a phpcs re-run does.
---

# phpcbf pass → commit 1

Part of the `php-standards` campaign; that skill owns the setup, the
questions, the state file and the MR. This one only writes commit 1: what
phpcbf wrote, the minimal edits that let it write, and the phpcs tooling.

## Start

```bash
cat .git/php-standards.md 2>/dev/null
ls phpcs.xml
```

- **No `phpcs.xml`**: the toolchain is not set up. Stop and invoke
  `php-standards` (its Steps 1–3 run first, then come back here).
- **No notes file** (standalone use, `phpcs.xml` already there): ask only the
  ticket id, and create `.git/php-standards.md` in the format of the
  `php-standards` skill, with `phpstan: ?` and `ci: ?`.
- Set `pass: phpcbf` in the notes file. If `## Baseline` has no phpcs line,
  take it now: `make phpcs c='--report=summary' | tail -5`.

Everything goes through the Makefile, arguments through `c='…'`. The
severity is in `phpcs.xml`; do not add `-n`.

## 1. One run on the whole tree

```bash
make phpcbf | grep -E 'FAILED TO FIX|A TOTAL OF'
```

**Never gate on phpcbf's exit code**: it is non-zero on successful runs.

**A `FAILED TO FIX` line** means phpcbf wrote **nothing at all** for that
file — every fix it computed was discarded — while the footer still prints an
encouraging `A TOTAL OF N ERRORS WERE FIXED`. Trusting that footer is how 1375
violations hide behind a file that looks done.

## 2. Unblock every `FAILED TO FIX` file

Follow `references/phpcbf-unblocking.md`: hand-edit the blockers (section
banners, commented-out PHP), re-run phpcbf on that file, then one sniff at a
time if it still does not converge. Repeat the whole-tree run until no
`FAILED TO FIX` line is left.

Each hand edit is a non-mechanical hunk inside a mechanical commit: note it
(file + what was removed) for the commit body.

## 3. Check

```bash
make phpcs c='--report=summary' | tail -5          # what is left for the phpcs pass
make shell
for f in $(git diff --name-only --diff-filter=ACM | grep -E '\.(php|module|inc|install|theme|profile)$'); do php -l "$f" | grep -v '^No syntax errors'; done
exit
make cr
```

`php -l` is not optional: a parse error in a `.module` file takes the site
down. `git diff --stat` only; read a hunk only for the hand-edited files.

## 4. Commit 1

Stage explicitly, never `git add -A`: the custom tree, `phpcs.xml`, the
Makefile, `composer.json`/`composer.lock` (`drupal/coder`), `.gitignore`.

```bash
git add web/modules/custom web/themes/custom phpcs.xml Makefile composer.json composer.lock .gitignore
git diff --cached --stat | tail -3
```

Message (follow the repo's format if it has one; keep the word `phpcbf`):

```
style(qa: #<ticket>): apply phpcbf autofixes

phpcs: <before> -> <after> (<standard>, <severity>)

Not mechanical:
- web/modules/custom/foo/foo.module: section banners removed (blocked phpcbf)
```

phpcbf found nothing and the tooling already existed: no commit, say so.

## End: propose `/clear`

Update the notes file (`pass: none`, the phpcs count left), then stop and
print, without starting the next pass:

```
phpcbf pass done — commit <sha>: <before> → <after> violations, <n> files unblocked by hand.
Next: the phpcs pass. Run /clear, then /php-standards (the state is in .git/php-standards.md and the commits).
```

Continue in this conversation only if the user declines the clear.

## Non-goals

- No hand fix of a phpcs violation that phpcbf could not compute: that is the
  `phpcs` pass and commit 2.
- No `// phpcs:ignore`, no loosening of `phpcs.xml` to get a file through.
- Do not reformat contrib, vendor, core, or generated assets.
