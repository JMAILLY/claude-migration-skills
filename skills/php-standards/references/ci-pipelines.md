# CI pipelines: phpcs and phpstan in GitLab, Sonar reports, deploy

This is the agency's GitLab setup. It adds two jobs that run phpcs and phpstan
on the deploy branches and turn their JSON output into SonarQube "external
issues" reports, plus everything around them that has to change so they work
and do not leak into the deploy.

## 0. Ask first

Ask these together, before writing any YAML:

1. **Which branches?** The usual answer is the deploy branches only
   (`release` + `master`/`main`). Adding the integration branch (`develop`)
   creates pipelines on a branch that may have none today. Say that plainly.
2. **Report-only or gating?** The agency template runs each tool with
   `|| true`, so **the jobs never fail on a violation**. They only fail when
   the tool is missing or the converter crashes. If the code is now clean,
   offer to drop the `|| true` so a regression fails the pipeline (and, since
   `syntax` runs before `deploy`, blocks the deploy).
3. **Sonar now, or later?** The converters and `sonar-project.properties` do
   nothing on their own (section 5). Only add the scanner job if the user
   asks and the Sonar variables exist.

## 1. Read the existing pipeline before adding anything

```bash
grep -n 'composer install' .gitlab-ci.yml
grep -n -A8 '^deploy' .gitlab-ci.yml        # its dependencies: list
```

**The question: does the CI `vendor/` ship?** The QA jobs need `require-dev`
(`vendor/bin/phpcs`, `vendor/bin/phpstan`). Whether the existing composer job
can provide it depends on what the deploy does with that `vendor/`:

```bash
grep -n -E "upload_vendors|exclude=/vendor|composer_options|deploy:vendors" deploy.php
```

- **The server rebuilds `vendor/` (the agency default).** Deployer's
  `deploy:vendors` runs `composer install --no-dev` in the release, and the
  upload either excludes `/vendor` (`upload_vendors` false) or rsyncs it and
  lets that install prune the dev packages. The CI `vendor/` only runs
  `vendor/bin/dep` on the runner. **Drop `--no-dev` from the existing composer
  job and point the QA jobs at it.** A second install job would only cost a
  full `composer install` per pipeline and protect nothing.
- **The CI `vendor/` is what runs in production** (no install on the server,
  or a server install without `--no-dev`). Keep `--no-dev` on that job, or
  phpstan, coder and the rest of `require-dev` ship. Add a separate
  `composer_qa` install for the QA jobs instead (section 2, variant B).

Either way, copying the QA jobs onto a `--no-dev` artifact gives
`vendor/bin/phpcs: not found`.

Also check the stage list. The template uses a `syntax` stage between `build`
and `deploy`; add it if it is missing.

## 2. The jobs

Match the project's existing style: runner `tags:`, per-environment job
suffixes (`_prod`, `_preprod`) and the `only:`/`rules:` syntax. Below is the
untagged, single-job form.

Variant A, the default (section 1, the server rebuilds `vendor/`): the existing
composer job, with `--no-dev` removed and the contrib directories added to its
artifacts.

