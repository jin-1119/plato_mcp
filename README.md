# plato-mcp

Unofficial MCP (Model Context Protocol) server for **PLATO**, Pusan National University's
Moodle-based LMS (https://plato.pusan.ac.kr/).

> Work in progress. See [`PLAN.md`](./PLAN.md) for the full implementation plan and
> [GitHub Issues](https://github.com/jin-1119/plato_mcp/issues) for current status.
> Full usage disclaimer and setup instructions land in a later phase (issue #31).

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

## Development

```bash
pip install -e ".[dev]"
pytest
```
