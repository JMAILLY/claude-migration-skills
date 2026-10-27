# Demo content — the `gm_demo` module

Demo content lives in a custom module, `gm_demo`, that exists **only on local
environments**. It is versioned (the team shares the fixtures, each unit MR
brings its own) and never delivered. The foundations MR creates it with its
locks; every later unit adds `fixtures/<unit>.yml` and, when needed, assets.

A module kept out of git (`.gitignore`) is the rejected alternative: fixtures
would be lost between branches and between machines.

## The three locks (plus one)

All of them ship in the foundations MR. Verify each one there.

1. **Config.** The module is enabled only through the `dev` config split
   (active when `APP_ENV=local`). It never appears in
   `config/sync/core.extension.yml`, so `make cim` elsewhere cannot enable it.

   ```yaml
   # config/sync/config_split.config_split.dev.yml (excerpt)
   module:
     devel: 0
     gm_demo: 0
   complete_list:
     - 'webform.webform.gm_demo_*'
   partial_list:
     - minifyhtml.config
     - user.role.anonymous
   ```

   Demo **config entities** (a webform an editor would build) carry the
   `gm_demo_` id prefix and are listed in `complete_list`, so `make cex`
   writes them to `config/dev/`, never to `config/sync`.

   `user.role.anonymous` is a **partial** split: the demo permission granted to
   anonymous lands in a patch under `config/dev/`, and the role in
   `config/sync` stays untouched. Never let a role depend on `gm_demo` in
   `config/sync`: config split would move the whole role out of sync.

2. **Deployment.** Excluded from the rsync upload in `deploy.php`, with the
   test tooling that never runs on a server:

   ```php
   '--exclude=/web/modules/custom/gm_demo',
   '--exclude=/tests',
   '--exclude=/phpunit.xml',
   '--exclude=/playwright.config.ts',
   ```

3. **Make.** `make demo` and `make demo-purge` refuse to run unless
   `APP_ENV=local` (targets below).

4. **Drush.** The commands themselves refuse when `APP_ENV` is not `local`:
   a direct `drush gm-demo:generate` on a server fails too.

Proof, in the foundations MR, after `make cim` and `make cex`:

```bash
grep -rn gm_demo config/sync && echo "LEAK" || echo "sync clean"
git diff --stat config/sync
make drush c='pm:list --status=enabled --filter=gm_demo'
```

## Layout

```
web/modules/custom/gm_demo/
├── gm_demo.info.yml
├── gm_demo.permissions.yml
├── gm_demo.routing.yml
├── gm_demo.services.yml
├── gm_demo.module
├── assets/                  # placeholders: landscape-1600x900.jpg, portrait-900x1200.jpg, square-1000.jpg, wide-2400x800.jpg, logo.svg, pictogram.svg, document.pdf, audio.mp3
├── fixtures/                # one file per unit: foundations.yml, paragraph-faq.yml…
│   └── sites/<site>/        # multisite: entities of one site only (palette, menus), merged into the unit
├── src/
│   ├── DemoGenerator.php
│   ├── Controller/StyleguideController.php
│   └── Drush/Commands/GmDemoCommands.php
├── templates/
│   ├── gm-demo-styleguide.html.twig
│   └── gm-demo-index.html.twig
└── tests/src/Kernel/DemoGeneratorTest.php
```

## Fixture format

```yaml
unit: content-news
depends_on: [taxonomy-themes, recurring-card]
entities:
  - key: media.news.landscape
    type: media
    bundle: image
    file: assets/landscape-1600x900.jpg
    alt: 'Wind turbines at sunset'
    values: { name: 'Landscape 16:9' }

  - key: node.news.long
    type: node
    bundle: news
    values:
      title: 'A very long news title that wraps on three lines on mobile to check the card and the page header hold together'
      field_theme: '@term:themes.energy'
      field_image: '@media:media.news.landscape'
      field_paragraphs:
        - _paragraph: text
          field_text: { value: '<p>Accents, « guillemets », &amp; 100 % — 5 € …</p>', format: basic_html }
      path: { alias: /demo/content-news/long, pathauto: 0 }
    translations:
      en:
        title: 'English title'
        field_paragraphs:
          - _paragraph: text
            field_text: { value: '<p>English only paragraph.</p>', format: basic_html }

  - key: node.news.minimal
    type: node
    bundle: news
    values: { title: 'Minimal news, every optional field empty' }

  - key: menu.main.news
    type: menu
    values: { title: 'News', menu_name: main, link: { uri: '@node:node.news.long' }, weight: 2 }

  - key: user.editor
    type: user
    values: { name: demo-editor, mail: demo-editor@example.com, pass: demo, status: 1, roles: [editor] }
```