```yaml
composer:
  stage: preparation
  # ...existing keys...
  script:
    # Dev dependencies are installed on purpose: phpcs and phpstan come from
    # this vendor/. It never ships, since deploy.php excludes it from the upload
    # and the server runs its own composer install --no-dev.
    - composer install --optimize-autoloader --no-ansi --no-interaction --no-progress --no-scripts
  artifacts:
    paths:
      - vendor/
      - web/core/
      # phpstan-drupal resolves contrib classes from these.
      - web/modules/contrib/
      - web/themes/contrib/
      # ...existing paths (scaffold files, etc.)...

phpcs:
  stage: syntax
  only:
    - release
    - master
  dependencies:
    - composer
  script:
    - mkdir -p qa-reports
    - vendor/bin/phpcs --config-set installed_paths "vendor/drupal/coder/coder_sniffer,vendor/slevomat/coding-standard"
    - vendor/bin/phpcs --standard=phpcs.xml --report=json --report-file=qa-reports/phpcs-report.json || true
    - cp qa-reports/phpcs-report.json qa-reports/phpcs-report-sonar.json
    - php phpcs2sonar.php qa-reports/phpcs-report-sonar.json
  artifacts:
    paths:
      - qa-reports/phpcs-report.json
      - qa-reports/phpcs-report-sonar.json
    expire_in: 1 hour
  allow_failure: false

phpstan:
  stage: syntax
  only:
    - release
    - master
  dependencies:
    - composer
  script:
    - mkdir -p qa-reports
    - vendor/bin/phpstan analyse --configuration=phpstan.neon --no-progress --memory-limit=512M --error-format=json > qa-reports/phpstan-report.json || true
    - cp qa-reports/phpstan-report.json qa-reports/phpstan-report-sonar.json
    - php phpstan2sonar.php qa-reports/phpstan-report-sonar.json
  artifacts:
    paths:
      - qa-reports/phpstan-report.json
      - qa-reports/phpstan-report-sonar.json
    expire_in: 1 hour
  allow_failure: false
```

Variant B, only when the CI `vendor/` ships: leave the composer job alone and
add a dedicated install, then use `composer_qa` in the QA jobs' `dependencies:`.

```yaml
# Quality checks get their own install: the composer job runs --no-dev, and its
# vendor/ is the one that ships, so phpcs and phpstan cannot come from it.
composer_qa:
  stage: preparation
  only:
    - release
    - master
  script:
    - composer install --optimize-autoloader --no-ansi --no-interaction --no-progress --no-scripts
  artifacts:
    paths:
      - vendor/
      - web/core/
      - web/modules/contrib/
      - web/themes/contrib/
    expire_in: 1 hour
    when: always
```

Why each piece is there:

- The install artifacts include `web/core/` because phpstan-drupal needs a
  Drupal root, and the contrib directories so that phpstan-drupal discovers
  the same extensions as locally.
- The QA jobs list **only** the install job in `dependencies:`, so they do not
  pull `.env` or `settings.php` artifacts they have no use for.
- `--config-set installed_paths` is redundant when the dealerdirect installer
  ran, but harmless. Keep it: it is what makes the job work on a runner image
  whose Composer skipped the plugins.
- `--no-suggest` appears in older templates. It is deprecated in Composer 2;
  drop it.
- Gating version: delete `|| true` on the tool lines and keep the converter
  lines. phpcs exits 1 on warnings too unless `-n` is passed; match the
  severity the user chose for the cleanup.

## 3. The converter scripts

Both scripts go at the repo root, outside the scanned paths, so phpcs and
phpstan do not analyse them. They rewrite the JSON report in place into
Sonar's generic external-issues format. A clean report converts to
`{"issues": []}`.

`phpcs2sonar.php`:

