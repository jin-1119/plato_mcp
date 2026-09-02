# Abuse-prevention review for write tools (issue #37)

## Scope

Re-reviewed `submit_assignment` and `post_qna_question` (the two implemented write
tools) for spam/abuse potential now that the server is meant to be publicly
deployed, and specifically re-checked whether the dry_run confirmation pattern
from issue #24 (`docs/write_confirmation_pattern.md`) could be trivially bypassed.

`reply_to_qna` is not in scope -- it isn't implemented (see issue #27/#23; no real
Q&A reply mechanism has ever been observed to build against).

## Finding: the confirmation pattern's own documented gap was real

`docs/write_confirmation_pattern.md` already flagged this honestly when it was
written: `dry_run` was a *convention* the tool description asked the calling LLM to
respect, but nothing on the server actually enforced it. A client that ignored
`ToolAnnotations.destructive_hint` and an LLM that ignored the "wait for
confirmation" instruction could call `dry_run=False` on the very first try, with no
prior preview ever shown to a human.

## Fix: PreviewTracker enforces it server-side

`write_tools.PreviewTracker` (new in this issue) requires a `dry_run=True` preview
-- for the exact same session, action, and parameters -- to be on file before a
`dry_run=False` call is allowed to proceed. Specifically:

- **Keyed on session + action + a hash of the parameters.** A preview for one
  assignment/question can't be used to wave through a confirm for a *different*
  one, and a preview shown in one MCP session can't authorize a confirm from
  another.
- **Consumed on use.** One preview authorizes exactly one confirm, not repeated
  ones -- an LLM can't preview once and then loop `dry_run=False` calls.
- **Expires after 5 minutes.** A stale preview from an old, abandoned conversation
  turn can't be replayed much later.
- Wired into both `submit_assignment_for` and `post_qna_question_for`; calling
  either with `dry_run=False` without a fresh, matching preview now raises
  `WriteConfirmationError` before any network call that would mutate PLATO state.

This directly closes the gap the design doc called out, rather than just
re-documenting it. Verified live against the real account (not just mocks): a
`dry_run=False` call with no prior preview was rejected before any HTTP POST was
made; after a genuine `dry_run=True` preview, the confirmation gate correctly
allowed the next matching call through (stopped short of the real POST itself, per
the same "don't post real content without explicit go-ahead" boundary already
established for issue #27).

## Other abuse vectors considered

- **Volume/spam** (many submissions or posts in a short time): covered by issue
  #35's rate limiter, which already wraps every outbound PLATO call including the
  write tools' network requests.
- **Submitting/posting something different from what was previewed**: covered by
  PreviewTracker's parameter hashing -- a preview only authorizes a confirm with
  the *exact same* parameters, so a preview for a benign submission can't be used
  to cover a confirm for a different one.
- **Malicious `text`/`content_text` values** (e.g. script injection, since Q&A
  content is rendered as HTML by PLATO's own UI): out of scope for this server --
  the content is submitted as the authenticated user's own text, exactly as if
  they'd typed it into PLATO's own form; sanitizing it further isn't this server's
  job any more than a browser sanitizes what a user types into a textbox before
  submitting it. PLATO's own server-side handling of submitted content is the
  relevant boundary here, not something this project can or should second-guess.

## Sign-off

The one real gap found (unenforced `dry_run`) is fixed and covered by 12 new
regression tests (`tests/unit/test_abuse_prevention.py`, 105 total across the
suite), plus live verification against the real account. No further findings from
this pass. Required before issue #32 (public listing) per the original plan.
