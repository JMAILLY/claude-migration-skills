# When phpcbf reports `FAILED TO FIX`

## What actually happens

phpcbf fixes a file in **loops**: it applies the fixers, re-runs the sniffs, and
repeats until nothing changes (50 passes max). If two fixers keep undoing each
other, the loop never converges — and phpcbf then **throws the whole file away**.
Not the conflicting fix: *every* fix it had computed for that file.

The file therefore keeps 100% of its violations, while the run footer still
prints:

```
A TOTAL OF 412 ERRORS WERE FIXED IN 37 FILES
```

That footer counts the files that converged. The only line that matters is:

```
FAILED TO FIX  web/modules/custom/foo/src/Bar.php
```

**Never conclude a file is fixed from the footer.** Conclude it from
`make phpcs c='<path>'` printing `No violations were found`.

## The two recurring causes

### 1. Section banner comments

```php
//////////////////////////////////////////////////
// LOAD THE ARTICLES
//////////////////////////////////////////////////
```

`Drupal.Commenting.InlineComment` wants a space after `//` → the rule line
becomes `// ////////…`, which then trips the "must start with a capital" and
"must end with a full stop" rules, which the next pass undoes. Infinite.

**Fix:** replace the whole banner with the single ordinary comment it stood for.

```php
// Load the articles.
```

### 2. Large blocks of commented-out PHP

```php
// $query = $this->database->select('node', 'n');
//   $query->condition('type', 'article');
//     $result = $query->execute();
```

The fixer reads each line as a continuation of the one above and fights over
indentation forever.

**Fix:** delete the dead code. No amount of reformatting makes commented-out PHP
compliant, and it is in git history anyway. Read it first — if it documents
something real, turn that into one sentence of comment and delete the rest.

### Others worth knowing

- A docblock immediately followed by a `#[Attribute]` or an annotation the
  fixer wants to re-indent.
- Heredoc/nowdoc bodies near a `ScopeIndent` violation — the fixer counts the
  heredoc content as code.
- Files with mixed line endings (CRLF): normalize to LF first, in its own commit.

## The unblocking procedure

```bash
# 1. Which files were discarded
make phpcbf c='web/modules/custom/<module>' 2>&1 | grep 'FAILED TO FIX'

# 2. For each one, look at what the fixers are fighting over
make phpcs c='web/modules/custom/<module>/src/Bar.php --report=source'
```

Then, in order:

1. **Hand-edit the blockers** in that file — banners, commented-out code — and
   commit that as its own step (`style(<module>: #<ticket>): unblock the comment
   fixer in Bar.php`). It makes a confusing diff readable.
2. **Re-run phpcbf on that single file.** If it converges, done.
3. **If it still fails, run one sniff at a time.** Each sniff converges alone
   even when the full set does not:

```bash
make phpcbf c='--sniffs=Drupal.WhiteSpace.ScopeIndent web/modules/custom/<module>/src/Bar.php'
make phpcbf c='--sniffs=Drupal.Commenting.InlineComment web/modules/custom/<module>/src/Bar.php'
make phpcbf c='--sniffs=Drupal.Commenting.DocComment web/modules/custom/<module>/src/Bar.php'
```

Take the sniff names straight from `--report=source` output — it prints the
exact identifiers.

4. **If a single sniff still fails on a single file**, fix that file by hand.
   One file is not worth more tooling.

## Verify, always

```bash
make shell
php -l web/modules/custom/<module>/src/Bar.php
exit
make phpcs c='web/modules/custom/<module>'   # No violations were found
```

`git diff` the unblocking commit before moving on: deleting commented-out code
is the one step of this skill that can delete something live by accident.
