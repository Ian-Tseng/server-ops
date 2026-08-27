# Privacy

Local Server Ops 0.3.0 performs no analytics, problem-report submission,
feedback submission, diagnostic upload, or other outbound transmission by default.
Managed update checks remain off until separately enabled. They delegate only package
identity and version discovery to GitHub CLI, never workspace content, process details,
receipts, prompts, logs, or findings. Update consent creates one local installation hash
for policy binding; no analytics installation identity is created, and the hash is not
transmitted by this helper.

Configured health checks are explicit literal-loopback HTTP requests. Local receipts may
contain workspace paths and bounded process identity fields; they remain in the owner
profile state directory and are never uploaded automatically. Review receipts before
sharing them. Do not place credentials in adapters, argv, URLs, or verification commands.
The content-free `SkillOutcomeReceipt` contains only enum and package-identity fields;
public issue submission is a separate twice-confirmed action owned by
`analyze-project-claims`.
