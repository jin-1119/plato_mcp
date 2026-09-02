# PLATO MCP 서버 구축 계획

작성일: 2026-09-02

## 0. 확정된 방향

- **AI가 할 수 있는 범위**: 조회(읽기) + 쓰기(과제 제출, Q&A 글쓰기 등) + 자료(pdf 등) 다운로드까지 전부 포함
- **배포 방식**: Smithery(또는 유사 MCP 마켓플레이스)에 공개 배포
- **자격증명 저장 정책**: 서버는 학번/비밀번호를 저장하지 않음. 사용자가 자기 Claude/MCP 설정에 직접 입력 → 요청 시 서버로 전달 → 서버는 세션 동안만 메모리에 보관, 디스크 저장 안 함
- **ubboard(공지/Q&A) 세션 관리**: `requests` 세션 쿠키 방식 (Playwright 불필요 — PLATO 로그인폼이 SSO 없는 자체 로그인으로 확인됨)
- **능동 알림(polling)**: 1차 범위에서 제외. 기본 도구(조회/쓰기/다운로드)부터 완성 후 2차로 추가

## 1. 사전 조사에서 확인된 사실

| 항목 | 상태 | 방법 |
|---|---|---|
| 강좌 목록 | ✅ 가능 | `core_enrol_get_users_courses` (공식 API) |
| 강좌 콘텐츠(주차별 자료·링크·파일) | ✅ 가능 | `core_course_get_contents` (공식 API) |
| 과제 목록/제출현황 | ✅ 가능 | `mod_assign_get_assignments`, `mod_assign_get_submission_status` (공식 API) |
| 과제 제출 (쓰기) | ✅ 가능 (함수 존재 확인) | `mod_assign_save_submission` (공식 API) |
| 성적 | ✅ 가능 | `gradereport_user_get_grade_items` (공식 API, 강좌별로 권한에 따라 막힐 수 있음) |
| 캘린더 일정 | ✅ 가능 | `core_calendar_get_calendar_events` (공식 API) |
| 쪽지/알림함 | ✅ 가능 | `core_message_get_messages` 등 (공식 API) |
| **공지사항(Notices)** | ❌ 공식 API 없음 → **스크레이핑 필요** | `modname: "ubboard"` — 부산대 자체 커스텀 게시판 모듈, 439개 공식 함수 중 대응 함수 없음. `/mod/ubboard/view.php?id=...` HTML 파싱 필요 |
| **Q&A 게시판** | ❌ 공식 API 없음 → **스크레이핑 필요** | 위와 동일한 ubboard 모듈 |
| 표준 Moodle 포럼 | 미사용 확인 | `mod_forum_get_forums_by_courses` 호출 시 빈 배열 — 학교가 ubboard로 대체함 |

**결론**: 강좌자료·과제·성적·캘린더·쪽지는 **공식 Moodle Web Service API**로, **공지사항/Q&A만 스크레이핑**으로 처리하는 하이브리드 구조가 필요.

## 2. 아키텍처

```
mcp_server/
├── server.py           # FastMCP 앱, MCP tool 등록 진입점
├── moodle_client.py     # 공식 webservice REST 호출 래퍼 (courses/contents/assignments/grades/calendar/messages)
├── ubboard_scraper.py    # requests 세션 로그인 + BeautifulSoup 파싱 (공지/Q&A)
├── auth.py               # 세션별 wstoken + requests.Session 쿠키 in-memory 캐시 (디스크 저장 안 함)
├── models.py              # 응답 스키마 (pydantic)
├── smithery.yaml           # Smithery 배포 설정 (사용자 config 스키마: pnu_id, pnu_password)
└── Dockerfile
```

### 인증 흐름
1. 사용자가 Smithery 설치 시 `pnu_id`, `pnu_password`를 자기 config로 입력 (Smithery의 per-user config 주입 방식 사용)
2. 서버는 세션 시작 시 또는 첫 tool 호출 시:
   - `login/token.php` 호출 → wstoken 발급 → 메모리 캐시 (세션 종료 시 폐기)
   - ubboard 접근이 필요하면 `requests.Session`으로 `/login/index.php`에 로그인 → 쿠키 메모리 캐시
3. 어떤 credential도 로그 출력/디스크 저장하지 않음

## 3. MCP 도구(tool) 목록

### 읽기
- `list_courses` — 수강 강좌 목록
- `get_course_contents(course_id)` — 주차별 자료/링크/파일 구조 (파일 URL 포함)
- `list_assignments(course_id)` / `get_assignment_detail(assignment_id)` — 과제 목록/상세/마감일/제출현황
- `get_grades(course_id)` — 성적
- `list_calendar_events(days_ahead)` — 다가오는 일정
- `list_notices(course_id)` — 공지사항 목록 (ubboard 스크레이핑)
- `get_notice_detail(notice_id)` — 공지 상세 (ubboard 스크레이핑)
- `list_qna(course_id)` / `get_qna_detail(post_id)` — Q&A 게시판 (ubboard 스크레이핑)
- `get_unread_messages` — 안 읽은 쪽지/알림

### 쓰기
- `submit_assignment(assignment_id, file_path_or_text)` — 과제 제출
- `post_qna_question(course_id, title, content)` — Q&A 질문 작성 (ubboard 스크레이핑, form POST)
- `reply_to_qna(post_id, content)` — Q&A 답글

### 다운로드
- `download_course_file(file_url, save_path)` — 강의자료(pdf 등) 다운로드

## 4. 단계별 로드맵

- **Phase 0 (완료)**: `login/token.php` 활성화 확인, 439개 함수 목록 확보, ubboard 발견
- **Phase 1**: 공식 API 기반 읽기 도구 (`list_courses`, `get_course_contents`, `list_assignments`, `get_grades`, `list_calendar_events`, `get_unread_messages`) — 로컬에서 Claude Desktop에 연결해 테스트
- **Phase 2**: ubboard 스크레이퍼 (`list_notices`, `get_notice_detail`, `list_qna`) — HTML 구조 분석 후 파싱기 작성
- **Phase 3**: 쓰기 작업 (`submit_assignment`, `post_qna_question`, `reply_to_qna`) — 실수로 잘못 제출되는 걸 막기 위해 tool 설명에 "실행 전 사용자 확인 필요" 명시, 가능하면 dry-run 옵션 제공
- **Phase 4**: `download_course_file` — 파일 크기/타입 제한
- **Phase 5**: Smithery 패키징 (`smithery.yaml`, Dockerfile, README에 "본인 계정 용도 한정" 안내 + 학교 이용약관 관련 디스클레이머)
- **Phase 6 (2차)**: 능동 알림 — 채널 결정 후 별도 폴링 서비스 설계

## 5. 남은 리스크/확인 필요 사항

- Smithery가 Python 기반 MCP 서버 배포를 어떤 방식(Docker/stdio 등)으로 지원하는지 실제 배포 전에 Smithery 문서 확인 필요
- 공개 배포 시 학교 이용약관/robots.txt(`Disallow: /`) 위반 가능성 — README에 "본인 계정 개인 용도로만 사용, 오남용 시 책임은 사용자에게 있음" 명시 권장
- ubboard 글쓰기(POST) 시 CSRF 토큰(sesskey) 처리 필요 — 실제 폼 구조 확인 후 구현
- 쓰기 작업(과제 제출 등)은 되돌리기 어려우므로 Phase 3에서 신중한 확인 절차 설계 필요
