# Security

This document describes what plato-mcp stores, for how long, and the known
credential-exposure surfaces -- both fixed and still-open -- so you can decide
whether to run it and how.

## What is stored, and where

| Data | Where it lives | Persisted to disk? | Lifetime |
|---|---|---|---|
| PLATO student ID / password (local/stdio run) | Process environment / `.env` file you provide | Only if you put it in your own `.env` -- the server itself never writes it anywhere | As long as your `.env` exists; the server only reads it |
| PLATO student ID / password (remote/streamable-http run) | In-memory only, per HTTP request (headers/query params) | **No** | One request; not cached beyond the login session below |
| Login session (`wstoken`, cookies, `sesskey`) | In-memory `SessionManager` cache (`auth.py`), keyed by an opaque per-connection session key | **No** | Until the process restarts, the session is evicted, or a fresh login is forced |
| Course content, grades, messages, Q&A/notice posts fetched by tools | Nowhere -- passed straight through as tool output to whatever MCP client called the tool | No | Not stored by this server at all (see the caller's own retention: e.g. your AI assistant's conversation history) |
| Downloaded course files (local/stdio) | Wherever you told `download_course_file`'s `save_path` to put it | Yes, by design -- that's the point of the local download path | Until you delete it yourself |
| Downloaded course files (remote/streamable-http) | Returned as base64 content in the tool response (small files), or not stored at all (large files use a direct link the caller's own browser fetches) | No | N/A -- never touches this server's disk |

**In short: this server has no database, no credential store, and writes
nothing to disk on its own initiative.** The one place credentials land on
disk is the `.env` file *you* create for local/stdio use -- that's your file,
not something this server manages, and it should never be committed to
version control (see `.gitignore`).

## Known credential-exposure surfaces

These are places a credential or access token *could* end up somewhere other
than directly between you and PLATO -- either fixed already, or an inherent
tradeoff of how PLATO's own API works.

### Fixed

- **URL-embedded credentials in error messages** (issue #34): `requests`
  embeds the full request URL -- including query-string credentials -- in
  `HTTPError`/`RequestException` messages. Login and API calls were switched
  from GET to POST so credentials never appear in a URL at all; the one
  endpoint that structurally requires a token in the URL (file downloads,
  see below) catches and sanitizes that specific failure mode instead. See
  `docs/security_audit.md`.
- **PLATO password logged via the container's own access log** (issue #63):
  when deployed remotely, Smithery delivers your credentials as query
  parameters on the request URL. The web server's default access-log format
  would otherwise log that full URL -- password included -- to its own
  stdout on every request. Replaced with a logging middleware that never
  records the query string. See `docs/smithery_deployment_model.md`.
- **Unenforced write-confirmation bypass** (issue #37): the "preview before
  you act" pattern for `submit_assignment`/`post_qna_question` was originally
  just a convention an LLM was asked to follow, not something the server
  enforced -- a client or model that skipped the preview step could submit
  or post immediately. Now enforced server-side (`PreviewTracker`): a
  matching preview must exist, is single-use, and expires after 5 minutes.
  See `docs/abuse_prevention_review.md`.

### Inherent, not a bug -- know before you rely on this

- **The remote download-link fallback token is broadly scoped.** For a
  course file too large to return inline (over `INLINE_BASE64_MAX_MB`),
  `download_course_file` returns a direct PLATO URL with a `?token=...`
  suffix instead of the file content. That token is a general-purpose Moodle
  webservice credential -- confirmed live by calling an unrelated API
  function (`core_webservice_get_site_info`) with it and getting your real
  name, student ID, and full account access back. **Anyone who obtains that
  URL (e.g. from a shared chat transcript) can use it against your account
  broadly, not just to fetch that one file.** This is a property of PLATO's
  own Moodle webservice token model, not something this server can narrow
  down further without PLATO-side changes. Common course files (observed
  100KB-1.5MB) stay under the inline-delivery threshold and never expose
  this token at all; only larger files hit this path.
- **Rate limiting protects PLATO, not your credentials.** The outbound
  request limiter (`security.py`) exists to keep this server (especially a
  publicly-shared deployment) from hammering PLATO's servers, not as a
  security boundary around your account.

## What this project has not done

- **No independent third-party security audit.** Everything above was found
  through this project's own review passes (issues #34-37, #56, #63), not an
  external assessment. Treat this as "known issues found and fixed by the
  people who wrote it," not "certified secure."
- **`reply_to_qna` is unimplemented**, and `post_qna_question`'s real
  (non-preview) POST path has never actually been exercised against a live
  PLATO account -- both are documented gaps, not silent ones.
- **No automated CI security scanning** (dependency vulnerability scanning,
  SAST) is currently configured for this repository.

## Reporting a concern

This is an independent, community project with no formal security team.
Open a GitHub issue (avoid including real credentials, tokens, or other
students' personal information in the issue itself) or contact the
maintainer directly for anything sensitive.