Rules:

- `key` is unique across all fixtures and stable: other fixtures reference it
  as `@<type>:<key>` (`@term:themes.energy`). Never an entity id.
- `type`: `term`, `media`, `file`, `node`, `user`, `menu`, `block`, or any
  entity type id (`webform`). `bundle` maps to the entity type's bundle key.
  A config entity gives its `id` in `values`, prefixed `gm_demo_`.
- Multisite: `fixtures/sites/<site>/<unit>.yml` adds the entities of one site
  (its palette terms, its menus) to the shared unit; the site is the one
  Drush runs on (`make demo SITE=<site>`).
- Remote media (oEmbed video) fetch the provider when generated: the network
  must be up; keep one per fixture, with a stable public URL.
- `_paragraph: <bundle>` creates a paragraph inline, nested as deep as needed.
- A `uri` that starts with `@` becomes `entity:<type>/<id>`.
- `translations.<langcode>` holds the values of that translation. With the
  asymmetric mode, it carries **its own** paragraphs.
- A node built only to host paragraphs uses a stable alias
  `/demo/<unit>[/<case>]` and `pathauto: 0`. A content type unit leaves
  pathauto on for at least one node, to test its pattern.
- Every fixture covers the edge cases: long title and text, empty optional
  fields, minimum and maximum item counts, special characters, and the
  translation when the site is multilingual.
- One account per editorial role defined by the CDC (`demo-<role>`, password
  `demo`, local only). Log in with `make drush c='user:login --name=demo-editor'`.

## Makefile targets

```make
APP_ENV := $(shell sh -c "grep -E '^APP_ENV=' .env 2>/dev/null | tail -n1 | cut -d '=' -f2 | tr -d '\r'")

demo: ## Génère le contenu de démo, local uniquement (usage: make demo [unit=<id>])
	@[ "$(APP_ENV)" = "local" ] || { echo "Refused: APP_ENV=$(APP_ENV), demo content is local only."; exit 1; }
	$(DRUSH) gm-demo:generate $(unit)
	$(DRUSH) cr

demo-purge: ## Supprime le contenu de démo, local uniquement (usage: make demo-purge [unit=<id>])
	@[ "$(APP_ENV)" = "local" ] || { echo "Refused: APP_ENV=$(APP_ENV), demo content is local only."; exit 1; }
	$(DRUSH) gm-demo:purge $(unit)
	$(DRUSH) cr
```

Add both names to `.PHONY`. In a multisite, `$(DRUSH)` already carries
`--uri=$(SITE)`; add `demo-all` looping over `$(SITES)` (`multisite.md`).

## Module files

`gm_demo.info.yml`:

```yaml
name: 'GM Demo'
type: module
description: 'Local-only demo content, style guide and demo index. Never deployed.'
package: Custom
core_version_requirement: ^11
dependencies:
  - drupal:node
  - drupal:media
  - drupal:taxonomy
  - drupal:menu_link_content
  - paragraphs:paragraphs
```

`gm_demo.permissions.yml`:

```yaml
access gm_demo pages:
  title: 'Access the style guide and the demo index'
  restrict access: false
```

`gm_demo.routing.yml`:

```yaml
gm_demo.styleguide:
  path: '/styleguide'
  defaults:
    _controller: '\Drupal\gm_demo\Controller\StyleguideController::styleguide'
    _title: 'Style guide'
  requirements:
    _permission: 'access gm_demo pages'

gm_demo.index:
  path: '/styleguide/demo'
  defaults:
    _controller: '\Drupal\gm_demo\Controller\StyleguideController::index'
    _title: 'Demo content'
  requirements:
    _permission: 'access gm_demo pages'
```

