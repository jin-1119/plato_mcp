# Third-party PII exposure review (issue #36)

## What flows through the tools, and who it can identify

Grepped every model for a field that names a person, and classified each by whose
identity it can expose:

| Field | Tool(s) | Whose identity | Risk category |
|---|---|---|---|
| `FileEntry.author` | `get_course_contents` | Whoever uploaded a course file -- almost always course staff | Low: course staff, not classmates |
| `MessageItem.userfromfullname` | `get_unread_messages` | Sender of a notification addressed to this account | Low: this account's own notifications, not a public feed of others' messages |
| `UbboardPostSummary.writer` / `UbboardPostDetail.writer` (Notices) | `list_notices`, `get_notice_detail` | Instructor/TA who posted the notice | Low: course staff |
| `UbboardPostSummary.writer` / `UbboardPostDetail.writer` (Q&A) | `list_qna`, `get_qna_detail` | **Any classmate who posted a question** | **The real finding -- see below** |

Everything except Q&A's `writer` identifies course staff or is scoped to messages
already addressed to this account -- not a general feed of other students' identity
or content. Those are treated as low-risk and left as-is with no further action.

## The actual finding: Q&A `writer` can name a classmate

`list_qna`/`get_qna_detail` can return another enrolled student's display name
alongside their question text. This is the one field in the whole tool surface where
a third party (not course staff, not this account) gets identified.

## Decision: pass through as-is, not redacted

Reasoning:

1. **No new access is granted.** This account already has legitimate access to
   every Q&A post it can see through the tool -- it's the exact same content
   visible by opening the Q&A board in a browser, scoped to courses this account
   is actually enrolled in. The tool changes the medium, not the access boundary.
2. **Redacting would break the feature.** A Q&A tool that hides who asked a
   question can't answer "has anyone already asked this?" or "what did the
   professor tell so-and-so" -- which is the actual point of exposing Q&A at all.
3. **There's no principled partial redaction available.** The scraped fields are
   already minimal (`writer`, `title`, `content_html`) -- there's no structured way
   to strip "the PII part" out of freeform post content without gutting it.

This mirrors how the project has treated course-content authorship (issue #34's
audit, and the original file-download research) throughout: information the
account already has standing access to is passed through; what changes is being
careful about *where else* that information now flows.

## What IS new, and must be disclosed: the AI/LLM data-flow

Browsing the Q&A board in a browser and calling `list_qna` through this MCP server
are not equivalent from a data-flow standpoint. The MCP call's output becomes part
of the conversation sent to whatever LLM/AI provider (e.g. Anthropic) the connected
client is using. A classmate posting a question never agreed to their name and post
appearing in a third party's AI conversation, even though they did implicitly agree
to it being visible to logged-in classmates via PLATO's own UI.

This is disclosed in the README's privacy note (see below), not solved in code --
there is no way for the server itself to know or control what the connecting AI
client does with tool output.

## Known gap: the "secret" flag is unverified server-side

`docs/ubboard_structure.md` (issue #19) found that Q&A's write form has a `secret`
checkbox (private/instructor-only post, checked by default). Whether PLATO's server
actually withholds a secret post's content from other students at the HTTP response
level -- i.e. whether our scraper would simply never receive it -- or only hides it
client-side (in which case our scraper could inadvertently pull content the student
intended to keep private) has **never been tested**, because no real Q&A post has
ever existed on the test account (same gap already tracked in issue #23 and
`tests/integration/README.md`).

This must be verified before public deployment: post a real `secret` Q&A question
from one test account and confirm `list_qna`/`get_qna_detail` called from a
*different* account cannot see it. Until then, treat "the secret flag is enforced
server-side" as an assumption, not a confirmed fact.

## Where this decision is recorded in code

- `ubboard/models.py`: `UbboardPostSummary.writer` / `UbboardPostDetail.writer`
  field descriptions point here.
- `models.py`: `FileEntry.author` / `MessageItem.userfromfullname` field
  descriptions note their lower-risk classification.
- `README.md`: privacy note added, cross-referencing this document.