```php
#!/usr/bin/env php
<?php
/**
 * Transforms PHPCS json report file to custom issues report for SonarQube
 */

const SONARQUBE_DEFAULT_EFFORT_MINUTES_ERROR = 10;
const SONARQUBE_DEFAULT_EFFORT_MINUTES_WARNING = 5;
const SONARQUBE_DEFAULT_END_COLUMN = 1;
const SONARQUBE_DEFAULT_START_COLUMN = 0;
const SONARQUBE_DEFAULT_LINE = 1;
const SONARQUBE_ENGINE_ID = 'PHPCS';
const SONARQUBE_SEVERITY_ERROR = 'MAJOR';
const SONARQUBE_SEVERITY_WARNING = 'MINOR';
const SONARQUBE_TYPE_ERROR = 'BUG';
const SONARQUBE_TYPE_WARNING = 'CODE_SMELL';
const FILENAME_PATHS_TO_REMOVE = [];

$reportFilePath = $argv[1];

try {
  $reportData = file_get_contents($reportFilePath);

  if (false === $reportData) {
    throw new Exception('Cannot read file ' . $reportFilePath);
  }

  $decodedData = json_decode($reportData, true);

  if (false === $decodedData) {
    throw new Exception('Cannot decode json content from file ' . $reportFilePath);
  }

  if (!isset($decodedData['files'])) {
    throw new Exception('Wrong PHPCS report format in file ' . $reportFilePath);
  }

  $issues = [];

  foreach ($decodedData['files'] as $fileName => $fileInfo) {
    $fileName = preg_replace(FILENAME_PATHS_TO_REMOVE, '', $fileName);

    if (empty($fileInfo['messages'])) {
      continue;
    }

    foreach ($fileInfo['messages'] as $message) {
      $isError = strtoupper($message['type']) === 'ERROR';

      $issue = [
        'engineId'      => SONARQUBE_ENGINE_ID,
        'ruleId'        => $message['source'] ?? 'PHPCS.Generic.Rule',
        'type'          => $isError ? SONARQUBE_TYPE_ERROR : SONARQUBE_TYPE_WARNING,
        'effortMinutes' => $isError ? SONARQUBE_DEFAULT_EFFORT_MINUTES_ERROR : SONARQUBE_DEFAULT_EFFORT_MINUTES_WARNING,
        'severity'      => $isError ? SONARQUBE_SEVERITY_ERROR : SONARQUBE_SEVERITY_WARNING,
      ];

      $issue['primaryLocation'] = [
        'message'   => $message['message'],
        'filePath'  => $fileName,
        'textRange' => [
          'startLine'   => $message['line'] ?? SONARQUBE_DEFAULT_LINE,
          'endLine'     => $message['line'] ?? SONARQUBE_DEFAULT_LINE,
        ],
      ];

      $issues[] = $issue;
    }
  }

  $issuesData = json_encode(['issues' => $issues], JSON_PRETTY_PRINT);
  $bytes      = file_put_contents($reportFilePath, $issuesData);

  if (false === $bytes || $bytes !== strlen($issuesData)) {
    throw new Exception('Cannot write content to file ' . $reportFilePath);
  }

  echo 'PHPCS report has been successfully transformed to SonarQube format.' . PHP_EOL;
  exit(0);
} catch (Throwable $e) {
  echo 'Error: ' . $e->getMessage() . PHP_EOL;
  exit(1);
}
```

`phpstan2sonar.php`:

