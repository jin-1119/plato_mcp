# plato-mcp

Unofficial MCP (Model Context Protocol) server for **PLATO**, Pusan National University's
Moodle-based LMS (https://plato.pusan.ac.kr/).

> Work in progress. See [`PLAN.md`](./PLAN.md) for the full implementation plan and
> [GitHub Issues](https://github.com/jin-1119/plato_mcp/issues) for current status.

## Disclaimer

- **Not affiliated with or endorsed by Pusan National University (PNU) or the
  PLATO/Moodle platform.** This is an independent, community-built integration
  that automates the same PLATO account access you already have through your
  own browser -- it grants no new permissions and does not act on behalf of PNU.
- **Use at your own risk, and in compliance with PNU's terms of service.** In
  particular, the notices/Q&A board (`ubboard`) has no official API, so this
  project reads it by scraping the rendered HTML with your own logged-in
  session -- against a site whose `robots.txt` says `Disallow: /`. That
  directive is aimed at anonymous crawlers, not an authenticated user's own
  browsing, but it's still scraping, and you are responsible for confirming
  this fits within PNU's acceptable-use policy for your account before you
  connect this server to it. Recommended: personal, low-volume use, not
  automated bulk scraping of the entire site.
- **Your PLATO credentials are never persisted to disk by this server.** See
  [`SECURITY.md`](./SECURITY.md) for exactly what is and isn't stored, and for
  how long.
- **This project has not been independently security-audited by a third
  party.** Several credential-handling and abuse-prevention issues were found
  and fixed during development (see `docs/security_audit.md` and
  `docs/abuse_prevention_review.md`) -- fixing what we found ourselves is not
  the same guarantee as an external audit.

## Privacy note

This server passes through course content -- including, on the Q&A board,
**other students' names and posts** -- because your account already has legitimate
access to it via PLATO itself; the tool doesn't grant any new access. What's
different from browsing PLATO in a browser is that this content becomes part of
whatever conversation you have with your AI assistant, i.e. it's sent to that
assistant's AI/LLM provider (e.g. Anthropic) as tool output. Keep that in mind
before asking broad questions against a course's Q&A board.

See [`docs/pii_review.md`](./docs/pii_review.md) for the full review, including a
known gap: whether PLATO enforces a Q&A post's "private/instructor-only" flag on
the server side (so this tool would never see such a post at all) has not been
empirically verified.

**When running remotely** (e.g. via a Claude.ai Connector rather than local
Claude Code/Desktop), `download_course_file` for a large file (over the
inline-delivery size limit) returns a download *link* rather than the file
itself, and that link has a live PLATO access token embedded in it. **That
token is not scoped to the one file** -- it authenticates arbitrary PLATO API
calls for your account, confirmed by live testing. Sharing that link, or a
chat transcript containing it, is equivalent to sharing an active credential
for your account, not just handing out one file. See
[`SECURITY.md`](./SECURITY.md) and
[`docs/smithery_deployment_model.md`](./docs/smithery_deployment_model.md)
for the full detail.

## Development

```bash
pip install -e ".[dev]"
pytest
```
