# Testing — levels, setup, templates

## What `/gm:ticket` brings, reused here

- **Explicit acceptance criteria**, each tied to a `REQ-xxx`. A criterion
  deduced rather than read in the CDC is marked « (inféré) ».
- **Bug discipline.** A bug found during the build (regression of a delivered
  unit, wrong behaviour) gets a **failing test that reproduces it first**, then
  one change at a time, with the three-attempt rule: after three failed fixes,
  stop and go back to the root cause (`shared/root-cause.md` of the GM plugin
  when installed).

## Levels

| Level | Tool | Tests | Write it |
|---|---|---|---|
| Unit | PHPUnit `UnitTestCase` | Pure PHP logic: `gm_site` / `gm_utils` services, computations, formatting. | As soon as a unit adds non-trivial PHP logic |
| Kernel | PHPUnit `KernelTestBase` | Drupal wiring: services, hooks, preprocess with logic, access rules, the `gm_demo` commands (idempotent generate, exact purge). | As soon as a unit adds a hook, a service or an access rule |
| E2E | Playwright | Per demo page and breakpoint: status 200, no console error, key elements present, interactions (mobile menu, accordion, carousel, form), keyboard navigation. | Always, at least one test per unit |
| Automatic a11y | `@axe-core/playwright` | Automatically detectable WCAG rules on every demo page. Complements `drupal-rgaa`, never replaces it. | Always |
| Visual regression | Playwright `toHaveScreenshot` | Reference captures per demo page, per breakpoint, and of `/styleguide`. Protects the delivered units. | Spec always; references only once the PO/client accepted the unit (below) |
| Manual UAT | MR description | Mockup fidelity, back-office editing, UX feel. | Always |

**No test for pure config** (a field exists, a paragraph type exists):
`make cim` and the E2E tests already cover it.

The plan of each unit maps **every acceptance criterion to the level that
verifies it** (unit Step 4).

## Setup — in the foundations MR

The starter ships `drupal/core-dev` but no `phpunit.xml`, no Playwright and no
test target. All of it is created once, in `build/foundations`.

### PHPUnit