```php
#!/usr/bin/env php
<?php
/**
 * Transforms PHPStan json report file to custom issues report for SonarQube
 */

const SONARQUBE_DEFAULT_EFFORT_MINUTES_NON_IGNORABLE = 15;
const SONARQUBE_DEFAULT_EFFORT_MINUTES_IGNORABLE     = 5;
const SONARQUBE_DEFAULT_END_COLUMN                   = 1;
const SONARQUBE_DEFAULT_START_COLUMN                 = 0;
const SONARQUBE_DEFAULT_LINE                         = 1;
const SONARQUBE_ENGINE_ID                            = 'PHPSTAN';
const SONARQUBE_RULE_ID                              = 'PHPSTAN';
const SONARQUBE_SEVERITY_NON_IGNORABLE               = 'MAJOR';
const SONARQUBE_SEVERITY_IGNORABLE                   = 'MINOR';
const SONARQUBE_TYPE_NON_IGNORABLE                   = 'VULNERABILITY';
const SONARQUBE_TYPE_IGNORABLE                       = 'BUG';
const FILENAME_PATHS_TO_REMOVE                       = [];

$reportFilePath = $argv[1];

try {
  $reportData = file_get_contents($reportFilePath);

  if (false === $reportData) {
    throw new Exception('Cannot read file ' . $reportFilePath);
  }

  $decodedData = json_decode($reportData, true);

  if (false === $decodedData) {
    throw new Exception('Cannot decode json content from file ' . $reportFilePath);
  }

  if (!isset($decodedData['files'])) {
    throw new Exception('Wrong PHPStan report format in file ' . $reportFilePath);
  }

  $issues = [];

  foreach ($decodedData['files'] as $fileName => $fileInfo) {
    $fileName = preg_replace(FILENAME_PATHS_TO_REMOVE, '', $fileName);

    $primaryLocation = array_pop($fileInfo['messages']);

    $issue = [
      'engineId'      => SONARQUBE_ENGINE_ID,
      'ruleId'        => SONARQUBE_RULE_ID,
      'type'          => $primaryLocation['ignorable'] ? SONARQUBE_TYPE_IGNORABLE : SONARQUBE_TYPE_NON_IGNORABLE,
      'effortMinutes' => $primaryLocation['ignorable'] ? SONARQUBE_DEFAULT_EFFORT_MINUTES_IGNORABLE : SONARQUBE_DEFAULT_EFFORT_MINUTES_NON_IGNORABLE,
      'severity'      => $primaryLocation['ignorable'] ? SONARQUBE_SEVERITY_IGNORABLE : SONARQUBE_SEVERITY_NON_IGNORABLE,
    ];

    $issue['primaryLocation'] = [
      'message'   => $primaryLocation['message'],
      'filePath'  => $fileName,
      'textRange' => [
        'startLine'   => $primaryLocation['line'] ?? SONARQUBE_DEFAULT_LINE,
        'endLine'     => $primaryLocation['line'] ?? SONARQUBE_DEFAULT_LINE,
      ],
    ];

    foreach ($fileInfo['messages'] as $message) {
      $issue['secondaryLocations'][] = [
        'message'   => $message['message'],
        'filePath'  => $fileName,
        'textRange' => [
          'startLine'   => $message['line'] ?? SONARQUBE_DEFAULT_LINE,
          'endLine'     => $message['line'] ?? SONARQUBE_DEFAULT_LINE,
        ],
      ];

      if (!$message['ignorable']) {
        $issue['effortMinutes'] += SONARQUBE_DEFAULT_EFFORT_MINUTES_NON_IGNORABLE;
        $issue['severity']      = SONARQUBE_SEVERITY_NON_IGNORABLE;
        $issue['type']          = SONARQUBE_TYPE_NON_IGNORABLE;

        continue;
      }

      $issue['effortMinutes'] += SONARQUBE_DEFAULT_EFFORT_MINUTES_IGNORABLE;
    }

    $issues[] = $issue;
  }

  $issuesData = json_encode(['issues' => $issues]);
  $bytes      = file_put_contents($reportFilePath, $issuesData);

  if (false === $bytes || $bytes !== strlen($issuesData)) {
    throw new Exception('Cannot write content to file ' . $reportFilePath);
  }

  echo 'PHPStan report has been successfully transformed to SonarQube format.';
  exit(0);
} catch (Throwable $e) {
  echo $e->getMessage();
  exit(1);
}
```

## 4. Around the jobs

- **`.gitignore`**: add `/qa-reports/`.
- **Variant A: the contrib artifacts reach the deploy job.** It depends on the
  composer job, so it now receives `web/modules/contrib/` and
  `web/themes/contrib/`, and an rsync of the tree uploads them for nothing
  (the server install puts them back anyway). Add
  `--exclude=/web/modules/contrib` and `--exclude=/web/themes/contrib` next
  to `--exclude=/web/core` in `upload_options`.
- **Variant B: the deploy job's `dependencies:`** must **not** include
  `composer_qa`. Otherwise its dev `vendor/` overwrites the `--no-dev` one
  and ships.