`gm_demo.services.yml`:

```yaml
services:
  gm_demo.generator:
    class: Drupal\gm_demo\DemoGenerator
    arguments: ['@entity_type.manager', '@keyvalue', '@file_system', '@extension.list.module', '%site.path%']
  Drupal\gm_demo\DemoGenerator: '@gm_demo.generator'
```

`gm_demo.module`:

```php
<?php

/**
 * @file
 * Local-only demo content and style guide.
 */

declare(strict_types=1);

/**
 * Implements hook_theme().
 */
function gm_demo_theme(): array {
  return [
    'gm_demo_styleguide' => ['variables' => ['tokens' => []]],
    'gm_demo_index' => ['variables' => ['units' => []]],
  ];
}
```

`src/DemoGenerator.php`:

```php
<?php

declare(strict_types=1);

namespace Drupal\gm_demo;

use Drupal\Core\Entity\ContentEntityInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Extension\ModuleExtensionList;
use Drupal\Core\Field\FieldItemListInterface;
use Drupal\Core\File\FileExists;
use Drupal\Core\File\FileSystemInterface;
use Drupal\Core\KeyValueStore\KeyValueFactoryInterface;
use Drupal\Core\KeyValueStore\KeyValueStoreInterface;
use Drupal\Core\Serialization\Yaml;

/**
 * Generates and purges the demo entities described by the unit fixtures.
 */
final class DemoGenerator {

  private const TYPES = [
    'term' => 'taxonomy_term',
    'media' => 'media',
    'file' => 'file',
    'node' => 'node',
    'user' => 'user',
    'menu' => 'menu_link_content',
    'block' => 'block_content',
  ];

  private KeyValueStoreInterface $registry;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    KeyValueFactoryInterface $keyValueFactory,
    private readonly FileSystemInterface $fileSystem,
    private readonly ModuleExtensionList $moduleList,
    private readonly string $sitePath,
  ) {
    $this->registry = $keyValueFactory->get('gm_demo.registry');
  }

  /**
   * Returns the fixtures keyed by unit, dependencies first.
   */
  public function units(): array {
    $fixtures = [];
    foreach (glob($this->path('fixtures') . '/*.yml') as $file) {
      $fixtures[basename($file, '.yml')] = Yaml::decode(file_get_contents($file));
    }
    foreach (glob($this->path('fixtures/sites/' . basename($this->sitePath)) . '/*.yml') ?: [] as $file) {
      $unit = basename($file, '.yml');
      $site = Yaml::decode(file_get_contents($file));
      $fixtures[$unit]['depends_on'] ??= $site['depends_on'] ?? [];
      $fixtures[$unit]['entities'] = array_merge($fixtures[$unit]['entities'] ?? [], $site['entities'] ?? []);
    }
    $ordered = [];
    $visiting = [];
    $visit = function (string $unit) use (&$visit, &$ordered, &$visiting, $fixtures): void {
      if (isset($ordered[$unit])) {
        return;
      }
      if (isset($visiting[$unit])) {
        throw new \RuntimeException("Fixture dependency cycle on $unit.");
      }
      $visiting[$unit] = TRUE;
      foreach ($fixtures[$unit]['depends_on'] ?? [] as $dependency) {
        if (isset($fixtures[$dependency])) {
          $visit($dependency);
        }
      }
      $ordered[$unit] = $fixtures[$unit];
    };
    array_map($visit, array_keys($fixtures));
    return $ordered;
  }

  /**
   * Creates or updates the entities of one unit, or of every unit.
   */
  public function generate(?string $unit = NULL): array {
    $report = [];
    foreach ($this->select($unit) as $name => $fixture) {
      foreach ($fixture['entities'] ?? [] as $item) {
        $report[$name][] = $this->upsert($name, $item);
      }
    }
    return $report;
  }

  /**
   * Deletes exactly what generate() created, last created first.
   */
  public function purge(?string $unit = NULL): int {
    $count = 0;
    foreach (array_reverse($this->select($unit)) as $fixture) {
      foreach (array_reverse($fixture['entities'] ?? []) as $item) {
        foreach ([$item['key'], $item['key'] . '.file'] as $key) {
          $entry = $this->registry->get($key);
          if ($entry) {
            $this->entityTypeManager->getStorage($entry['type'])->load($entry['id'])?->delete();
            $this->registry->delete($key);
            $count++;
          }
        }
      }
    }
    return $count;
  }

  /**
   * Returns the registry entries of a unit.
   */
  public function registered(string $unit): array {
    return array_filter($this->registry->getAll(), fn (array $entry): bool => $entry['unit'] === $unit);
  }

  private function select(?string $unit): array {
    $units = $this->units();
    if ($unit === NULL) {
      return $units;
    }
    if (!isset($units[$unit])) {
      throw new \InvalidArgumentException("No fixture for unit $unit.");
    }
    return [$unit => $units[$unit]];
  }

  private function upsert(string $unit, array $item): string {
    $type = self::TYPES[$item['type']] ?? $item['type'];
    $storage = $this->entityTypeManager->getStorage($type);
    $entry = $this->registry->get($item['key']);
    $entity = $entry ? $storage->load($entry['id']) : NULL;

    $values = $this->resolve($item['values'] ?? []);
    if (isset($item['bundle'])) {
      $values[$storage->getEntityType()->getKey('bundle')] = $item['bundle'];
    }
    if (isset($item['file'])) {
      $values += $this->mediaSource($unit, $item);
    }

    $stale = [];
    if ($entity) {
      $stale = $entity instanceof ContentEntityInterface ? $this->paragraphs($entity, array_keys($values)) : [];
      foreach ($values as $field => $value) {
        $entity->set($field, $value);
      }
    }
    else {
      $entity = $storage->create($values);
    }

    foreach ($item['translations'] ?? [] as $langcode => $translated) {
      $translated = $this->resolve($translated, $langcode);
      if ($entity->hasTranslation($langcode)) {
        $translation = $entity->getTranslation($langcode);
        $stale = array_merge($stale, $this->paragraphs($translation, array_keys($translated)));
        foreach ($translated as $field => $value) {
          $translation->set($field, $value);
        }
      }
      else {
        $entity->addTranslation($langcode, $translated);
      }
    }

    $entity->save();
    array_map(fn ($paragraph) => $paragraph->delete(), $stale);
    $this->registry->set($item['key'], ['type' => $type, 'id' => $entity->id(), 'unit' => $unit]);
    return ($entry ? 'updated ' : 'created ') . $item['key'];
  }

  private function resolve(array $values, ?string $langcode = NULL): array {
    foreach ($values as $name => $value) {
      $values[$name] = $name === 'uri' && is_string($value) && str_starts_with($value, '@')
        ? $this->uri($value)
        : $this->resolveValue($value, $langcode);
    }
    return $values;
  }

  private function resolveValue(mixed $value, ?string $langcode): mixed {
    if (is_string($value) && preg_match('/^@(\w+):(.+)$/', $value, $match)) {
      return ['target_id' => $this->idOf($match[1], $match[2])];
    }
    if (is_array($value) && isset($value['_paragraph'])) {
      return $this->paragraph($value, $langcode);
    }
    return is_array($value) ? $this->resolve($value, $langcode) : $value;
  }

  private function paragraph(array $value, ?string $langcode): array {
    $bundle = $value['_paragraph'];
    unset($value['_paragraph']);
    $values = ['type' => $bundle] + $this->resolve($value, $langcode);
    if ($langcode) {
      $values['langcode'] = $langcode;
    }
    $paragraph = $this->entityTypeManager->getStorage('paragraph')->create($values);
    $paragraph->save();
    return ['target_id' => $paragraph->id(), 'target_revision_id' => $paragraph->getRevisionId()];
  }

  private function paragraphs(ContentEntityInterface $entity, array $fields): array {
    $paragraphs = [];
    foreach ($fields as $field) {
      $items = $entity->hasField($field) ? $entity->get($field) : NULL;
      if ($items instanceof FieldItemListInterface && $items->getFieldDefinition()->getType() === 'entity_reference_revisions') {
        $paragraphs = array_merge($paragraphs, $items->referencedEntities());
      }
    }
    return $paragraphs;
  }

  private function mediaSource(string $unit, array $item): array {
    $directory = 'public://gm_demo';
    $this->fileSystem->prepareDirectory($directory, FileSystemInterface::CREATE_DIRECTORY);
    $uri = $this->fileSystem->copy($this->path($item['file']), $directory . '/' . basename($item['file']), FileExists::Replace);

    $files = $this->entityTypeManager->getStorage('file');
    $entry = $this->registry->get($item['key'] . '.file');
    $file = ($entry ? $files->load($entry['id']) : NULL) ?? $files->create(['uri' => $uri, 'status' => 1]);
    $file->save();
    $this->registry->set($item['key'] . '.file', ['type' => 'file', 'id' => $file->id(), 'unit' => $unit]);

    $mediaType = $this->entityTypeManager->getStorage('media_type')->load($item['bundle']);
    $field = $mediaType->getSource()->getSourceFieldDefinition($mediaType)->getName();
    return [$field => ['target_id' => $file->id(), 'alt' => $item['alt'] ?? '']];
  }

  private function idOf(string $type, string $key): int|string {
    $entry = $this->registry->get($key) ?? throw new \RuntimeException("Unknown fixture key $key: generate its unit first.");
    if ($entry['type'] !== (self::TYPES[$type] ?? $type)) {
      throw new \RuntimeException("Fixture key $key is a {$entry['type']}, not a $type.");
    }
    return $entry['id'];
  }

  private function uri(string $reference): string {
    [$type, $key] = explode(':', substr($reference, 1), 2);
    return 'entity:' . (self::TYPES[$type] ?? $type) . '/' . $this->idOf($type, $key);
  }

  private function path(string $relative): string {
    return DRUPAL_ROOT . '/' . $this->moduleList->getPath('gm_demo') . '/' . $relative;
  }

}
```

