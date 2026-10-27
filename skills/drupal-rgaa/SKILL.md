---
name: drupal-rgaa
description: >
  RGAA accessibility check of a Drupal component or page on its real
  rendering, returning a French verdict per criterion (conforme, non
  conforme, non applicable) with evidence and the blocking points to fix.
  Initial version: the Drupal-specific checklist is under construction, so it
  applies the RGAA 4.1.2 criteria relevant to the component (keyboard, focus
  visible, contrast, text alternatives, heading structure, form labels, 200 %
  zoom, 320 px reflow, landmarks, status messages, moving content), checked
  in Chrome. Its call contract is frozen so its content can grow without
  touching the skills that call it. Use when drupal-build-unit or
  drupal-build-foundations reaches its end validations, or when the user asks
  for an RGAA / accessibility check of a Drupal page or component.
  IMPORTANT: it checks the rendered page, never the templates alone; axe is
  an input, not the verdict.
---

# Drupal RGAA check

**Status: initial version.** The Drupal-specific checklist (core and contrib
markup pitfalls, Paragraphs, Views, Webform, media, CKEditor content) is under
construction. Until it exists, this skill applies the **RGAA 4.1.2** criteria
that fit the component, using the procedure below. Only this file changes as
it grows; the contract does not.

## Call contract (frozen)

**Input** — given by the caller, asked if missing:

| Field | Example |
|---|---|
| `unit` | `paragraph-faq` |
| `category` | `foundations`, `header`, `footer`, `recurring`, `media`, `paragraph-block`, `taxonomy`, `content-type`, `integration`, or `page` |
| `pages` | local URLs of the demo pages (`/demo/paragraph-faq`, `/styleguide#buttons`) |
| `breakpoints` | from `.build/state.md` (`375, 768, 1440`) |
| `scope` | optional CSS selector of the component; the whole page otherwise |

**Output** — in French, ready to paste in the MR:

```markdown
## RGAA — <unit>

Verdict : conforme | non conforme (<n> bloquants)
Référentiel : RGAA 4.1.2 (critères applicables au composant) — checklist Drupal en construction.

| Critère | Statut | Preuve / remarque | Bloquant |
|---|---|---|---|
| 7.3 Composants contrôlables au clavier | C | Entrée/Espace ouvrent l'élément, Échap ferme | — |
| 10.7 Focus visible | NC | Bouton « Fermer » : contour 1 px, ratio 1.9:1 sur fond gris | oui |
| 5.x Tableaux | NA | Aucun tableau | — |
```

`C` conforme, `NC` non conforme, `NA` non applicable. **Bloquant** = a
non-conformity on a criterion the unit is responsible for. Return the list
of blocking points first, each with the fix to make; the caller fixes them
and calls again with the same input.

## Procedure

Load the `claude-in-chrome` skill and the Chrome tools in one `ToolSearch`
call. For each page, at each breakpoint:

1. **axe first** (already in `make test-e2e`): read its result for the pages.
   Each violation is a lead, mapped to its RGAA criterion; absence of
   violations proves little.
2. **Keyboard**: Tab through the scope from the address bar. Every
   interactive element is reachable, in a logical order, operable (Enter,
   Space, arrows where the pattern expects them, Escape closes), never
   trapped; nothing receives focus while hidden.
3. **Focus visible** on every focusable element, contrast of the indicator
   ≥ 3:1 against its background.
4. **Contrast**: text 4.5:1 (3:1 large), UI components and meaningful icons
   3:1 — computed on the rendered colours (`getComputedStyle`), including
   hover, focus, disabled and error states, and text over images. Colours the
   editor picks from a palette are reported as « dépend de la contribution »
   with the decision of `decisions.md`; only the default pairs and the pairs
   of the demo content can be blocking.
5. **Text alternatives**: informative images and icons have a relevant
   alternative; decorative ones are hidden (`alt=""`, `aria-hidden`); icon-only
   buttons and links have an accessible name.
6. **Structure**: heading outline without jumps that break the page's
   hierarchy, one `h1` per page; landmarks (`header`, `nav` with distinct
   labels, `main`, `footer`); lists marked as lists.
7. **Forms**: every field has a label tied to it, required fields indicated
   in text, errors tied to fields and summarised, `autocomplete` on personal
   data fields, status messages announced.
8. **Zoom 200 %** (text): no loss of content or function.
9. **Reflow at 320 px** width: no horizontal scroll, except content that
   needs two dimensions (tables, maps).
10. **Motion and time**: moving or auto-updating content can be paused;
    `prefers-reduced-motion` honoured.
11. **Language**: `lang` on the page, `lang` on any passage in another
    language (language switcher included).

## RGAA 4.1.2 criteria by category

Apply the rows of the category; add any other criterion the component
obviously touches, and the criteria of the unit's `a11y` requirements (a
design accessibility checklist lands there in the intake). Numbers per RGAA 4.1.2 — check the wording against the
official reference (accessibilite.numerique.gouv.fr) when in doubt.

| Category | Criteria |
|---|---|
| Every unit | 3.2 and 3.3 (contrasts), 7.1 (scripts and assistive tech), 7.3 (keyboard), 10.4 (zoom 200 %), 10.7 (focus visible), 10.11 (reflow 320 px), 10.12 (text spacing), 12.8 (tab order), 12.9 (no keyboard trap) |
| foundations | 1.1–1.3 (icons), 3.1 (colour alone), 9.1 (headings), 9.3 (lists), 9.4 (quotes), 10.1 (CSS layout), 11.1, 11.2, 11.10, 11.11 (forms), 7.5 (messages) |
| header | 6.1, 6.2 (links), 8.7 (language changes), 9.2 (structure), 12.6 (landmarks), 12.7 (skip links), 10.13 (content on hover/focus), 11.1 (search label) |
| footer | 6.1 (link purpose, new window mentioned when used), 6.2, 9.2, 12.6, 1.2 (decorative logos) |
| recurring | 1.1–1.3 (images), 6.1, 6.2 (card links), 11.1–11.13 (forms), 7.4 (context changes), 7.5 (status messages), 13.1 (time limits) for banners and forms |
| paragraph-block | 1.1–1.3, 4.x (media: captions, transcript, controls), 5.x (tables in rich text), 9.1, 9.3, 10.13, 13.8 (moving content: carousels) |
| media | 1.1–1.3 (alternatives, pictograms decorative by default), 4.1–4.13 (audio and video: transcript, captions, controls, no autoplay), 2.1, 2.2 (iframe titles), 6.1 (document links: format and size) |
| integration | 7.1, 7.3 (consent tool and widgets by keyboard), 12.8, 13.1, 13.8 (third-party widgets that move or time out) |
| taxonomy | 6.1, 9.1, 9.3, 11.1 (filters) |
| content-type | 8.5, 8.6 (page title), 8.3 (default language), 9.1, 9.2, 1.1 (media), 5.x, 11.x (exposed filters), 7.5 (result counts), 12.1 (two ways to reach a page) |

## Under construction — Drupal checklist

The checks to add here, as they are confirmed on real builds:

- core markup that fails by default and the template to override;
- Paragraphs and CKEditor content an editor can break (heading levels, empty
  links, images without alt);
- Views exposed filters, pagers and AJAX announcements;
- Webform and Form API error handling;
- media library and responsive images;
- the admin forms an editor uses (when the CDC puts the back office in
  scope).
