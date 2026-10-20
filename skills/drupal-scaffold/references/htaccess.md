# .htaccess: prepend rules and preprod auth

## What can move to a prepend

The prepend is read before the whole stock file. That is safe for:

| Directive | Why position does not matter |
|---|---|
| `Redirect 301 …` (mod_alias) | mod_alias and mod_rewrite run in a fixed module order, whatever the line order in the file. Prod redirects buried in Drupal's `<IfModule mod_rewrite.c>` block move as-is. |
| A request firewall (7G, 8G…) | Only `[F]` rules. It *should* run first. |
| `AddOutputFilterByType DEFLATE`, `BrowserMatch`, `Options -MultiViews` | Not order-dependent. Wrap each in its own `<IfModule>`. |
| Your own `RewriteRule`s | All `RewriteRule`s in one `.htaccess` form a single ordered set, whatever `<IfModule>` they sit in. Prepended rules simply run before Drupal's, which is what a redirect wants. |

The prepend runs before Drupal's `protossl` detection, so write `https://`
literally instead of `http%{ENV:protossl}://`.

## Rules to rewrite, not copy

**Generic force-www.** On prod the stock block is often uncommented:

```apache
RewriteCond %{HTTP_HOST} !^www\. [NC]
RewriteRule ^ http%{ENV:protossl}://www.%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
```

Once it ships to every environment, it breaks the preprod and local hosts
(`www.preprod.example.com`). Restrict it to the prod domain, and confirm with the
user which bare domains the prod answers on:

```apache
RewriteCond %{HTTP_HOST} ^example\.com$ [NC]
RewriteRule ^ https://www.example.com%{REQUEST_URI} [L,R=301]
```

**Trailing slash stripping.** Keep it if prod has it. Behind a TLS-terminating
proxy (local Traefik), the 301 points to `http://`; the proxy then upgrades it.

## Duplicates to drop

Hand-pasted blocks (often copied from a Laravel or WordPress `.htaccess`) re-add
what the stock file already does:

- **A second front controller** (`RewriteCond !-f` / `!-d` → `index.php [L]`)
  placed *before* Drupal's rules is a **security bug**. The `[L]` rewrites to
  `index.php` before the stock hidden-path rule
  (`RewriteRule "/\.|^\.(?!well-known/)" - [F]`) sees the original URI. Drop it.
- `RewriteRule .* - [E=HTTP_AUTHORIZATION:…]`: stock already does it.
- `ExpiresActive` / `ExpiresDefault` / `ExpiresByType … 1 year`: stock sets
  `ExpiresDefault` and turns expiry off for PHP.
- Old gzip rules (`^(.*)\.css $1\.css\.gz`): the current stock serves
  pre-compressed aggregates (gzip and brotli) with stricter patterns.

Commented-out lines and their headers: keep only if they document a toggle the
team uses (e.g. firewall logging).

## Building the prepend from the prod file

Cut by line ranges from the prod branch's copy, so third-party blocks stay
byte-identical:

```bash
git show origin/master:web/.htaccess > "$S/prod.htaccess"
grep -n '^# Apache/PHP/Drupal settings\|Redirect 301\|^# 7G' "$S/prod.htaccess"
{
  sed -n '1,<end of firewall>p' "$S/prod.htaccess"
  cat <<'EOF'

<IfModule mod_rewrite.c>
  RewriteEngine on
  RewriteCond %{HTTP_HOST} ^example\.com$ [NC]
  RewriteRule ^ https://www.example.com%{REQUEST_URI} [L,R=301]
</IfModule>

<IfModule mod_alias.c>
EOF
  grep -E '^\s*Redirect 30[12] ' "$S/prod.htaccess"
  echo '</IfModule>'
} > scaffold/htaccess-prepend.txt
```

Count the redirects on both sides: `grep -c 'Redirect 30'`.

`Redirect` never matches a query string: a rule like
`Redirect 301 /contact/?to=x …` is dead in prod as well. Keep it verbatim, and
mention it in the MR rather than "fixing" it unasked.

## Preprod auth

The preprod Basic auth is appended **after** each deploy, on the preprod branch
only. Nothing environment-specific is committed:

```yaml
preprod-auth:
  stage: deploy
  only:
    - release
  <<: *inject_conditional_vars        # reuse the anchor that sets SSH_USER / SSH_HOST
  needs:
    - deploy
  script:
    - *init_ssh
    - |
      WEB_DIR="<deploy path>/current/web"
      ssh ${SSH_USER}@${SSH_HOST} "cat > ${WEB_DIR}/.htpasswd" <<< "$PREPROD_HTPASSWD"
      ssh ${SSH_USER}@${SSH_HOST} "cat >> ${WEB_DIR}/.htaccess" <<EOF
      AuthType Basic
      AuthName "Preprod"
      AuthUserFile ${WEB_DIR}/.htpasswd
      Require valid-user
      Header set X-Robots-Tag "noindex, nofollow"
      EOF
      echo "Preprod htpasswd and .htaccess configured"
```

- `AuthUserFile` needs an **absolute** path. On shared hosts `~` expands to
  something like `/homez.NNN/<user>`: resolve it once
  (`ssh … 'cd <deploy path>/current/web && pwd'`), never guess it. Do not use
  `pwd -P`, which would pin one release directory.
- Use the `current` symlink path. Each deploy creates a fresh release, so the
  append never accumulates.
- `PREPROD_HTPASSWD`: a masked, protected variable holding the `.htpasswd` line
  (`htpasswd -nbB <user> <password>`).
- Between the end of `deploy` and this job, the preprod is open for a few
  seconds. If that matters, run the same lines at the end of the deploy job's
  script, behind `if [ "$CI_COMMIT_REF_NAME" = release ]`.
- Monitoring and external crons hitting the preprod URL will now get 401.