Test database: SQLite when the php container has `pdo_sqlite` with SQLite ≥
3.45 (Drupal 11's minimum), else a dedicated MariaDB database.

```bash
make shell
php -r 'echo (new PDO("sqlite::memory:"))->query("select sqlite_version()")->fetchColumn(), PHP_EOL;'
exit
```

`phpunit.xml` at the root:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="web/core/tests/bootstrap.php"
         colors="true"
         cacheResult="false"
         failOnWarning="true"
         beStrictAboutOutputDuringTests="true">
  <php>
    <ini name="error_reporting" value="32767"/>
    <ini name="memory_limit" value="-1"/>
    <env name="SIMPLETEST_BASE_URL" value="http://apache"/>
    <env name="SIMPLETEST_DB" value="sqlite://localhost//tmp/drupal-test.sqlite"/>
    <env name="BROWSERTEST_OUTPUT_DIRECTORY" value="/tmp"/>
    <env name="SYMFONY_DEPRECATIONS_HELPER" value="disabled"/>
  </php>
  <testsuites>
    <testsuite name="unit">
      <directory>web/modules/custom/*/tests/src/Unit</directory>
      <directory>web/themes/custom/*/tests/src/Unit</directory>
    </testsuite>
    <testsuite name="kernel">
      <directory>web/modules/custom/*/tests/src/Kernel</directory>
      <directory>web/themes/custom/*/tests/src/Kernel</directory>
    </testsuite>
  </testsuites>
</phpunit>
```

With MariaDB instead: `mysql://drupal:drupal@db/drupal_test`, the database
created once with the root account of the `db` service (add a
`make test-db` target if the team needs it again).

Exclude `phpunit.xml` and `tests/` from the deploy upload
(`references/demo-content.md`, lock 2).

### Playwright service

Official image, in a Compose **profile** so `make up` never starts it. The
image tag and the `@playwright/test` version are **the same exact version**,
pinned in both places: a mismatch fails at launch, a floating tag changes the
reference captures.

```yaml
  playwright:
    image: mcr.microsoft.com/playwright:v1.56.1-noble
    profiles: [e2e]
    working_dir: /var/www/html
    volumes:
      - ./:/var/www/html
    environment:
      BASE_URL: https://${COMPOSE_PROJECT_NAME}.dev.localhost
      E2E_PROXY_HOST: ${E2E_PROXY_HOST:-traefik}
    ipc: host
    networks:
      - traefik-public
```

Pick the current Playwright release at setup time, never the example above.

**Chromium resolves every `*.localhost` name to loopback by itself**,
ignoring DNS, `/etc/hosts` and `extra_hosts`: inside the container that is the
container, not Traefik. The config maps the site's name to the Traefik
container on the shared network with `--host-resolver-rules`. Find its name
with `docker ps --filter network=traefik-public` and set `E2E_PROXY_HOST` in
`.env` when it is not `traefik`. Prove it on setup: the first test must reach
the site, not a connection refused.

`package.json` (the starter lists everything under `dependencies`; follow the
file's convention):

```json
"@playwright/test": "1.56.1",
"@axe-core/playwright": "4.11.0"
```

Install through `make npm-install`; the browsers come from the image.

`playwright.config.ts` at the root. The projects are **the breakpoints from
`.build/state.md`**:

```ts
import { defineConfig, devices } from '@playwright/test';

const breakpoints = { mobile: 375, tablet: 768, desktop: 1440 };

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: true,
  retries: 0,
  reporter: [['list']],
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: 'disabled', caret: 'hide' },
  },
  use: {
    baseURL: process.env.BASE_URL,
    ignoreHTTPSErrors: true,
    launchOptions: {
      args: [`--host-resolver-rules=MAP *.dev.localhost ${process.env.E2E_PROXY_HOST ?? 'traefik'}`],
    },
  },
  projects: Object.entries(breakpoints).map(([name, width]) => ({
    name,
    use: { ...devices['Desktop Chrome'], viewport: { width, height: 900 } },
  })),
});
```

E2E runs on Chromium only; other browsers are part of the manual UAT.

### Make targets

```make
DC_E2E = $(DC) --profile e2e run --rm playwright

test: ## Lance PHPUnit, unit + kernel, sans Xdebug (usage: make test [c='--testsuite unit'])
	$(DC) exec -e XDEBUG_MODE=off --user www-data $(PHP) vendor/bin/phpunit -c phpunit.xml $(c)

test-e2e: ## Lance Playwright : E2E, axe, régression visuelle (usage: make test-e2e [c='tests/e2e/header.spec.ts'])
	$(DC_E2E) npx playwright test $(c)

test-e2e-update: ## Met à jour les captures de référence — écart voulu uniquement (usage: make test-e2e-update c='<spec>')
	$(DC_E2E) npx playwright test --update-snapshots $(c)

test-all: ## PHPUnit puis Playwright
	$(MAKE) test
	$(MAKE) test-e2e

screenshots: ## Captures de MR d'une unité dans .build/screenshots/ (usage: make screenshots unit=<id>)
	@[ -n "$(unit)" ] || { echo "Usage: make screenshots unit=<id>"; exit 1; }
	$(DC) --profile e2e run --rm -e UNIT=$(unit) playwright npx playwright test -c tests/screenshots/playwright.config.ts
```

Add the names to `.PHONY`. E2E tests use the demo data set: `make demo`
runs before `make test-e2e` on a fresh database.

`XDEBUG_MODE=off` is required, not a speed-up: in `develop` mode Xdebug keeps
the frames of caught exceptions alive, a database transaction outlives its
kernel test, and PHPUnit dies at shutdown (« StatementPrefetchIterator …
null given »).

### CI

First read `.gitlab-ci.yml`: when the pipeline only runs on release or
production branches (no MR, no integration-branch pipeline), a PHPUnit job
would never run where it matters. Record that in `decisions.md` and skip the
job; the local `make test-all` before each delivery is the gate.

Otherwise PHPUnit (unit + kernel) joins the pipeline; E2E, axe, visual
regression and captures stay **local** (record it in `decisions.md`). Follow the existing
pipeline's style (`only:` or `rules:`) and image; the job needs the dev
dependencies:

```yaml
phpunit:
  stage: test
  script:
    - composer install --no-progress --no-interaction --prefer-dist
    - vendor/bin/phpunit -c phpunit.xml
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "develop"
```

Check that the CI image has `pdo_sqlite` (same command as above). Do not touch
the deploy jobs' `--no-dev` installs.

### Third-party hosts

Analytics, consent tools, video hosts and client-imposed scripts make tests
slow, flaky and noisy (console errors, layout shifts in captures). Every E2E
and capture run **blocks external hosts by default** and stubs the few a test
needs, in `tests/e2e/helpers.ts`:

```ts
export async function isolate(page: Page, allow: string[] = []): Promise<void> {
  await page.route(/^https?:\/\//, (route) => {
    const host = new URL(route.request().url()).hostname;
    const local = host.endsWith('.dev.localhost') && !host.endsWith('-vite.dev.localhost');
    return local || allow.includes(host) ? route.continue() : route.abort('blockedbyclient');
  });
}
```

The Vite dev server host is blocked too: when `APP_ENV=local` the theme
attaches the HMR client, which logs a CORS error whenever `npm-dev` is not
running. Tests run on the built assets (`make npm-build`).

Call it before `page.goto` in `open()`; filter the resulting
`net::ERR_BLOCKED_BY_CLIENT` lines out of the console errors. A test that
checks an integration's local side (consent placeholder, opt-out widget)
fulfils the external script with a stub (`route.fulfill({ body: '' })`)
rather than allowing the real host.

### Multisite

With `sites:` in `state.md`, follow `multisite.md`: one Playwright project per
site × breakpoint, references per site, `make test-all` on every site.

## Conventions

- One spec per unit: `tests/e2e/<unit-id>.spec.ts`; the reference captures
  live next to it (`<unit-id>.spec.ts-snapshots/`) and are versioned.
- **References come after acceptance.** A reference frozen before the PO or
  client accepted the unit freezes a rendering that may still change. Each
  spec carries `const ACCEPTED = false;` and its visual tests start with
  `test.skip(!ACCEPTED, 'awaiting PO/client acceptance')`. Once accepted, a
  follow-up commit flips the flag and adds the references
  (`make test-e2e-update c='<spec>'`). Unit delivery does not wait for it.
- Reference captures are created and updated **only in the `playwright`
  container** (`make test-e2e-update`), and only for an intended change: the
  commit body says « écart voulu » and why.
- Locators by role and accessible name first (`getByRole('button', { name })`):
  they test the accessibility contract at the same time.
- Wait for fonts before any capture; mask what changes between runs (dates
  relative to now, random order, autoplay).
- A failing test of a delivered unit is a regression of this unit's branch
  until proven otherwise.

### Shared helpers — `tests/e2e/helpers.ts`

```ts
import { expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

export async function open(page: Page, path: string, allow: string[] = []): Promise<string[]> {
  const errors: string[] = [];
  await isolate(page, allow);
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('ERR_BLOCKED_BY_CLIENT')) errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  const response = await page.goto(path);
  expect(response?.status(), path).toBe(200);
  await page.evaluate(() => document.fonts.ready);
  return errors;
}

export async function expectAccessible(page: Page, selector?: string): Promise<void> {
  let builder = new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']);
  if (selector) builder = builder.include(selector);
  const { violations } = await builder.analyze();
  expect(violations.map((v) => `${v.id} (${v.nodes.length}): ${v.help} — ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(', ')}`)).toEqual([]);
}

export async function tabThrough(page: Page, container: string, maxStops = 400): Promise<{ stops: number; missing: string[] }> {
  await page.locator('body').focus();
  const missing: string[] = [];
  const seen = new Set<string>();
  let stops = 0;
  for (let i = 0; i < maxStops; i++) {
    await page.keyboard.press('Tab');
    const state = await page.evaluate((selector) => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) return null;
      const id = `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}[${(el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 30)}]@${Math.round(el.getBoundingClientRect().top + window.scrollY)}`;
      const style = getComputedStyle(el);
      const visible = (style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0) || style.boxShadow !== 'none';
      return { id, inside: !!el.closest(selector), visible };
    }, container);
    if (!state || seen.has(state.id)) break;
    seen.add(state.id);
    if (!state.inside) continue;
    stops++;
    if (!state.visible) missing.push(state.id);
  }
  return { stops, missing };
}

export async function hideFloating(page: Page): Promise<void> {
  await page.evaluate(() => {
    for (const el of document.querySelectorAll<HTMLElement>('body *')) {
      if (['fixed', 'sticky'].includes(getComputedStyle(el).position)) el.style.visibility = 'hidden';
    }
  });
}
```

