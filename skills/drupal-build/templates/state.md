# Build state

cdc: <path or URL> — read in full on YYYY-MM-DD, <n> pages
figma: <file URL> — file key <key>, style guide node <id>
breakpoints: mobile 375 · tablet 768 · desktop 1440 (D-003)
languages: fr (default) · en — asynchronous translation (D-001)
sites: - (or: site_a (driver, site-a.dev.localhost) · site_b (site-b.dev.localhost) — D-006)
palette: no (or: per site — taxonomy `palette`, defaults from Figma, D-007)
source: - (or: ~/path/to/source-site — blocks ported per unit brief)
integration: develop
plan: draft
gitlab: <namespace/project>

## Milestones (/gm:archi-c4)

- [ ] foundations
- [ ] header + footer
- [ ] recurring
- [ ] media
- [ ] taxonomy
- [ ] paragraph
- [ ] content
- [ ] integration

## Units

| id | category | depends | status | branch | MR | mode |
|---|---|---|---|---|---|---|
| foundations | foundations | - | planned | build/foundations | - | review |
| header | header | foundations | planned | build/header | - | review |
| footer | footer | foundations | planned | build/footer | - | review |
| recurring-palette | recurring | foundations | planned | build/recurring-palette | - | review |
| recurring-card | recurring | foundations | planned | build/recurring-card | - | review |
| media-image | media | foundations | planned | build/media-image | - | auto |
| taxonomy-themes | taxonomy | foundations | planned | build/taxonomy-themes | - | auto |
| paragraph-faq | paragraph | foundations | planned | build/paragraph-faq | - | auto |
| content-news | content | taxonomy-themes, recurring-card | planned | build/content-news | - | review |
