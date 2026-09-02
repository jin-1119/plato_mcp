# ubboard HTML structure (issue #19 findings)

Captured 2026-09-02 against a real PLATO account, cookie-session login (no SSO —
plain form POST to `/login/index.php`). Fixtures saved in `tests/fixtures/ubboard/`
(scrubbed of the logged-in student's name and the live `sesskey`).

## 1. Login (for issue #20 — auth.py cookie-session support)

`GET /login/index.php` returns **two** login forms:

| Form id | `logintab` value | Purpose |
|---|---|---|
| `form-login-sso` | `univ` | School SSO login (student ID + password) — **this is what worked** |
| `form-login-person` | `person` | Separate "personal account" login, not used by us |

Both forms share one `logintoken` hidden field (CSRF token, scraped from the GET response).

POST to `https://plato.pusan.ac.kr/login/index.php` with:
```
anchor=
logintoken=<scraped from GET>
logintab=univ
username=<student id>
password=<password>
rememberusername=1
```
On success: redirects to `/`, response HTML title is `홈 | PLATO`, a `logout.php` link is
present, and the session sets `MoodleSession` + `MOODLEID1_` cookies. Same student ID/password
that works for `login/token.php` (wstoken) works here — no separate credential needed.

`sesskey` (needed for any POST/write action) is embedded in the post-login page as
`"sesskey":"<value>"` inside an inline `<script>` block (Moodle's `M.cfg`). Extract with a
regex: `"sesskey":"(\w+)"`.

## 2. Resolving which ubboard module is "Notices" vs "Q&A"

**`core_course_get_contents` already gives us everything we need** — no extra navigation
required. Each ubboard module in the response has:

```json
{
  "id": 37082,
  "modname": "ubboard",
  "name": "Notices",
  "url": "https://plato.pusan.ac.kr/mod/ubboard/view.php?id=37082",
  "customdata": "{\"type\":\"notice\",\"basic\":\"1\"}"
}
```

`customdata` (a JSON string, needs a second `json.loads`) has a `"type"` field:
- `"type":"notice"` → the announcements/Notices board
- `"type":"qna"` → the Q&A board
- `"type":"default"` (seen once, on a module actually named "Please take the survey!") →
  a plain ubboard instance not used for notices/Q&A, should be ignored by our tools

So: call `core_course_get_contents`, filter `modname == "ubboard"`, parse `customdata`,
and you have the board's module id (`id`, used as `?id=` in all ubboard URLs) with no
separate scrape needed to *find* the board.

## 3. List view — `GET /mod/ubboard/view.php?id=<module_id>`

Pagination params (not yet exercised against >1 page live, since the largest real board
found had 2 posts): `?id=<id>&listsize=15&page=<n>` (`listsize` options seen in the UI:
15/30/50/100/0=all).

Total post count: `div.totalcount` text (English UI: `"Total 1 items"`, Korean UI:
`"총1개"` — **don't regex-match the English phrase**, just read the `<span>` inside
`div.totalcount`, or better, count list rows directly).

Each post is one row: `div.grid-row.grid-row-notice` (sibling of a
`div.grid-row.grid-row-header` which is the column-header row, skip it). An empty board
renders `div.grid-row.grid-row-nodata` instead of any data rows.

Per-row fields (selectors relative to the row):
| Field | Selector | Notes |
|---|---|---|
| Post/article id + board id | `.grid-cell-subject a[href]` | href is `article.php?...&bwid=<post_id>&id=<board_id>` — **`bwid` is the actual post id**, `id` is the board module id (same as the list page's `?id=`) |
| Title | `.grid-cell-subject a .text-truncate.text` | plain text |
| Writer | `.grid-cell-writer .text-truncate` | display name (for Notices, this is the instructor) |
| Date | `.grid-cell-date span[title]` | `title` attr has full timestamp `"2026-08-28 14:06:15"`, visible text is date-only `"2026-08-28"` — **use the `title` attribute for full precision** |
| View count | `.grid-cell-viewcount .count` | plain integer text |

## 4. Detail view — `GET /mod/ubboard/article.php?id=<board_id>&bwid=<post_id>`

| Field | Selector | Notes |
|---|---|---|
| Title | `h3.article-title` | |
| Writer | `.subject-box-description .csms-user-picture .text-truncate` | same shape as list view |
| Date | `.subject-description-date` | full `"2026-08-28 14:06:15"` as plain text here (no separate `title` attr needed) |
| View count | `.subject-description-viewcount` (strip the icon, keep the trailing number) | |
| Body | `.article-content .text_to_html` | **inner HTML** (not text) — contains real `<p>`/`<span>` markup, must be preserved or explicitly stripped, not just `.get_text()`'d blindly if we want to keep formatting |
| Attachments | not observed — the one real post found had none. No `.attach`/`.pluginfile` link present on that page. **Unverified**; re-check once a post with an attachment exists |

The detail page also re-embeds the same list-view row markup below the article (a
"related posts" style list) — same selectors as section 3 apply there too, harmless to
ignore or reuse.

## 5. Q&A reply/thread structure

**Not verified.** No Q&A board on this test account has any post at all (scanned every
enrolled course; all Q&A boards show 0 items). The list/detail selectors above almost
certainly apply to Q&A too (same `ubboard` module, same theme), but the **reply/threading
DOM structure has never been seen** and must be captured before implementing #23
(`list_qna`/`get_qna_detail`) for real. Flagging as a follow-up check, not blocking Phase 2
list/detail work on Notices, but needed before trusting the Q&A read path.

## 6. Write form — `GET /mod/ubboard/write.php?id=<board_id>`

A "Write" link/button (`.../write.php?id=<id>`) is present on Q&A board list pages for
this student account, but **not** on Notices board list pages (students can't post
Notices — instructor-only, as expected). Form fields (relevant to issue #26,
`ubboard/writer.py`):

```
id=<board_id>                  # which board
coursemostype=insert           # "insert" for a new post
bwid=                          # empty for new post; presumably set to parent post id for a reply -- UNVERIFIED
rnum=                          # empty, purpose unclear -- UNVERIFIED
sesskey=<csrf token>           # REQUIRED, from the post-login page's M.cfg.sesskey
_qf__mod_ubboard_write_form=1  # Moodle mform marker, must be present
mform_isexpanded_id_general-ubboard=1
subject=<title>
secret=1                       # "secret/private post" checkbox, defaults to checked
content[text]=<body>           # the actual post body (Moodle editor field convention)
content[format]=1
content[itemid]=<random draft id>  # Moodle draft-area id for the rich text editor; must be
                                     # read from the GET'd form, not invented
attachment=<random draft id>   # separate draft-area id for file attachments
submitbutton=Save
cancel=Cancel
```

`content[itemid]` and `attachment` are Moodle's per-form-load random draft item ids —
**must be scraped fresh from each `GET write.php` response**, not hardcoded or reused
across requests.

**Not verified**: what a reply (as opposed to a fresh Q&A question) looks like — whether
it reuses `write.php` with `bwid` set to the parent post's id, or a different endpoint
entirely. No existing post to reply to on this account to check against.

## 7. Answers to the specific questions from issue #19

- **Is the ubboard module id different from course_id?** Yes, always — it's a normal
  Moodle course-module id (same namespace as any other activity), unrelated to the
  course id itself.
- **How are notices vs Q&A distinguished?** `customdata.type` (`"notice"` vs `"qna"`),
  available directly from `core_course_get_contents` — no extra scrape needed.
- **Can course contents give us the board id without extra navigation?** Yes, confirmed
  (section 2).

## Summary for downstream issues

- **#20** (cookie-session login): use `logintab=univ`, form details in section 1.
- **#21** (parser.py): list + detail selectors in sections 3–4 are ready to implement
  and unit-test against the fixtures. Q&A-specific reply parsing is not ready — no real
  data to validate against.
- **#22** (`list_notices`/`get_notice_detail`): fully unblocked.
- **#23** (`list_qna`/`get_qna_detail`): list/detail structurally the same as Notices,
  but **thread/reply nesting is unverified** — treat as higher-risk, re-check against a
  real Q&A thread before considering it done.
- **#26** (`ubboard/writer.py`): form field map is in section 6; still need to see a real
  reply to confirm the `bwid` reuse theory before implementing replies (question-posting
  should be safe to implement from what we have).