- **What the deploy uploads.** The QA files (`phpcs.xml`, `phpstan.neon`, the
  two converters, `qa-reports/`) are tracked at the repo root, so a deploy
  that rsyncs the tree sends them to the servers. They sit outside the docroot,
  so this is housekeeping rather than exposure, but exclude them anyway. With
  Deployer's `upload_options`:

  ```php
  set('upload_options', function () {
    $options = [
      '--exclude=.git',
      // ...existing excludes...
      // CI quality tooling: only the phpcs/phpstan jobs use it.
      '--exclude=/phpcs.xml',
      '--exclude=/phpstan.neon',
      '--exclude=/phpcs2sonar.php',
      '--exclude=/phpstan2sonar.php',
      '--exclude=/qa-reports',
    ];
    // ...
  });
  ```

  Anchor each pattern with a leading `/`. An unanchored `phpcs.xml` would also
  exclude a contrib module's own copy. On a `git archive` or artifact-based
  deploy, use `.gitattributes` `export-ignore` instead.
- A `.rsyncignore` file is often vestigial. Check that something actually
  reads it before editing it.

## 5. SonarQube

`sonar-project.properties` is configuration for `sonar-scanner`. **On its own
it does nothing.** SonarQube never fetches a repository; an analysis only
appears when a scanner runs and pushes it. With only the jobs above, the
reports are GitLab artifacts that expire after an hour. If the user asks
whether "adding the properties is enough", the answer is no, unless something
outside the project's pipeline (a group-level or compliance pipeline) runs the
scanner. Check SonarQube for a recent analysis of a sibling project before
claiming either way.

The agency template, to copy as is and then extend `sonar.exclusions` with the
project's built assets and theme `node_modules`:

