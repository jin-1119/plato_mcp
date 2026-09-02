# PLATO MCP — 프로젝트 계획

> 부산대학교 LMS **PLATO**(https://plato.pusan.ac.kr/, Moodle 4.5.13 기반)를 다루는 MCP 서버.
> 레포: https://github.com/jin-1119/plato_mcp
> Project 보드: https://github.com/users/jin-1119/projects/1

## 한눈에 보기

| 항목 | 내용 |
|---|---|
| 목표 | AI(Claude)가 PLATO에 직접 안 들어가도 강좌 자료·공지·과제·성적·Q&A를 조회/작성/다운로드하도록 |
| v1 범위 | 읽기 + 쓰기(과제 제출, Q&A 글쓰기) + 파일 다운로드 **전부 포함** |
| 배포처 | Smithery (공개 MCP 마켓플레이스) |
| 자격증명 정책 | 서버 코드가 학번/비밀번호를 디스크에 저장하지 않음. Smithery per-user config로 주입 → 세션 메모리에서만 사용 |
| 언어/SDK | Python, 공식 `mcp` SDK (FastMCP) |

## 확인된 핵심 사실

1. **PLATO는 Moodle 기반**이고, `login/token.php`(service=`moodle_mobile_app`)로 wstoken 발급이 실제로 됨 — 439개 공식 webservice 함수가 열려있음을 실제 호출로 검증.
2. **공식 API로 되는 것**: 강좌 목록/콘텐츠, 과제 목록/제출, 성적, 캘린더, 쪽지·알림, **파일 다운로드**(fileurl에 `?token=` 붙이면 끝, PDF 다운로드 실제 테스트 성공).
3. **공식 API로 안 되는 것 — 공지사항/Q&A**: 부산대가 표준 Moodle forum 대신 자체 `ubboard` 커스텀 모듈을 씀 (`modname: "ubboard"`, `/mod/ubboard/view.php?id=...`). 439개 함수 중 대응 함수 없음 → **HTML 스크레이핑 필요** (`requests` 세션 쿠키 로그인 방식, SSO 없어서 Playwright 불필요).
4. robots.txt가 `Disallow: /`로 전체 크롤링을 막고 있어 공개 배포 시 법적/약관 리스크 있음 → README에 디스클레이머 필수, 서버는 자격증명 미저장, rate limiting 적용.

상세 조사 원문: [`PLATO_MCP_사전조사.md`](./PLATO_MCP_사전조사.md)

## 아키텍처

```
src/plato_mcp/
├── server.py            # FastMCP 앱, tool 등록 진입점
├── config.py            # Smithery config 스키마 (pnu_id, pnu_password, ...)
├── auth.py              # 세션별 wstoken + requests.Session 쿠키 in-memory 캐시
├── moodle_client.py     # webservice/rest/server.php 범용 REST 호출 래퍼
├── ubboard/
│   ├── scraper.py       # list_notices/get_notice_detail/list_qna/get_qna_detail (읽기)
│   ├── writer.py        # post_qna_question/reply_to_qna (쓰기, sesskey 처리)
│   └── parser.py        # BeautifulSoup 파싱 (HTML 구조 바뀌면 여기만 수정)
├── files.py              # download_course_file
├── tools/                 # MCP tool 등록 (courses/assignments/grades/calendar/messages/notices_qna/downloads)
├── models.py               # pydantic 응답 스키마
├── errors.py                # 타입 예외 (AuthError, MoodleAPIError, ScrapeError, RateLimitError)
└── security.py               # 로그/자격증명 마스킹, rate limiter
```

인증 흐름: 세션 시작 시 `login/token.php`로 wstoken 발급 → 메모리 캐시. ubboard 접근 시에만 추가로 쿠키 로그인 → `sesskey` 스크레이핑. 어떤 경우도 디스크에 저장 안 함.

## Phase 및 GitHub 이슈

| Phase | 부모 이슈 | 내용 | 하위 이슈 |
|---|---|---|---|
| 0 | [#1](https://github.com/jin-1119/plato_mcp/issues/1) | 프로젝트 부트스트랩 | [#9](https://github.com/jin-1119/plato_mcp/issues/9) 스켈레톤 · [#10](https://github.com/jin-1119/plato_mcp/issues/10) auth.py · [#11](https://github.com/jin-1119/plato_mcp/issues/11) moodle_client.py |
| 1 | [#2](https://github.com/jin-1119/plato_mcp/issues/2) | 공식 API 읽기 도구 | [#12](https://github.com/jin-1119/plato_mcp/issues/12) list_courses · [#13](https://github.com/jin-1119/plato_mcp/issues/13) get_course_contents · [#14](https://github.com/jin-1119/plato_mcp/issues/14) assignments · [#15](https://github.com/jin-1119/plato_mcp/issues/15) grades · [#16](https://github.com/jin-1119/plato_mcp/issues/16) calendar · [#17](https://github.com/jin-1119/plato_mcp/issues/17) messages · [#18](https://github.com/jin-1119/plato_mcp/issues/18) 통합 스모크테스트 |
| 2 | [#3](https://github.com/jin-1119/plato_mcp/issues/3) | ubboard 스크레이퍼(읽기) | [#19](https://github.com/jin-1119/plato_mcp/issues/19) 🚧HTML 구조 분석(BLOCKER) · [#20](https://github.com/jin-1119/plato_mcp/issues/20) 쿠키 로그인 · [#21](https://github.com/jin-1119/plato_mcp/issues/21) parser.py · [#22](https://github.com/jin-1119/plato_mcp/issues/22) list_notices · [#23](https://github.com/jin-1119/plato_mcp/issues/23) list_qna |
| 3 | [#4](https://github.com/jin-1119/plato_mcp/issues/4) | 쓰기 작업 | [#24](https://github.com/jin-1119/plato_mcp/issues/24) 확인 플로우 설계 · [#25](https://github.com/jin-1119/plato_mcp/issues/25) submit_assignment · [#26](https://github.com/jin-1119/plato_mcp/issues/26) writer.py · [#27](https://github.com/jin-1119/plato_mcp/issues/27) post/reply Q&A |
| 4 | [#5](https://github.com/jin-1119/plato_mcp/issues/5) | 파일 다운로드 | [#28](https://github.com/jin-1119/plato_mcp/issues/28) download_course_file |
| 5 | [#6](https://github.com/jin-1119/plato_mcp/issues/6) | Smithery 배포 | [#29](https://github.com/jin-1119/plato_mcp/issues/29) 배포방식 확인 · [#30](https://github.com/jin-1119/plato_mcp/issues/30) smithery.yaml/Dockerfile · [#31](https://github.com/jin-1119/plato_mcp/issues/31) README 디스클레이머 · [#32](https://github.com/jin-1119/plato_mcp/issues/32) 공개 릴리즈 |
| 6 | [#7](https://github.com/jin-1119/plato_mcp/issues/7) | 능동 알림 (2차, 보류) | [#33](https://github.com/jin-1119/plato_mcp/issues/33) 채널 설계 스파이크 |
| - | [#8](https://github.com/jin-1119/plato_mcp/issues/8) | 보안/개인정보 (전체 관통) | [#34](https://github.com/jin-1119/plato_mcp/issues/34) 로그 마스킹 · [#35](https://github.com/jin-1119/plato_mcp/issues/35) rate limiting · [#36](https://github.com/jin-1119/plato_mcp/issues/36) 제3자 PII 검토 · [#37](https://github.com/jin-1119/plato_mcp/issues/37) 쓰기 도구 어뷰징 검토 |

## 지금 바로 시작 가능한 이슈 (Ready, 의존성 없음)

- **[#9](https://github.com/jin-1119/plato_mcp/issues/9)** — Python 프로젝트 스켈레톤 (모든 것의 시작점)
- **[#19](https://github.com/jin-1119/plato_mcp/issues/19)** — 🚧 `[BLOCKER]` ubboard HTML 구조 분석
- **[#24](https://github.com/jin-1119/plato_mcp/issues/24)** — 쓰기 작업 확인 플로우 설계
- **[#29](https://github.com/jin-1119/plato_mcp/issues/29)** — Smithery Python 배포 방식 확인
- **[#31](https://github.com/jin-1119/plato_mcp/issues/31)** — README 디스클레이머

## 의존관계 요약

```
#9 → #10 → #11 → {#12~#17} → #18
#10 → #19[BLOCKER] → #20 → #21 → {#22,#23}
#24 (독립)
#14 + #24 → #25
#19 + #20 → #26 → #27 (#24 필요)
#13 + #10 → #28
#29(독립) → #30(+#9) → #31(독립) → #32 (#18,#22,#23,#25,#27,#28,#30,#31,#34,#37 필요)
#33 완전 보류
#34 지속적, #32 전에 재검증
#35 needs #11 + #20
#36 needs #21 + #23
#37 needs #24,#25,#27, #32 전에 완료 필수
```

## 참고 문서

- 사전 조사: [`PLATO_MCP_사전조사.md`](./PLATO_MCP_사전조사.md)
- 이전 계획 초안: [`PLATO_MCP_계획.md`](./PLATO_MCP_계획.md) (이 파일이 최신 정리본)
