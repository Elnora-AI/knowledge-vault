# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | Yes       |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately via one of:

- **Email:** [security@elnora.ai](mailto:security@elnora.ai)
- **GitHub Security Advisories:** [Report a vulnerability](https://github.com/Elnora-AI/knowledge-vault/security/advisories/new)

Include as much as you can: a description, steps to reproduce, potential impact, and any suggested fix.

## Response Timeline

- **Acknowledgement:** within 48 hours
- **Initial assessment:** within 5 business days
- **Fix and disclosure:** within 90 days

## Scope

**In scope:**

- The plugin content in this repository (agents, commands, skills, hooks) and how it reads config and vault files
- The optional connector framework under `connectors/`
- The CI guards (`scripts/check-no-secrets.mjs`, `scripts/check-json.mjs`)

**Out of scope:**

- Third-party dependencies (report to their maintainers)
- Obsidian itself, and any transcript/meeting tool a user wires into a connector
- A user's own vault contents or their choice of `vault_path`

## Best Practices for Users

- Keep `.claude/knowledge-base.local.md` gitignored — it holds your real `vault_path`.
- If you enable a connector that uses an LLM, provide the API key via an environment variable; never commit it.
- Only point connector source adapters at data you trust; the bundled Quill adapter opens its database read-only.
