# Screenshots — Chrome for the comparison, Playwright for the MR

Two tools, two jobs. Do not mix them.

| Tool | Job | When | Output |
|---|---|---|---|
| **Claude in Chrome** | Explore and **compare with Figma**: hover, focus, resize on the fly, read computed styles. | Unit Step 7, while fixing | Nothing kept |
| **Playwright** (`make screenshots unit=<id>`) | The MR captures, identical from one machine and one run to the next. | Unit Step 9 | `.build/screenshots/<id>/` |

Visual regression (`toHaveScreenshot`) is a third, separate use: versioned
reference captures that fail a test (`references/testing.md`).

## Comparing with Figma (Step 7)

1. Load the Chrome tools in one `ToolSearch` call (`claude-in-chrome` skill
   first), open a new tab on the demo page from `/styleguide/demo`.
2. For each row of the unit brief's **Figma nodes** table: `get_screenshot` of
   that node id only, resize the window to the breakpoint, put the page in the
   same state (hover, focus with Tab, menu open, form error), compare.
3. Check in order: layout and alignment, spacing, typography (family, size,
   weight, line height), colours, radii and shadows, icons, then behaviour.
   Read computed styles with `javascript_tool` when the eye hesitates:
   `getComputedStyle(el).fontSize`.
4. Fix the gap with **tokens**, never with an arbitrary value. A gap that a
   token cannot express is either a missing token (add it in the theme, say so
   in the MR) or a Figma inconsistency (record it in the brief, keep the
   token).

Never upload a Chrome screenshot to the MR: the MR captures come from
Playwright only.

## `make screenshots unit=<id>`

Runs in the `playwright` container (target in `references/testing.md`) with
its own config, so captures never mix with the visual references.

`tests/screenshots/playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';
import base from '../../playwright.config';

export default defineConfig({
  ...base,
  testDir: '.',
  testMatch: 'capture.spec.ts',
  workers: 1,
  projects: base.projects,
});
```

`tests/screenshots/units/<unit-id>.ts` — one manifest per unit, written in
the unit's Step 9:

```ts
import type { Shot } from '../capture.spec';

export const shots: Shot[] = [
  { name: 'page', path: '/demo/paragraph-faq', fullPage: true },
  { name: 'block', path: '/demo/paragraph-faq', selector: '.paragraph--type--faq' },
  {
    name: 'item-open',
    path: '/demo/paragraph-faq',
    selector: '.paragraph--type--faq',
    state: async (page) => page.getByRole('button').first().click(),
  },
  {
    name: 'focus',
    path: '/demo/paragraph-faq',
    selector: '.paragraph--type--faq',
    state: async (page) => {
      await page.keyboard.press('Tab');
      await page.getByRole('button').first().focus();
    },
  },
];
```

`tests/screenshots/capture.spec.ts`:

```ts
import { test, type Page } from '@playwright/test';
import { isolate } from '../e2e/helpers';

export type Shot = {
  name: string;
  path: string;
  selector?: string;
  fullPage?: boolean;
  state?: (page: Page) => Promise<unknown>;
};

const unit = process.env.UNIT!;
const { shots } = (await import(`./units/${unit}.ts`)) as { shots: Shot[] };

for (const shot of shots) {
  test(shot.name, async ({ page }, info) => {
    await isolate(page);
    await page.goto(shot.path);
    await page.evaluate(() => document.fonts.ready);
    if (shot.state) await shot.state(page);
    const target = shot.selector ? page.locator(shot.selector).first() : page;
    await target.screenshot({
      path: `.build/screenshots/${unit}/${info.project.name}-${shot.name}.png`,
      fullPage: shot.fullPage,
      animations: 'disabled',
    });
  });
}
```

What to capture, per breakpoint retained in `state.md`:

- the full demo page, and the component alone;
- the useful states: hover, focus, open menu, form error, empty optional
  fields, maximal content;
- for foundations: each `/styleguide` section.

Keep it to what a reviewer needs: one image per state that the UAT names.

## Upload to GitLab

The files stay local in `.build/screenshots/` (never committed). Upload each
image to the project, then embed the returned markdown in the MR description:

```bash
for f in .build/screenshots/<id>/*.png; do
  glab api --method POST projects/:id/uploads -F "file=@$f" | grep -o '"markdown":"[^"]*"'
done
```

`:id` is resolved by `glab` from the current repository. Each response's
`markdown` field (`![desktop-page](/uploads/<hash>/desktop-page.png)`) goes in
the description as is: the path is relative to the project, it renders in the
MR.

Lay them out per breakpoint, in French:

```markdown
## Captures

| | Mobile (375) | Tablette (768) | Desktop (1440) |
|---|---|---|---|
| Page | ![](/uploads/…/mobile-page.png) | ![](/uploads/…/tablet-page.png) | ![](/uploads/…/desktop-page.png) |
| Élément ouvert | ![](/uploads/…/mobile-item-open.png) | … | … |
| Focus | … | … | … |
```

Upload before opening the MR, so the description is complete in one go. If
the MR already exists, update it: `glab mr update <iid> --description "$(cat <file>)"`.
