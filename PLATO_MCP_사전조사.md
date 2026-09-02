# PLATO(부산대 LMS) MCP 서버 구축 사전 조사

조사일: 2026-09-02
대상: https://plato.pusan.ac.kr/

## 결론 요약

- **PLATO는 Moodle 기반 LMS**로 확인됨.
- 웹 스크레이핑으로 MCP 서버를 만드는 방식은 **실제로 널리 쓰이는 검증된 패턴** 맞음.
- 다만 PLATO는 **Moodle 공식 Web Service(REST) API가 활성화되어 있을 가능성이 높음** — 순수 스크레이핑보다 이 경로를 먼저 시도하는 것이 훨씬 안정적이고 정당한 방식.
- robots.txt가 전체 크롤링을 금지(`Disallow: /`)하고 있어, 공개 배포 시 법적/약관 리스크 검토 필요. 개인용(본인 계정만) 사용은 리스크가 상대적으로 낮음.

---

## 1. PLATO 플랫폼 식별 결과

HTML 구조 및 API 직접 호출로 Moodle 기반임을 확인:

- 로그인 경로: `/login/index.php`, `/login/register/agree.php` — Moodle 표준 경로
- 코스 조회: `/course/view.php?id=...` — Moodle 표준 URL 패턴
- 파일 서빙: `/pluginfile.php/...` — Moodle 특유 파일 시스템
- 테마: `theme/coursemos` (국내 Moodle 커스터마이징 업체가 자주 쓰는 테마)
- 모듈: `/mod/ubboard/` (Moodle 게시판 모듈)

### 결정적 증거 — Moodle 공식 Web Service API 응답 확인

```
GET /login/token.php
→ {"errorcode":"missingparam", ...}   (username 파라미터 누락 — Moodle 표준 응답)

GET /login/token.php?username=testuser123&password=wrongpass123&service=moodle_mobile_app
→ {"error":"다시 로그인해 주세요.","errorcode":"invalidlogin", ...}

GET /webservice/rest/server.php?wstoken=test&wsfunction=core_webservice_get_site_info&moodlewsrestformat=json
→ {"errorcode":"invalidtoken", ...}
```

`service=moodle_mobile_app`으로 토큰 발급 시도 시 "webservicesnotenabled"가 아니라 **"invalidlogin"**(로그인 정보 틀림) 오류가 반환됨 → **PLATO에서 Moodle Mobile 공식 앱용 Web Service가 실제로 활성화되어 있다는 강력한 근거**.

즉, 본인 학번/비밀번호로 `login/token.php`를 호출하면 정식 `wstoken`을 발급받고, 이후 `webservice/rest/server.php`를 통해 `core_course_get_courses`, `core_enrol_get_users_courses`, `mod_assign_get_assignments`, `gradereport_user_get_grade_items` 등 **Moodle 공식 REST API**를 정상 호출할 수 있을 가능성이 높음.

(단, SSO 연동 여부·모바일 앱 전용 제한(User-Agent/앱 서명 체크) 여부는 실제 계정으로 테스트해야 확실함)

## 2. robots.txt / 이용약관 제약

```
User-agent: *
Disallow: /
```

전체 사이트에 대해 크롤러 접근을 명시적으로 금지. 로그인 기반 사이트에서 흔한 설정이지만 자동화 접근 거부 의사로 해석될 여지 있음.

이용약관 원문은 로그인 필요 페이지로 추정되어 직접 확인 못함. 실제 구현 전 로그인 후 약관을 직접 확인 권장 (일반적으로 "자동접속 프로그램/매크로 사용 금지" 조항이 있는 경우가 많음).

## 3. 기술적 접근법

### 인증 방식 (우선순위)

1. **Moodle 공식 Web Service (1순위)**: `login/token.php`로 본인 자격증명 → `wstoken` 발급 → `webservice/rest/server.php?wstoken=...&wsfunction=...` 호출. 토큰은 로컬에 암호화 저장(OS keychain 권장), 평문 저장 금지.
2. **세션 쿠키 + 스크레이핑 (보조/폴백)**: 웹서비스로 커버 안 되는 기능(예: `ubboard` 게시판 등 커스텀 모듈)만 Playwright로 로그인 후 세션 쿠키(`MoodleSession`) 재사용, HTML 파싱.

→ **하이브리드 설계**: "가능하면 Web Service 호출 → 안 되면 스크레이핑 폴백" 구조 권장.

### MCP 도구(tool) 설계 예시

| 도구명 | 기능 |
|---|---|
| `list_courses` | 수강 중인 강좌 목록 |
| `get_course_content(course_id)` | 강좌 자료/주차별 콘텐츠 |
| `list_assignments(course_id)` / `get_assignment_detail(id)` | 과제 목록/상세, 마감일 |
| `get_grades(course_id)` | 성적/평가 항목 |
| `list_announcements` / `get_calendar_events` | 공지사항, 캘린더 일정 |
| `download_file(file_id)` | 강의자료 다운로드 |
| `submit_assignment(...)` | 과제 제출 (쓰기 작업은 별도 승인 절차 권장) |

### 사용 라이브러리

- MCP SDK: 공식 `@modelcontextprotocol/sdk` (TypeScript 또는 Python)
- 브라우저 자동화: **Playwright** (세션/컨텍스트 관리가 Puppeteer보다 용이)
- HTTP + 파싱: Python `httpx`/`requests` + `BeautifulSoup`, 또는 Node `cheerio`
- Moodle REST: 별도 SDK 불필요(단순 REST). Python `moodlepy` 래퍼도 존재

## 4. 참고할 기존 오픈소스 프로젝트

