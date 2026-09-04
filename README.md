# plato-mcp

[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Status: WIP](https://img.shields.io/badge/status-work%20in%20progress-orange)](./PLAN.md)
[![Unofficial](https://img.shields.io/badge/PNU-unofficial%20project-red)](#면책조항)

부산대학교(PNU)의 무들(Moodle) 기반 LMS인 **PLATO**(https://plato.pusan.ac.kr/)를 위한 비공식
[MCP](https://modelcontextprotocol.io/)(Model Context Protocol) 서버입니다. Claude 같은 AI
어시스턴트가 여러분을 대신해 PLATO에 로그인하지 않고도, 여러분이 이미 접근 권한을 가진
강좌 자료·공지·과제·성적·Q&A를 조회·작성·다운로드할 수 있게 해 줍니다.

> **아직 개발 중입니다.** 전체 구현 계획은 [`PLAN.md`](./PLAN.md)를, 현재 진행 상황은
> [GitHub Issues](https://github.com/jin-1119/plato_mcp/issues) /
> [Project 보드](https://github.com/users/jin-1119/projects/1)를 참고하세요.

> **이 서버는 새로운 권한을 부여하지 않습니다.** 여러분의 PLATO 학번·비밀번호로 인증하며,
> 브라우저로 직접 열람할 때 볼 수 있는 것만 볼 수 있습니다 — 다만 그 내용이 AI와의 대화로
> 흘러 들어간다는 차이가 있습니다. 시작하기 전에 아래 [면책조항](#면책조항)과
> [개인정보 안내](#개인정보-안내)를 반드시 읽어 주세요.

```bash
pip install -e ".[dev]"
pytest
```

Smithery를 통한 배포/설치 방법은 [`smithery.yaml`](./smithery.yaml)을,
자격증명이 어떻게 다뤄지는지는 [`SECURITY.md`](./SECURITY.md)를 참고하세요.

---

## 제공하는 도구 (MCP Tools)

공식 Moodle webservice API로 동작하는 도구와, `ubboard`(공지/Q&A) HTML을 본인 세션으로
스크레이핑하는 도구로 나뉩니다. 쓰기 도구(✏️)는 실행 전 확인 절차를 거칩니다
(자세한 내용은 [`docs/write_confirmation_pattern.md`](./docs/write_confirmation_pattern.md)).

**강좌 / 과제 / 성적 / 일정 / 쪽지** — 공식 API

- `list_courses` — 수강 중인 강좌 목록
- `get_course_contents` — 강좌 콘텐츠(주차별 자료 등)
- `list_assignments` — 과제 목록
- `get_assignment_detail` — 과제 상세
- `submit_assignment` ✏️ — 과제 제출
- `get_grades` — 성적 조회
- `list_calendar_events` — 캘린더 일정
- `get_unread_messages` — 안 읽은 쪽지

**공지사항 / Q&A(`ubboard`)** — 로그인 세션 스크레이핑

- `list_notices` — 공지사항 목록
- `get_notice_detail` — 공지사항 상세
- `list_qna` — Q&A 게시글 목록
- `get_qna_detail` — Q&A 게시글 상세
- `post_qna_question` ✏️ — Q&A 질문 등록

**파일**

- `download_course_file` — 강좌 첨부파일 다운로드 (원격 실행 시 링크 반환, 위
  [개인정보 안내](#개인정보-안내) 참고)

## 아키텍처

```
src/plato_mcp/
├── server.py            # FastMCP 앱, tool 등록 진입점
├── config.py            # Smithery config 스키마 (pnu_id, pnu_password, ...)
├── auth.py              # 세션별 wstoken + requests.Session 쿠키 in-memory 캐시
├── moodle_client.py     # webservice/rest/server.php 범용 REST 호출 래퍼
├── ubboard/
│   ├── scraper.py       # list_notices/get_notice_detail/list_qna/get_qna_detail
│   ├── writer.py        # post_qna_question (sesskey 처리)
│   └── parser.py        # BeautifulSoup 파싱
├── files.py             # download_course_file
├── tools/                # MCP tool 등록 (courses/assignments/grades/calendar/messages/notices_qna/downloads)
├── models.py              # pydantic 응답 스키마
├── errors.py               # 타입 예외 (AuthError, MoodleAPIError, ScrapeError, RateLimitError)
└── security.py              # 로그/자격증명 마스킹, rate limiting
```

인증 흐름: 세션 시작 시 `login/token.php`로 wstoken을 발급받아 메모리에 캐시합니다.
`ubboard`(공지/Q&A) 접근 시에만 추가로 쿠키 로그인을 수행해 `sesskey`를 스크레이핑합니다.
어떤 경우도 디스크에 저장하지 않습니다. 배경이 된 사전 조사는
[`PLATO_MCP_사전조사.md`](./PLATO_MCP_사전조사.md), 전체 로드맵은
[`PLAN.md`](./PLAN.md)를 참고하세요.

---

## 개발

**사전 요건**

- Python 3.11+
- 로컬 개발/테스트에는 실제 PLATO 계정이 필요 없습니다 (테스트는 mock 기반)

```bash
pip install -e ".[dev]"
pytest
```

--- 

## 면책조항

- **부산대학교(PNU) 또는 PLATO/무들 플랫폼과 아무런 제휴 관계가 없으며, 이들의 승인을
  받지 않았습니다.** 이 프로젝트는 여러분이 이미 브라우저로 하고 있는 것과 동일한 PLATO
  계정 접근을 자동화하는 독립적인 커뮤니티 프로젝트입니다 — 새로운 권한을 부여하지 않으며
  PNU를 대신해 어떠한 행위도 하지 않습니다.
- **모든 사용은 본인 책임이며, PNU의 이용약관을 준수해야 합니다.** 특히 공지사항/Q&A
  게시판(`ubboard`)은 공식 API가 없어 로그인된 본인 세션으로 렌더링된 HTML을 직접
  스크레이핑하는데, 이 사이트의 `robots.txt`는 `Disallow: /`를 명시하고 있습니다. 이
  지침은 익명 크롤러를 겨냥한 것이며 인증된 사용자 본인의 열람 행위를 겨냥한 것은
  아니지만, 그래도 스크레이핑인 것은 사실입니다. 이 서버를 계정에 연결하기 전에 본인
  계정에 대한 PNU의 acceptable-use 정책에 부합하는지 확인할 책임은 사용자에게 있습니다.
  권장 사용 방식은 개인적·저빈도 사용이며, 사이트 전체를 대상으로 한 자동 대량
  스크레이핑은 권장하지 않습니다.
- **PLATO 로그인 정보는 이 서버에 의해 디스크에 영구 저장되지 않습니다.** 무엇이,
  얼마나 오래 저장/보관되는지 정확한 내용은 [`SECURITY.md`](./SECURITY.md)를
  참고하세요.
- **이 프로젝트는 제3자에 의한 독립적인 보안 감사를 받지 않았습니다.** 개발 과정에서
  자체적으로 여러 자격증명 처리·오남용 방지 이슈를 발견하고 수정했습니다
  (`docs/security_audit.md`, `docs/abuse_prevention_review.md` 참고) — 하지만
  스스로 찾아 고친 것은 외부 감사와 같은 수준의 보증이 아닙니다.

--- 

## 개인정보 안내

이 서버는 강좌 콘텐츠를 그대로 전달합니다 — Q&A 게시판의 경우 **다른 학생들의 이름과
게시글**도 포함됩니다. 이는 본인 계정이 PLATO를 통해 이미 정당하게 접근할 수 있는
내용이며, 이 도구가 새로운 접근 권한을 부여하는 것은 아닙니다. 브라우저로 PLATO를
직접 열람할 때와 다른 점은, 이 내용이 AI 어시스턴트와 나누는 대화의 일부가 된다는
것입니다. 즉 도구 출력으로서 해당 AI/LLM 제공업체(예: Anthropic)에 전송됩니다.
강좌 Q&A 게시판을 대상으로 폭넓은 질문을 하기 전에 이 점을 유념하세요.

전체 검토 내용과 알려진 미해결 사항(PLATO가 Q&A 게시글의 "비공개/강사 전용" 플래그를
서버 측에서 실제로 강제하는지 — 즉 이 도구가 그런 게시글을 애초에 볼 수 없는지 —
여부는 아직 실증적으로 검증되지 않았습니다)은
[`docs/pii_review.md`](./docs/pii_review.md)에서 확인할 수 있습니다.

**원격으로 실행할 경우** (로컬 Claude Code/Desktop이 아니라 Claude.ai 커넥터 등을
통해 실행하는 경우), 인라인 전송 크기 제한을 초과하는 큰 파일에 대해
`download_course_file`은 파일 자체가 아니라 다운로드 *링크*를 반환하며, 이 링크에는
살아있는 PLATO 액세스 토큰이 포함되어 있습니다. **이 토큰은 해당 파일 하나에만
한정되지 않습니다** — 실제로 확인해 본 결과 본인 계정에 대한 임의의 PLATO API 호출을
인증하는 데 사용할 수 있었습니다. 이 링크나 이 링크가 포함된 대화 기록을 공유하는
것은 파일 하나를 공유하는 것이 아니라 계정에 대한 활성 자격증명을 공유하는 것과
같습니다. 자세한 내용은 [`SECURITY.md`](./SECURITY.md)와
[`docs/smithery_deployment_model.md`](./docs/smithery_deployment_model.md)를
참고하세요.

- Lint: `ruff check .`
- 이슈/보드 운영 방식은 [`PLAN.md`](./PLAN.md#phase-및-github-이슈)를 참고하세요.
