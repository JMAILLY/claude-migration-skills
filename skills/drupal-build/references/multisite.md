# Multisite — one codebase, one theme, one database per site

Applies when the intake recorded `sites:` in `state.md`. Every site shares the
code, the custom modules, the theme and `config/sync`; each has its own
database, its own content, and its own values for the config listed in
`config_ignore`. The units are built once, for every site.

## What the intake records

```markdown
sites: site_a (driver, site-a.dev.localhost) · site_b (site-b.dev.localhost)
per-site config: gm_site.settings, system.site, <the gm_* settings> (config_ignore, D-006)
palette: per site — taxonomy `palette`, defaults from Figma (D-007)
```

The **driver site** is the one each unit is built and compared with Figma on;
the others are verified, not rebuilt.

## Layout

- `web/sites/<site>/settings.php` and `services.yml` per site,
  `web/sites/sites.php` mapping each local and production host to its
  directory. Database names per site in `.env` (`MYSQL_DATABASE_<SITE>`), or
  one database server with one schema per site.
- One `config/sync` for all sites. What must differ per site goes to
  `config_ignore` (config entries, wildcards allowed), decided in the intake.
  Content (terms, nodes, menus links) differs by nature: it is not config.
- The config splits (`dev`, `preprod`, `prod`) stay shared: `gm_demo` is
  enabled locally on every site.
- The Makefile follows the `lando-to-docker` convention: `SITE ?= <driver>`,
  `DRUSH = … vendor/bin/drush --uri=$(SITE)`, `SITES = site_a site_b`, and an
  `-all` variant for the targets that must run everywhere (`cim-all`,
  `cr-all`, `demo-all`). If the starter's Makefile is single-site, this
  conversion is part of the foundations MR.

## Config: what never to do

- A config entry in `config_ignore` is **not exported** by `make cex` on the
  site where it changed, and not imported elsewhere. A unit that adds config
  a site must own goes to `config_ignore` in the same MR, with a deploy step
  that sets its initial value on each site (update hook), listed in the MR.
- Never `make cex` on a site other than the driver: config that drifted on
  that site would overwrite `config/sync` for every site.
- `make cim-all` after each unit: a config change must import cleanly on
  every site, not only the driver.

## Per-site content and fixtures

- Each site has its own demo data: `make demo SITE=<site>` (or `demo-all`).
  Shared fixtures in `fixtures/<unit>.yml`; site-specific entities (palette
  terms, site name, menus) in `fixtures/sites/<site>/<unit>.yml`, merged into
  the unit by the generator (`demo-content.md`).
- The palette fixture of each site uses that site's colours, so the visual
  references prove the per-site theming works.

## Tests and captures

- Playwright: one `BASE_URL` per site. The config adds a project per site ×
  breakpoint (`site_a-desktop`), reading the sites from an env variable
  (`E2E_SITES=site_a=https://site-a.dev.localhost,site_b=…`).
- Visual references are per site: the same page on two palettes is two
  references.
- `make test-all` covers every site before delivery; the MR captures cover
  the driver site, plus one capture per other site for anything the palette
  or the per-site config changes.

## In each unit

- Built and compared with Figma on the driver site.
- Self-verification adds: `make cim-all`, `make demo-all`, `make test-all`
  on every site.
- The UAT names the site for each line, and has one line per other site for
  what differs per site.
- The Contract lists any config the unit put under `config_ignore`.