```properties
# Global code encoding
sonar.sourceEncoding=UTF-8

# External issue reports (converted in CI by phpstan2sonar.php and phpcs2sonar.php scripts)
sonar.php.phpstan.reportPaths=qa-reports/phpstan-report-sonar.json
sonar.php.phpstan.level=5
sonar.externalIssuesReportPaths=qa-reports/phpstan-report-sonar.json,qa-reports/phpcs-report-sonar.json

# Exclude some directories and files from analysis
sonar.exclusions=web/core/**,web/modules/contrib/**,web/themes/contrib/**,vendor/**,scripts/composer/**,web/sites/*/default.settings.php,web/sites/example.settings.local.php,drush/Commands/*.php

# PHP file suffixes
sonar.php.file.suffixes=.php,.module,.inc,.install,.theme,.profile

# Targeted deactivation of SonarQube rules that conflict with Drupal coding standards
# Reason: Drupal allows procedural hook functions using snake_case names in these file types.
sonar.issue.ignore.multicriteria=e1a,e1b,e1c,e1d,e1e,e1f,e2a,e3,e4a,e4b,e5a,e5b,e6,e7a,e7b,e7c,e7d,e7e,e8a,e8b,e9a,e9b,e10a,e10b,e11,e12a,e12b,e13a,e13b,e13c,e13d,e14a,e14b


# S100 - Function names (hooks snake_case)
sonar.issue.ignore.multicriteria.e1a.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1a.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e1b.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1b.resourceKey=web/modules/custom/**/*.install
sonar.issue.ignore.multicriteria.e1c.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1c.resourceKey=web/modules/custom/**/*.inc
sonar.issue.ignore.multicriteria.e1d.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1d.resourceKey=web/modules/custom/**/*.php
sonar.issue.ignore.multicriteria.e1e.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1e.resourceKey=web/themes/custom/**/*.inc
sonar.issue.ignore.multicriteria.e1f.ruleKey=php:S100
sonar.issue.ignore.multicriteria.e1f.resourceKey=web/themes/custom/**/*.theme

# S101 - Class names (plugins can dévier)
sonar.issue.ignore.multicriteria.e2a.ruleKey=php:S101
sonar.issue.ignore.multicriteria.e2a.resourceKey=**/src/Plugin/**/*.php

# S115 - Constant names (TRUE/FALSE/NULL en majuscules)
sonar.issue.ignore.multicriteria.e3.ruleKey=php:S115
sonar.issue.ignore.multicriteria.e3.resourceKey=web/**/custom/**

# S3776 - Cognitive Complexity (hooks verbeux)
sonar.issue.ignore.multicriteria.e4a.ruleKey=php:S3776
sonar.issue.ignore.multicriteria.e4a.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e4b.ruleKey=php:S3776
sonar.issue.ignore.multicriteria.e4b.resourceKey=web/modules/custom/**/*.install

# S110 - Inheritance tree depth (framework imposé)
sonar.issue.ignore.multicriteria.e5a.ruleKey=php:S110
sonar.issue.ignore.multicriteria.e5a.resourceKey=**/src/Plugin/**/*.php
sonar.issue.ignore.multicriteria.e5b.ruleKey=php:S110
sonar.issue.ignore.multicriteria.e5b.resourceKey=**/src/EventSubscriber/**/*.php

# S125 - Commented-out code (install/update)
sonar.issue.ignore.multicriteria.e6.ruleKey=php:S125
sonar.issue.ignore.multicriteria.e6.resourceKey=web/modules/custom/**/*.install

# S1781 - Identical functions (hooks fins) // PHP keywords and constants "true", "false", "null" should be lower case
sonar.issue.ignore.multicriteria.e7a.ruleKey=php:S1781
sonar.issue.ignore.multicriteria.e7a.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e7b.ruleKey=php:S1781
sonar.issue.ignore.multicriteria.e7b.resourceKey=web/modules/custom/**/*.install
sonar.issue.ignore.multicriteria.e7c.ruleKey=php:S1781
sonar.issue.ignore.multicriteria.e7c.resourceKey=web/sites/**/*.php
sonar.issue.ignore.multicriteria.e7d.ruleKey=php:S1781
sonar.issue.ignore.multicriteria.e7d.resourceKey=web/themes/custom/**/includes/*.inc
sonar.issue.ignore.multicriteria.e7e.ruleKey=php:S1781
sonar.issue.ignore.multicriteria.e7e.resourceKey=web/themes/custom/**/*.theme

# S107 - Too many parameters (signatures de hooks)
sonar.issue.ignore.multicriteria.e8a.ruleKey=php:S107
sonar.issue.ignore.multicriteria.e8a.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e8b.ruleKey=php:S107
sonar.issue.ignore.multicriteria.e8b.resourceKey=web/modules/custom/**/*.install

# S1186 - Empty methods/hooks (opt-in interfaces)
sonar.issue.ignore.multicriteria.e9a.ruleKey=php:S1186
sonar.issue.ignore.multicriteria.e9a.resourceKey=**/src/EventSubscriber/**/*.php
sonar.issue.ignore.multicriteria.e9b.ruleKey=php:S1186
sonar.issue.ignore.multicriteria.e9b.resourceKey=**/src/Plugin/**/*.php

# S1172 - Unused method parameters (hooks)
sonar.issue.ignore.multicriteria.e10a.ruleKey=php:S1172
sonar.issue.ignore.multicriteria.e10a.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e10b.ruleKey=php:S1172
sonar.issue.ignore.multicriteria.e10b.resourceKey=web/modules/custom/**/*.install

# S1451 - Missing file header (licence gérée au niveau projet)
sonar.issue.ignore.multicriteria.e11.ruleKey=php:S1451
sonar.issue.ignore.multicriteria.e11.resourceKey=web/modules/custom/**

# S1185 - Override fait juste parent() (annotations/DI)
sonar.issue.ignore.multicriteria.e12a.ruleKey=php:S1185
sonar.issue.ignore.multicriteria.e12a.resourceKey=**/src/Plugin/**/*.php
sonar.issue.ignore.multicriteria.e12b.ruleKey=php:S1185
sonar.issue.ignore.multicriteria.e12b.resourceKey=**/src/Controller/**/*.php

# S1192 - String literals should not be duplicated
sonar.issue.ignore.multicriteria.e13a.ruleKey=php:S1192
sonar.issue.ignore.multicriteria.e13a.resourceKey=web/modules/custom/**/*.php
sonar.issue.ignore.multicriteria.e13b.ruleKey=php:S1192
sonar.issue.ignore.multicriteria.e13b.resourceKey=web/modules/custom/**/*.module
sonar.issue.ignore.multicriteria.e13c.ruleKey=php:S1192
sonar.issue.ignore.multicriteria.e13c.resourceKey=web/themes/custom/**/includes/*.inc
sonar.issue.ignore.multicriteria.e13d.ruleKey=php:S1192
sonar.issue.ignore.multicriteria.e13d.resourceKey=web/themes/custom/**/*.theme

# S4833 - Use of namespaces should be preferred to "include" or "require" functions
sonar.issue.ignore.multicriteria.e14a.ruleKey=php:S4833
sonar.issue.ignore.multicriteria.e14a.resourceKey=web/themes/custom/**/*.theme
sonar.issue.ignore.multicriteria.e14b.ruleKey=php:S4833
sonar.issue.ignore.multicriteria.e14b.resourceKey=web/sites/**/*.php
```

