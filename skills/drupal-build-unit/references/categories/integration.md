# Category — integration

Unit ids `integration-<slug>`, branch `build/integration-<slug>`. **One
third-party service per unit**: analytics (Matomo, GA), consent tool
(tarteaucitron, an EU CMP), mailer API (transactional e-mail provider), an
external script imposed by the client (group footer, chat widget), search
console or other verification tags. Depends on `foundations`; on the consent
unit when the service needs consent; built before the unit that needs it.

## Deliverables

- **The integration itself**, through a contrib module when a maintained one
  exists, otherwise a small service in a custom module (HTTP client
  injected, timeouts, errors logged without personal data).
- **Configuration and secrets**: keys, site ids and endpoints come from
  environment variables (`.env`, read in `settings.php`), never from
  `config/sync`. Add the variables to `.env.example` with an empty value. In a
  multisite, one value per site.
- **Consent**: a script that sets cookies or tracks loads only after consent,
  through the project's consent tool; the « gérer les cookies » link reopens
  it. Opt-out widgets the CDC requires (analytics opt-out in the privacy page)
  are placed where the editor can move them (a block or an embed the text
  format allows).
- **Environments**: what runs locally (mailer to Mailpit through the same
  transport interface, analytics disabled or pointed at a test site), what
  only runs on servers. Production-only behaviour is guarded by `APP_ENV`, not
  by commenting code.
- **Production prerequisites** in the MR: the accounts, keys, DNS or
  verification steps someone must do outside the code, per environment and
  per site. The skill never does them and never writes them to a server.

## Control points

- No secret in git, in config, in logs or in the MR.
- The site works when the service is down or slow (timeouts, graceful
  fallback, the form still answers the user).
- External scripts are loaded with the attributes the provider documents
  (`async`/`defer`), through a Drupal library, not hard-coded in a template;
  CSP or SRI if the project uses them.
- Personal data sent to the service matches the privacy policy.

## Tests

- Kernel test for any custom service (request built correctly, error
  handling), with the HTTP client mocked. Never a real call in a test.
- E2E: external hosts are **blocked or stubbed** in Playwright (see
  `testing.md`), and the test checks the integration's local side: the
  consent gate, the opt-out widget's placeholder, the mail in Mailpit.
- What can only be verified on a server goes to the UAT, marked « après
  déploiement, par l'équipe » (never content created there by us).

## Contract

The env variables and their meaning, the service id and its public methods,
the library ids, the consent service name, what to call from another unit
(the form unit calls the mailer through the core mail manager or the
transport, not the provider's API).

## Demo

Usually none; a page that shows the integration's placeholder when it has a
visible part (opt-out widget, consent placeholder).
