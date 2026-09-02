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

## Known gap

`list_assignments`/`get_assignment_detail`'s "assignment exists and has a submission" path has never
been exercised against a live server, because no course in the test account currently has an assignment
posted. Re-run this checklist once a real assignment appears, or before Phase 3 (issue #17, submit_assignment)
starts -- that work will need a real assignment to test against anyway.