`src/Drush/Commands/GmDemoCommands.php`:

```php
<?php

declare(strict_types=1);

namespace Drupal\gm_demo\Drush\Commands;

use Drupal\gm_demo\DemoGenerator;
use Drush\Attributes as CLI;
use Drush\Commands\AutowireTrait;
use Drush\Commands\DrushCommands;

/**
 * Drush commands for the local demo content.
 */
final class GmDemoCommands extends DrushCommands {

  use AutowireTrait;

  public function __construct(
    private readonly DemoGenerator $generator,
  ) {
    parent::__construct();
  }

  /**
   * Creates or updates the demo content.
   */
  #[CLI\Command(name: 'gm-demo:generate')]
  #[CLI\Argument(name: 'unit', description: 'Unit id; every unit, dependencies first, when omitted.')]
  public function generate(?string $unit = NULL): void {
    $this->assertLocal();
    foreach ($this->generator->generate($unit) as $name => $lines) {
      $this->logger()->success(sprintf('%s: %d entities', $name, count($lines)));
    }
  }

  /**
   * Deletes the demo content, and only it.
   */
  #[CLI\Command(name: 'gm-demo:purge')]
  #[CLI\Argument(name: 'unit', description: 'Unit id; every unit, dependents first, when omitted.')]
  public function purge(?string $unit = NULL): void {
    $this->assertLocal();
    $this->logger()->success(sprintf('%d entities deleted', $this->generator->purge($unit)));
  }

  private function assertLocal(): void {
    if (($_ENV['APP_ENV'] ?? getenv('APP_ENV')) !== 'local') {
      throw new \RuntimeException('Demo content is local only (APP_ENV must be "local").');
    }
  }

}
```

