#!/usr/bin/env node
// Guard: fail if anything that looks like private or personal data leaks into
// the repo. This product must be 100% universal.
//
// The committed rules are deliberately GENERIC — structural red flags (absolute
// home paths, personal cloud mounts, non-placeholder emails, key/token shapes)
// plus the maintainer's own product brand outside its metadata allowlist. No
// real customer, vendor, or person name is hardcoded here.
//
// An optional, gitignored denylist (scripts/.no-secrets-denylist.txt — one
// term/regex per line) is also applied when present, so maintainers can scan
// for org-specific terms locally without committing them.
//
// Run locally:  node scripts/check-no-secrets.mjs
// Run in CI:     same; a non-zero exit lists every violation.

import { execSync } from "node:child_process";
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, relative, basename } from "node:path";

const ROOT = process.cwd();

const SKIP_DIRS = new Set([
  ".git", "node_modules", "dist", "build", "coverage",
  "__pycache__", ".venv", ".ruff_cache", ".pytest_cache",
]);

const TEXT_EXT = new Set([
  ".md", ".mjs", ".js", ".ts", ".json", ".py", ".yml", ".yaml",
  ".txt", ".toml", ".sh", ".ps1", ".cfg", ".ini", ".html", ".css", "",
]);

// This guard necessarily contains the patterns it searches for.
const SKIP_FILES = new Set(["scripts/check-no-secrets.mjs"]);

// "elnora" (the maintainer brand) may appear ONLY in these metadata strings.
// This includes the "Part of the Elnora family" cross-links to sibling public
// repos — sanctioned publisher metadata, not company-specific config.
const ALLOWED_ELNORA = [
  "opensource@elnora.ai",
  "security@elnora.ai",
  "github.com/elnora-ai",
  "elnora-ai",
  "elnora-ai/knowledge-vault",
  "elnora-ai/elnora-google-workspace",
  "elnora-google-workspace",
  "elnora-ai/elnora-slack",
  "elnora-slack",
  "elnora-ai/elnora-linear",
  "elnora-linear",
  "elnora-ai/elnora-whatsapp",
  "elnora-whatsapp",
  "elnora-ai/elnora-merit-aktiva",
  "elnora-merit-aktiva",
  "elnora family",
  "elnora ai, inc.",
  "elnora ai",
];

// Emails that are allowed to appear verbatim.
const ALLOWED_EMAIL = /^(opensource@elnora\.ai|security@elnora\.ai|noreply@anthropic\.com)$/i;
// Placeholder home-directory segments that are fine in examples.
const PLACEHOLDER_HOME = /^(yourname|username|user|you|name|jane|janedoe|home|me)$/i;

// Generic structural detectors — no real names.
const BANNED = [
  { name: "absolute macOS home path", re: /\/Users\/([a-z0-9._-]+)\//i, homeGroup: 1 },
  { name: "absolute Linux home path", re: /\/home\/([a-z0-9._-]+)\//i, homeGroup: 1 },
  { name: "personal cloud-storage mount", re: /(GoogleDrive-|CloudStorage\/)[\w.+-]*@/i },
  { name: "Slack user id", re: /\bU0[A-Z0-9]{7,}\b/ },
  { name: "AWS access key id", re: /\bAKIA[0-9A-Z]{16}\b/ },
  { name: "OpenAI/Anthropic-style key", re: /\b(sk-ant-|sk-)[A-Za-z0-9_-]{20,}/ },
  { name: "Linear API key", re: /\blin_api_[A-Za-z0-9]{20,}/ },
  { name: "GitHub token", re: /\bgh[pousr]_[A-Za-z0-9]{20,}\b/ },
  { name: "private key block", re: /-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/ },
  { name: "cloud gateway endpoint", re: /https:\/\/[\w.-]*\.(?:openai\.azure|azure-api)\.(?:com|net)/i },
];

const EMAIL_RE = /\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b/gi;
const ALLOWED_EMAIL_DOMAIN = /@(?:example\.(?:com|org|net)|test\.com)$/i;

function loadExtraDenylist() {
  const path = join(ROOT, "scripts", ".no-secrets-denylist.txt");
  if (!existsSync(path)) return [];
  const out = [];
  for (const raw of readFileSync(path, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    try {
      out.push({ name: `denylist: ${line}`, re: new RegExp(line, "i") });
    } catch {
      out.push({ name: `denylist: ${line}`, re: new RegExp(line.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i") });
    }
  }
  return out;
}

function walk(dir, out) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (!SKIP_DIRS.has(entry)) walk(full, out);
    } else {
      out.push(full);
    }
  }
}

function hasTextExt(path) {
  const b = basename(path);
  const dot = b.lastIndexOf(".");
  return TEXT_EXT.has(dot === -1 ? "" : b.slice(dot).toLowerCase());
}

function listGitFiles() {
  try {
    const out = execSync("git ls-files -z", { cwd: ROOT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    return out.split("\0").filter(Boolean).map((p) => join(ROOT, p));
  } catch {
    return null;
  }
}

const extra = loadExtraDenylist();
const files = listGitFiles() ?? (() => { const o = []; walk(ROOT, o); return o; })();
const violations = [];

for (const path of files) {
  if (!hasTextExt(path)) continue;
  const rel = relative(ROOT, path).split("\\").join("/");
  if (SKIP_FILES.has(rel)) continue;
  let content;
  try {
    content = readFileSync(path, "utf8");
  } catch {
    continue;
  }
  const lines = content.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lower = line.toLowerCase();

    for (const b of BANNED) {
      const m = b.re.exec(line);
      if (!m) continue;
      // Home-path rules allow known placeholder usernames.
      if (b.homeGroup && PLACEHOLDER_HOME.test(m[b.homeGroup])) continue;
      violations.push(`${rel}:${i + 1}  [${b.name}]  ${line.trim().slice(0, 120)}`);
    }

    for (const d of extra) {
      if (d.re.test(line)) violations.push(`${rel}:${i + 1}  [${d.name}]  ${line.trim().slice(0, 120)}`);
    }

    // Emails on a non-placeholder domain (catches real addresses generically).
    for (const em of line.match(EMAIL_RE) || []) {
      if (ALLOWED_EMAIL.test(em) || ALLOWED_EMAIL_DOMAIN.test(em)) continue;
      violations.push(`${rel}:${i + 1}  [non-placeholder email]  ${em}`);
    }

    // The maintainer brand outside its metadata allowlist.
    if (lower.includes("elnora")) {
      let stripped = lower;
      for (const allowed of ALLOWED_ELNORA) stripped = stripped.split(allowed).join("");
      if (stripped.includes("elnora")) {
        violations.push(`${rel}:${i + 1}  [non-metadata "elnora"]  ${line.trim().slice(0, 120)}`);
      }
    }
  }
}

if (violations.length > 0) {
  console.error(`Found ${violations.length} disallowed reference(s). This repo must be 100% universal.\n`);
  for (const v of violations) console.error(`  - ${v}`);
  console.error(
    `\nUse placeholder examples (Acme / Globex / Jane Doe / example.com). "Elnora" may appear only as ` +
      `publisher metadata (LICENSE, SECURITY contact, marketplace owner, plugin author, repo URL).`,
  );
  process.exit(1);
}

console.log(`check-no-secrets: scanned ${files.length} files. No disallowed references found.`);
