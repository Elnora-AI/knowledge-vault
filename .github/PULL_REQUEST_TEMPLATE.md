<!-- PR title must be a Conventional Commit, e.g. "feat: add /kb-setup verification step" -->

## What & why

<!-- What does this change and why? -->

## Checklist

- [ ] `node scripts/check-no-secrets.mjs` passes (no company/person/customer/path-specific strings)
- [ ] `node scripts/check-json.mjs` passes (manifests valid, no leaked config)
- [ ] `ruff check` and `pytest` pass (if Python changed)
- [ ] Docs/examples use only the generic placeholder entities (Acme / Globex / Jane Doe / example.com)
- [ ] No hardcoded vault paths, folder names, or timezones — everything reads from config
