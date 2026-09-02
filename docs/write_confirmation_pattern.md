# Write-tool confirmation pattern (issue #24)

Applies to all three write tools: `submit_assignment` (#25), `post_qna_question` and
`reply_to_qna` (#27). All three do something on PLATO that's hard or impossible to
undo (a submitted assignment can't be un-submitted; a posted Q&A question is visible
to the instructor and classmates immediately). This document is the one place the
pattern is defined -- each tool wires into it rather than inventing its own version.

## The pattern

Every write tool takes a `dry_run: bool = True` parameter, as its own explicit
argument (not inferred from anything else):

- **`dry_run=True` (the default)**: validate the inputs, prepare exactly what would be
  sent, and return a preview -- but make **no** mutating request to PLATO. The tool's
  docstring tells the LLM to show this preview to the user and only re-call with
  `dry_run=False` after the user has explicitly confirmed.
- **`dry_run=False`**: perform the real write, and return the same shape of result,
  now with `executed=True`.

Every write tool returns the same `WriteResult` shape (`src/plato_mcp/write_tools.py`):

```python
class WriteResult(BaseModel):
    dry_run: bool
    executed: bool
    preview: dict       # human-readable description of what would/did happen
    message: str        # one-line status, phrased differently for preview vs. real
```

Every write tool is also registered with the same MCP `ToolAnnotations`
(`WRITE_TOOL_ANNOTATIONS`, also in `write_tools.py`):

```python
ToolAnnotations(destructive_hint=True, idempotent_hint=False, read_only_hint=False)
```

## Why this combination, and not something else

**Why a `dry_run` flag instead of a two-step preview-token flow** (preview call
returns an opaque token, a second call must supply that exact token to execute):
a token only adds real protection against a *third party* replaying a stale preview
without ever having seen it -- but here, the same MCP session that requested the
preview is the one that would supply the token, so it adds bookkeeping (where do
tokens live? how long do they last? what invalidates them?) without a matching
security benefit for this threat model. A plain boolean is simpler, has no state to
manage or expire, and is trivial to explain to an LLM: "call it again with
`dry_run=False`."

**Why `ToolAnnotations(destructive_hint=True, ...)` in addition to the flag**: the
`dry_run` flag is a convention this server's own tool descriptions ask the calling
LLM to respect -- nothing stops a client (or an aggressively autonomous LLM) from
just calling with `dry_run=False` on the first try. `ToolAnnotations` is MCP's
standard, protocol-level signal for "this tool does something destructive and isn't
safe to auto-approve" -- MCP-compliant clients (Claude Desktop among them) can use
this to gate the call behind their own UI confirmation, independent of whether the
LLM chose to respect `dry_run`. The two layers cover different gaps: `dry_run` gives
the LLM (and the human reading its response) something concrete to review;
`destructive_hint` gives the *client* a chance to enforce a stop even if the LLM
doesn't.

**What this does NOT solve**: a sufficiently permissive MCP client that ignores
`destructive_hint`, paired with an LLM that ignores the "wait for confirmation"
instruction in the tool docstring, can still call straight through with
`dry_run=False`. That gap is explicitly the subject of issue #29 (abuse-prevention
review before public listing) -- this issue only establishes the pattern, not a
guarantee that it can't be bypassed.

## Consuming this pattern (for #25 / #27)

Each write tool's implementation should:

1. Build the exact payload it would send to PLATO (course/assignment ids, form
   fields, file contents, etc.) regardless of `dry_run`.
2. If `dry_run`, return `WriteResult(dry_run=True, executed=False, preview=<payload
   summary>, message="Preview only -- call again with dry_run=False to actually
   submit.")` without making the mutating HTTP/webservice call.
3. If not `dry_run`, make the real call, then return `WriteResult(dry_run=False,
   executed=True, preview=<same payload summary>, message="Submitted.")`.
4. Register the tool with `annotations=WRITE_TOOL_ANNOTATIONS`.