Purging one unit does not purge the units that reference it: their references
dangle until they are regenerated. `make demo-purge` without argument then
`make demo` resets everything.

## Style guide and demo index

`src/Controller/StyleguideController.php` reads the tokens from the theme's
`@theme` block, so the page follows the CSS without being edited:

```php
<?php

declare(strict_types=1);

namespace Drupal\gm_demo\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\Extension\ThemeExtensionList;
use Drupal\gm_demo\DemoGenerator;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Local-only style guide and demo index.
 */
final class StyleguideController extends ControllerBase {

  public function __construct(
    private readonly DemoGenerator $generator,
    private readonly ThemeExtensionList $themeList,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('gm_demo.generator'), $container->get('extension.list.theme'));
  }

  /**
   * Renders every token and every base component in every state.
   */
  public function styleguide(): array {
    $css = file_get_contents(DRUPAL_ROOT . '/' . $this->themeList->getPath($this->config('system.theme')->get('default')) . '/src/css/theme.css');
    preg_match_all('/--([a-z]+)-([a-z0-9-]+):\s*([^;]+);/', $css, $matches, PREG_SET_ORDER);
    $tokens = [];
    foreach ($matches as [, $namespace, $name, $value]) {
      if ($name !== '*') {
        $tokens[$namespace][$name] = trim($value);
      }
    }
    return ['#theme' => 'gm_demo_styleguide', '#tokens' => $tokens, '#cache' => ['max-age' => 0]];
  }

  /**
   * Lists the demo pages, grouped by unit.
   */
  public function index(): array {
    $units = [];
    foreach (array_keys($this->generator->units()) as $unit) {
      foreach ($this->generator->registered($unit) as $key => $entry) {
        $entity = $this->entityTypeManager()->getStorage($entry['type'])->load($entry['id']);
        if ($entity && in_array($entry['type'], ['node', 'taxonomy_term'], TRUE)) {
          $units[$unit][] = ['key' => $key, 'label' => $entity->label(), 'url' => $entity->toUrl()->toString()];
        }
      }
    }
    return ['#theme' => 'gm_demo_index', '#units' => $units, '#cache' => ['max-age' => 0]];
  }

}
```

