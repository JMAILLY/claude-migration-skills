# Decisions

## D-001 — Multilingual: asynchronous translation
Source: CDC p. 4 §1.3 (fr + en); mode confirmed by the human on YYYY-MM-DD.
Decision: each language owns its paragraphs (Paragraphs asymmetric translation); French is the default language.
Consequence: every fixture carries an `en` translation with its own paragraphs; host fields translatable, paragraph fields not synchronised.

## D-002 — CDC/Figma: news cards show the theme, not the author
Source: CDC p. 14 §3.2 lists theme; Figma card shows author.
Decision: CDC wins, the card shows the theme.
Consequence: card component variable `tag`, no `author`.

## D-003 — Breakpoints: mobile 375, tablet 768, desktop 1440
Source: CDC silent; Figma frames 375 and 1440; tablet proposed, validated YYYY-MM-DD.
Decision: Tailwind `md` = 48rem, `xl` = 90rem; tablet layouts derived from desktop.
Consequence: every unit tests and captures the three widths.

## D-004 — E2E and visual tests stay local
Source: test strategy, phase 1.
Decision: PHPUnit (unit + kernel) runs in CI; Playwright, axe and visual regression run locally in the `playwright` container.
Consequence: each MR reports its `make test-all` result; reference captures are regenerated only in that container.
