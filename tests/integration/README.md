# Integration smoke tests

These are opt-in, hit the real PLATO server with real credentials from
`.env`, and are **not** run in CI. Use `scripts/smoke_test_phase1.py`.

```bash
python scripts/smoke_test_phase1.py
```

## Phase 1 checklist (issue #18)

Run against a real PLATO account with at least one enrolled course.

- [x] `list_courses` — returns the account's actual enrolled courses (verified: 10 real courses)
- [x] `get_course_contents` — section/module structure matches the browser view (verified against 거시경제학, id=6253)
- [x] `list_assignments` — runs without error (verified: 0 live assignments existed at test time across
      enrolled courses, so only the empty-list path was exercised live; the populated path is covered by
      unit tests in `tests/unit/test_tools.py`)
- [x] `get_assignment_detail` — same caveat as above; structurally verified via unit tests only
      (submitted / not-submitted / late paths), since no real assignment existed to submit to
- [x] `get_grades` — returns real grade items for a course with visible grades (verified: 9 items for 6253);
      the `nopermissiontoviewgrades` path was also hit live (against course 12633, an exchange-program
      course with restricted grades) and returned `available=False` instead of crashing
- [x] `list_calendar_events` — returns 0 events when no events fall in the lookahead window (verified: the
      only two real events on this account are in the past, so an empty result is the *correct* answer,
      not a bug -- confirmed by checking their raw timestamps)
- [x] `get_unread_messages` — returns real unread notifications (verified: 3 real "new login" notifications)

## Phase 2 checklist (issues #19-#23)

- [x] `list_notices` — returns the real notice for 재무관리 (course 5973), matches the browser exactly
      (title/writer/date/view count); empty boards (e.g. 6253) return `[]`
- [x] `get_notice_detail` — matches the browser for the same real notice
- [x] `list_qna` — verified against 3 real courses, all return `[]` (every Q&A board on this account is
      genuinely empty, confirmed live)
- [ ] `get_qna_detail` — **never exercised against a real post.** No course on this account has ever had a
      Q&A question posted (checked live across all 10 enrolled courses). Implemented by reusing the same
      detail-page parser as `get_notice_detail` (same ubboard theme), which is a reasonable assumption but
      not a verified one for the Q&A board specifically. **Replies/threads are not parsed at all** -- no
      such page has ever been observed to know its markup. Re-run this once a real Q&A question (ideally
      with at least one reply) exists, and check `docs/ubboard_structure.md` section 5 for what's still
      unknown.

## Phase 3 checklist (issue #25)

- [x] `submit_assignment` (dry_run path) — sanity-checked against a real course: correctly resolves
      real assignment metadata via `list_assignments_for` and raises `ValueError` for a nonexistent
      assignment id
- [ ] `submit_assignment` (dry_run=False, real submission) — **never exercised.** No course on this
      account has ever had a real assignment to submit to. `mod_assign_save_submission` and its
      `plugindata[onlinetext_editor][...]` field names are verified against Moodle 4.5 source
      (`mod/assign/submission/onlinetext/locallib.php`), not against a live response. Re-run once a
      real assignment exists -- ideally a low-stakes test one, not a real graded submission.

## Phase 3 checklist (issues #26-#27)

- [x] `_fetch_write_form_tokens` (GET only) — verified live against the real Q&A write form:
      sesskey and both per-load draft-area ids extracted correctly
- [x] `post_qna_question` (dry_run path) — verified live: resolves the real Q&A board id (37083)
      and builds a correct preview, no request sent
- [ ] `post_new_thread` / `post_qna_question` (dry_run=False, real POST) — **deliberately not
      exercised live.** Unlike every read-only tool so far, this creates a real, visible post on
      a real course Q&A board -- doing that needs the user's explicit go-ahead (which was asked
      and deferred for now), not routine automated verification. When this is picked up: post one
      low-stakes test question, confirm it appears via `list_qna`, then decide whether/how to
      remove it (no delete tool exists yet).
- [ ] `reply_to_qna` — **not implemented at all.** The reply/thread POST mechanism (does it reuse
      `write.php` with `bwid` set to the parent post id? a different endpoint?) has never been
      observed -- no real Q&A thread exists anywhere on this account to reply to. See
      `docs/ubboard_structure.md` section 6. Needs a real thread to exist before this can be built
      on anything other than a guess.

## Known gap

`list_assignments`/`get_assignment_detail`'s "assignment exists and has a submission" path has never
been exercised against a live server, because no course in the test account currently has an assignment
posted. Re-run this checklist once a real assignment appears, or before Phase 3 (issue #17, submit_assignment)
starts -- that work will need a real assignment to test against anyway.

`AssignmentSummary`/`SubmissionStatus`/`SubmissionFeedback`/`PreviousAttempt`/`AssignmentExtraData` were
expanded (cmid, cutoffdate, gradingduedate, intro/introattachments, activity/activityattachments,
maxattempts, attemptreopenmethod, teamsubmission, cansubmit, locked, extensionduedate, gradingstatus,
feedback.grade/plugins, previousattempts, assignmentdata) based on reading Moodle 4.5's
`mod/assign/externallib.php` source directly (MOODLE_405_STABLE, matching PLATO's actual 4.5.13 release) --
field names are trustworthy, but none of it has been checked against a real PLATO response yet. When a
real assignment shows up, re-run `get_assignment_detail` against it and confirm every new field actually
appears with the expected shape (especially `feedback.plugins[].editorfields[].text`, which is where an
instructor's written feedback comment should show up).