When the user wants the analysis wired, the scanner job goes in a **later
stage than the QA jobs** and depends on them. Otherwise it never receives the
reports. An earlier agency template put it in `syntax`, depending only on
`env`, and analysed without the phpcs/phpstan reports.

```yaml
sonarqube:
  stage: test
  only:
    - release
    - master
  dependencies:
    - phpcs
    - phpstan
  image:
    name: sonarsource/sonar-scanner-cli:11
    entrypoint: [""]
  variables:
    SONAR_USER_HOME: "$CI_PROJECT_DIR/.sonar"
  cache:
    key: "sonar-cache-$CI_COMMIT_REF_SLUG"
    paths:
      - .sonar/cache
  script:
    - sonar-scanner -Dsonar.projectKey=$SONAR_PROJECT_KEY -Dsonar.host.url=$SONAR_HOST_URL -Dsonar.token=$SONAR_TOKEN -Dsonar.qualitygate.wait=true
```

- Variables `SONAR_HOST_URL`, `SONAR_TOKEN` (masked + protected) and
  `SONAR_PROJECT_KEY`. Check the GitLab group first: the host and the token are
  often defined there. A protected variable is empty on an unprotected branch.
- `-Dsonar.token`, not `-Dsonar.login` (deprecated since SonarQube 10).
- `sonar.qualitygate.wait=true` fails the job on a red gate, and that **blocks
  the deploy**. Ask whether that is wanted; otherwise use `allow_failure: true`
  or drop the flag.

## 6. Prove it before pushing

The runner cannot be exercised locally, but every script line can. Run them
inside the php container, which has the dev dependencies, writing the reports
to a throwaway directory instead of the repo:

```bash
docker compose ... exec -T php sh -c '
D=/tmp/qa && rm -rf $D && mkdir -p $D
vendor/bin/phpcs --standard=phpcs.xml --report=json --report-file=$D/phpcs-report.json || true
cp $D/phpcs-report.json $D/phpcs-report-sonar.json && php phpcs2sonar.php $D/phpcs-report-sonar.json
vendor/bin/phpstan analyse --configuration=phpstan.neon --no-progress --memory-limit=512M --error-format=json > $D/phpstan-report.json || true
cp $D/phpstan-report.json $D/phpstan-report-sonar.json && php phpstan2sonar.php $D/phpstan-report-sonar.json'
```

Both converters must print their success line. Then validate the YAML: run
`glab ci lint` when glab is authenticated, or at least parse the file (e.g.
`ruby -ryaml -e 'YAML.load_file(".gitlab-ci.yml")'`) and print each new job's
`stage` and `only`. Run `php -l` on `deploy.php`.

In the MR, say plainly that the jobs have **not run on GitLab yet**. They only
trigger on the deploy branches, so the first real run is the first
`release` pipeline. Put it in the UAT list.