`templates/gm-demo-styleguide.html.twig` renders, section by section: colour
swatches (name, value, contrast against white and the main text colour),
typography (each family, weight, size and line height, headings `h1`–`h6` and
the decoupled heading styles), spacing, containers and grid, radii, shadows,
then **every base component in every state** through the theme's own
templates:

```twig
{% for variant in ['primary', 'secondary', 'tertiary'] %}
  {% for state in ['default', 'focus', 'disabled'] %}
    {% include '@frontend/components/button.html.twig' with {
      label: variant|capitalize ~ ' — ' ~ state,
      variant: variant,
      disabled: state == 'disabled',
      attributes: create_attribute().addClass(state == 'focus' ? 'is-demo-focus' : ''),
    } only %}
  {% endfor %}
{% endfor %}
```

- Static states (disabled, error, success, focus through the `is-demo-focus`
  class that reuses the `:focus-visible` styles) are shown directly. Hover and
  active are checked by hovering in Chrome.
- Each section carries an `id` (`#colors`, `#buttons`, `#forms`…) so tests and
  captures can target it.
- Keep the template's own layout classes few, and add
  `@source "../../../../../modules/custom/gm_demo/templates";` to the theme's
  `tailwind.css` so they compile.

`templates/gm-demo-index.html.twig` lists the units in dependency order, each
with its demo pages. It is the entry point of the UAT and of the captures.

## Kernel test of the generator

`tests/src/Kernel/DemoGeneratorTest.php` proves the two promises: generation is
idempotent, purge deletes exactly what was created and nothing typed by hand.
Use a minimal fixture written to a temporary module path, or the
`foundations.yml` fixture when it only needs core entity types.

```php
public function testGenerateIsIdempotentAndPurgeIsExact(): void {
  $manual = Node::create(['type' => 'page', 'title' => 'Typed by hand']);
  $manual->save();

  $this->generator->generate('foundations');
  $count = $this->countNodes();
  $this->generator->generate('foundations');
  $this->assertSame($count, $this->countNodes());

  $this->generator->purge('foundations');
  $this->assertSame(1, $this->countNodes());
  $this->assertNotNull(Node::load($manual->id()));
}
```