- `tabThrough` returns the number of stops inside the container: always
  assert a **minimum** (`expect(stops).toBeGreaterThan(n)`), otherwise a
  broken Tab loop that stops at once passes silently.
- `hideFloating` before any **element** capture: a sticky header or a
  floating editor toolbar otherwise lands in the middle of the image once
  the page scrolls to the element.

## Templates per unit category

Every spec has the same skeleton; the category adds its interactions.

```ts
import { test, expect } from '@playwright/test';
import { open, expectAccessible, hideFloating } from './helpers';

const ACCEPTED = false;
const PAGES = ['/demo/paragraph-faq', '/demo/paragraph-faq/long'];

for (const path of PAGES) {
  test.describe(path, () => {
    test('renders without error', async ({ page }) => {
      const errors = await open(page, path);
      await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible();
      expect(errors).toEqual([]);
    });

    test('is accessible (axe)', async ({ page }) => {
      await open(page, path);
      await expectAccessible(page, 'main');
    });

    test('matches the reference', async ({ page }) => {
      test.skip(!ACCEPTED, 'awaiting PO/client acceptance');
      await open(page, path);
      await hideFloating(page);
      await expect(page.locator('main')).toHaveScreenshot('main.png');
    });
  });
}
```

| Category | Interactions to cover |
|---|---|
| foundations | `/styleguide` 200 and axe; one capture per section (`#colors`, `#typography`, `#buttons`, `#forms`…); `tabThrough` reaches at least the expected number of interactive components, each with a visible focus. Demo node pages have no `h1` until `content-page`: check their first `h2` instead. |
| header | Skip link is the first Tab stop and moves focus to `main`; main menu reachable by keyboard; mobile menu opens and closes (button, `Escape`), `aria-expanded` toggles, focus stays inside while open and returns to the button; search submits; language switcher links to the translation. |
| footer | Menus and social links have accessible names; external links announced; legal links resolve (200); the consent link reopens the consent tool. |
| media | Each media type renders on its demo page; document size and format shown; audio player operable by keyboard; remote video shows its consent placeholder (external host blocked). |
| integration | Local side only, external hosts blocked or stubbed: consent gate before the script, opt-out widget placeholder, mail delivered to Mailpit with the expected recipient and body. |
| recurring | Card: the whole card is clickable through one link, title is the link text; 403 and 404 return their status and the custom template; cookie banner: focus, accept and refuse by keyboard, choice persisted; forms: required fields, error messages tied to fields (`aria-describedby`), success message. |
| paragraph-block | Every fixture case (minimal, maximal, long, empty optional fields); interactive blocks: accordion (Enter/Space, `aria-expanded`), tabs (arrow keys, `aria-selected`), carousel (pause control, no autoplay without it, keyboard). |
| taxonomy | Term page if the CDC has one (200, title, listing); filter by term on the listings that use it. |
| content-type | Full page, teaser and card displays on their demo pages; the Views listing (pagination, sort, exposed filters by keyboard); pathauto alias matches the pattern; metatags present (`title`, `description`, `og:*`, `hreflang` when multilingual). |

Kernel templates: one test class per service or hook that carries logic,
named after it (`NewsListBuilderTest`), with the smallest module list in
`$modules` that boots it.