### Moodle 전용 MCP 서버 (공식 API 기반 — PLATO에 가장 참고할만함)

- [Jawadh-Salih/moodle-mcp-server](https://github.com/Jawadh-Salih/moodle-mcp-server) — 학생용, 강좌/성적/과제/마감일/알림 조회 목적이 PLATO 사용 사례와 거의 동일 (Go)
- [theredbluepill/moodle-mcp-server](https://github.com/theredbluepill/moodle-mcp-server)
- [Hefi002/tfg-mcp-moodle-server](https://github.com/Hefi002/tfg-mcp-moodle-server)
- [peancor/moodle-mcp-server](https://github.com/peancor/moodle-mcp-server)
- [loyaniu/moodle-mcp](https://github.com/loyaniu/moodle-mcp)
- [ijaureguialzo/moodle-webservice_mcp](https://github.com/ijaureguialzo/moodle-webservice_mcp) — 서버 관리자 권한으로 Moodle에 MCP 플러그인 설치하는 방식(개인 프로젝트로는 부적합)

### 로그인/SSO 기반 스크레이핑 MCP 서버 (설계 패턴 참고용)

- [pranav-vijayananth/brightspace-mcp-server](https://github.com/pranav-vijayananth/brightspace-mcp-server) — Purdue 대학, Playwright로 로그인+2FA(Duo Mobile) 처리 후 스크레이핑
- [bencered/d2l-mcp-server](https://github.com/bencered/d2l-mcp-server) — Playwright로 기관 SSO(MS 로그인) 자동화 + 세션 영속 저장, 과제/성적/캘린더/공지 도구 12개

PLATO(plato.pusan.ac.kr) 자체를 다루는 기존 프로젝트는 발견되지 않음 — 직접 만들어야 함.

## 5. 법적/윤리적 주의사항

- **한국 판례 동향**: 대법원 2022.5.12. 선고 2021도1533 판결 등은 크롤링의 형사처벌 가능성을 "이용약관이 자동접속 프로그램 사용을 명시적으로 금지했는지", "기술적 보호조치(로그인, robots.txt, CAPTCHA)를 우회했는지"로 판단. PLATO는 robots.txt로 전체 크롤링을 금지하고 로그인이라는 기술적 보호조치도 있으므로, 제3자 데이터를 대량 수집/재배포/공개 서비스화할 경우 법적 리스크 존재.
- **개인정보보호법**: 게시판, 조별과제 등에서 타인의 이름/게시글 등 개인정보가 노출될 수 있음 → 본인 정보 조회로 도구 범위 제한 필요.
- **개인용 vs 공개 배포 리스크 차이**:
  - **개인용(본인 계정, 로컬 사용)**: 본인이 이미 정당하게 접근 권한 있는 데이터를 자동화로 조회 → 상대적으로 리스크 낮음 (단, 학칙/정보보안 규정 위반 소지는 남을 수 있음).
  - **공개 배포/SaaS화**: 타인의 학번/비밀번호를 서버가 대리 처리/저장하면 개인정보보호법상 "개인정보처리자" 책임 발생, 대량 접속으로 인한 서버 부하 시 정보통신망법 문제 소지, 학교 측 계정 정지 리스크 큼. 공개 배포 고려 시 학교(정보화본부 등)에 사전 문의 권장.

### 권장 원칙

1. 가능하면 Moodle 공식 Web Service API 우선 사용 (스크레이핑 최소화)
2. 본인 계정 자격증명만 사용, 로컬에만 암호화 저장
3. 요청 빈도 제한(rate limiting)으로 서버 부하 방지
4. 개인용 도구로 한정, 공개 배포 전 학교 측과 협의

## 출처

- [부산대학교 AX·정보화혁신본부](https://uitc.pusan.ac.kr/uitc/53381/subview.do)
- [PLATO 사용법 - 부산대학교 스마트 교육플랫폼](https://graduate.pusan.ac.kr/gspa/12392/subview.do)
- [부산대학교 - 스마트 교육플랫폼 PLATO 안내](https://gsis.pusan.ac.kr/bbs/gsis/232/1240654/artclView.do)
- [Jawadh-Salih/moodle-mcp-server](https://github.com/Jawadh-Salih/moodle-mcp-server)
- [theredbluepill/moodle-mcp-server](https://github.com/theredbluepill/moodle-mcp-server)
- [Hefi002/tfg-mcp-moodle-server](https://github.com/Hefi002/tfg-mcp-moodle-server)
- [peancor/moodle-mcp-server](https://github.com/peancor/moodle-mcp-server)
- [loyaniu/moodle-mcp](https://github.com/loyaniu/moodle-mcp)
- [ijaureguialzo/moodle-webservice_mcp](https://github.com/ijaureguialzo/moodle-webservice_mcp)
- [pranav-vijayananth/brightspace-mcp-server](https://github.com/pranav-vijayananth/brightspace-mcp-server)
- [bencered/d2l-mcp-server](https://github.com/bencered/d2l-mcp-server)
- [대법원 2021도1533 판결 해설 - 법무법인 아틀라스](https://atlaw.kr/kr-blog/%EC%9B%B9%ED%81%AC%EB%A1%A4%EB%A7%81%EC%9D%98-%ED%98%95%EC%82%AC%EC%B2%98%EB%B2%8C-%EA%B0%80%EB%8A%A5%EC%84%B1-%EB%8C%80%EB%B2%95%EC%9B%90-2021%EB%8F%841533-%ED%8C%90%EA%B2%B0-%EC%99%84%EC%A0%84/
- [크롤링 관련 최근 대법원 판결과 그 시사점 - 신진앤김](https://www.shinkim.com/kor/media/newsletter/1843)
