# plato-mcp를 Smithery에 공개 배포하기 — 비전공자용 단계별 가이드

이 문서는 [#67](https://github.com/jin-1119/plato_mcp/issues/67) 작업(Smithery
배포 모델 변경 대응)을 실제로 따라 하기 위한 가이드입니다. 각 단계마다 **브라우저
화면에서 클릭하는 방법(GUI)**과 **터미널에 붙여넣는 방법(CLI)**을 둘 다 적어뒀으니,
편한 쪽으로 하시면 됩니다 — 화면에서 버튼을 못 찾겠으면 그 아래 CLI 명령어를
그대로 복사해서 터미널에 붙여넣으세요.

> Smithery 관련 화면/문구(3단계)는 2026-09-04 기준으로 실제 로그인해서 직접
> 확인한 내용입니다. Render와 Google Cloud Console 화면(1단계, 1B단계)은
> 이번엔 브라우저로 직접 재확인하지 못하고 알고 있는 최신 구성을 기준으로
> 적었습니다 — 버튼 이름이나 위치가 실제 화면과 살짝 다를 수 있으니, 안
> 맞는 부분이 있으면 알려주세요. 서비스들이 UI를 바꾸면 더 달라질 수 있습니다.

## 전체 그림

```
1) 어딘가에 이 서버를 올려서 "공개 인터넷 주소"를 하나 만든다
        ↓
2) 그 주소가 실제로 살아있는지 확인한다
        ↓
3) smithery.ai에 그 주소를 등록한다 (= "게시/배포")
        ↓
4) 등록이 잘 됐는지, 실제로 설치해서 도구 하나를 써본다
```

기존에 계획했던 "GitHub 저장소를 Smithery에 연결하면 Smithery가 알아서 빌드해서
호스팅해준다"는 방식은 **더 이상 지원되지 않습니다** (자세한 배경은
[`docs/smithery_deployment_model.md`](./smithery_deployment_model.md)의 addendum
참고). 그래서 1번 단계, 즉 "어딘가에 직접 올리는" 과정이 새로 필요합니다.

> **지금 상황**: 원래는 Google Cloud Run에 올리기로 했는데, GCP 결제 계정이
> 신분증/카드 심사 중이라 그게 끝날 때까지는 Cloud Run 배포가 막혀 있습니다
> (결제 계정 없이는 관련 API 자체를 켤 수 없음). 그래서 **카드 등록 없이 바로
> 시작할 수 있는 Render로 먼저 배포**하고, GCP 심사가 끝나면 원할 때 그대로
> Cloud Run으로 옮기기로 했습니다 (같은 `Dockerfile`을 그대로 쓰므로 옮기는
> 것 자체는 어렵지 않습니다). 아래 **1단계(Render, 지금)**를 먼저 진행하고,
> Cloud Run 절차는 **1단계-B(나중, 선택)**로 남겨뒀습니다.

---

## 1단계: Render에 지금 바로 배포하기 (카드 등록 불필요)

[Render](https://render.com)는 Google Cloud Run과 마찬가지로 "Dockerfile
하나만 있으면 인터넷 주소를 만들어주는" 서비스입니다. 무료 요금제는 **카드
등록 없이** 바로 쓸 수 있습니다. 이 프로젝트는 이미 `Dockerfile`이 준비되어
있어서 **코드를 하나도 고칠 필요 없이** 그대로 올릴 수 있습니다.

### 1-1. Render 가입

1. https://render.com 접속 → **Get Started** (또는 우측 상단 **Sign Up**).
2. **GitHub로 가입**하는 걸 추천합니다 (아래에서 저장소 연결이 자동으로
   더 쉬워집니다). GitHub 계정으로 로그인 승인.

### 1-2. 새 Web Service 만들기

1. 대시보드에서 **New +** 버튼 클릭 → **Web Service** 선택.
2. **Build and deploy from a Git repository** 선택 → **Next**.
3. 저장소 목록에서 **`jin-1119/plato_mcp`**를 찾아 **Connect**.
   - 목록에 안 보이면 **Configure account**를 눌러 Render가 그 저장소에
     접근할 수 있게 GitHub 쪽에서 권한을 승인해주세요.
4. 설정 화면에서:
   - **Name**: `plato-mcp`
   - **Region**: `Singapore` (한국에서 가장 가까운 지역)
   - **Branch**: `main`
   - **Language/Runtime**: **Docker** (저장소에 `Dockerfile`이 있으니
     Render가 자동으로 Docker로 잡아줄 것입니다. 안 잡히면 직접 Docker로
     바꿔주세요.)
   - **Instance Type**: **Free** 선택.
5. **Environment Variables** 섹션에서 **Add Environment Variable** 클릭:
   - Key: `MCP_TRANSPORT`, Value: `streamable-http`
   - (`PORT`는 Render가 자동으로 넣어주므로 따로 설정할 필요 없습니다 —
     이 서버 코드가 `PORT` 환경변수를 이미 읽도록 되어 있습니다.)
6. 맨 아래 **Deploy Web Service** 클릭.
7. 몇 분 정도 빌드 로그가 흐르며 배포됩니다. 끝나면 화면 위쪽에 서비스 주소
   (예: `https://plato-mcp.onrender.com`)가 보입니다.
   **이 주소를 복사해두세요 — 3단계에서 씁니다.**

### 1-3. 배포가 실제로 됐는지 확인

방금 복사한 주소 뒤에 `/mcp`를 붙여서 새 브라우저 탭에 그대로 입력해보세요
(예: `https://plato-mcp.onrender.com/mcp`). MCP 프로토콜은 원래 `POST`
요청으로만 응답하므로, 이렇게 주소창에 직접 쳐서 들어가면(=GET 요청)
**"Method Not Allowed" 같은 에러 화면이 뜨는 게 정상**입니다 — 이건 "서버가
살아있고, 응답은 하는데 이 방식의 요청은 안 받는다"는 뜻이라 오히려 성공
신호입니다. 반대로 페이지가 아예 안 뜨거나 "사이트에 연결할 수 없음" 같은
에러가 나오면 Render 대시보드의 **"Logs"** 탭에서 원인을 확인하세요.

> **무료 요금제 특징**: 15분 동안 요청이 없으면 서버가 잠들고(sleep), 다음
> 요청이 오면 다시 깨어나는 데 30초~1분 정도 걸립니다. 개인 저빈도 사용
> 목적이라 이 정도는 무방하지만, Smithery로 처음 접속할 때 "느리다"고
> 느껴지면 이 때문입니다 (버그가 아닙니다).

---

## 1단계-B (나중, GCP 결제 승인 후 — 선택): Google Cloud Run으로 옮기기

GCP 결제 계정 심사가 끝나면, 원할 경우 아래 절차로 Cloud Run에도 배포할 수
있습니다 (Render를 그대로 써도 무방하며, 이 단계는 선택 사항입니다). 같은
`Dockerfile`을 그대로 쓰므로 코드 변경은 필요 없습니다.

> **계정 안내**: 새 GCP 프로젝트를 `w72575535@gmail.com` 계정으로 만드셨다고
> 하셨으니, 브라우저는 그 계정으로 로그인한 상태에서 진행하세요 (오른쪽 위
> 프로필 아이콘 → 계정 전환/추가). CLI(터미널)로 진행할 경우 아래 1B-0을 먼저
> 하세요 — 이 컴퓨터의 `gcloud`는 현재 다른 계정(`jinyeonggim844@gmail.com`)으로
> 로그인되어 있습니다.

### 1B-0. (CLI만 해당) 터미널에서 올바른 계정/프로젝트로 전환

```bash
gcloud auth login
# 브라우저가 뜨면 w72575535@gmail.com으로 로그인

gcloud projects list
# 방금 만든 프로젝트의 PROJECT_ID를 확인

gcloud config set project <PROJECT_ID>
```

이후 CLI 명령어들은 전부 이 계정/프로젝트 기준으로 실행됩니다. (GUI로만 할
거면 이 단계는 건너뛰어도 됩니다.)

### 1B-1. 프로젝트 선택 확인

**GUI**

1. https://console.cloud.google.com 접속 (`w72575535@gmail.com`으로 로그인).
2. 화면 맨 위, 구글 클라우드 로고 옆에 있는 **프로젝트 선택 드롭다운**을
   클릭해서, 방금 만든 프로젝트가 선택되어 있는지 확인합니다. 아니라면
   목록에서 그 프로젝트를 선택하세요.

**CLI**

```bash
gcloud config get-value project
# 방금 만든 프로젝트 ID가 나오는지 확인. 아니면:
gcloud config set project <PROJECT_ID>
```

### 1B-2. (본인이 직접) 결제 계정이 연결돼 있는지 확인

> ⚠️ **이 부분은 Claude가 대신 할 수 없습니다.** 결제 카드 등록은 보안상 본인이
> 직접 해야 하는 영역입니다 — GUI든 CLI든 카드 등록 자체는 브라우저에서
> 진행해야 합니다.

**GUI**

1. 왼쪽 위 **≡ (메뉴)** 아이콘 클릭 → **결제(Billing)** 메뉴로 이동
   (또는 바로 https://console.cloud.google.com/billing/linkedaccount 접속).
2. 이 프로젝트에 결제 계정이 연결되어 있지 않다는 안내가 뜨면 **"결제 계정
   연결"**을 클릭해서, 있는 결제 계정을 연결하거나 없다면 **"결제 계정
   만들기"**로 새로 만들고 카드를 등록하세요.
3. 개인 저빈도 사용 기준으로는 Cloud Run 무료 한도(월 200만 요청) 안에서
   충분히 돌아가므로 **실제로 청구될 가능성은 거의 없습니다.** 다만 카드
   등록 자체는 구글 정책상 필수입니다.

**CLI (확인/연결만 — 카드 등록은 여전히 브라우저에서)**

```bash
gcloud billing accounts list
# 결제 계정이 있으면 ACCOUNT_ID가 나옵니다. 없으면 위 GUI 절차로 먼저 만드세요.

gcloud billing projects describe <PROJECT_ID> --format="value(billingEnabled)"
# False가 나오면 아래로 연결:
gcloud billing projects link <PROJECT_ID> --billing-account=<ACCOUNT_ID>
```

### 1B-3. 필요한 API 사용 설정

**GUI**

1. 화면 위쪽 검색창(🔍)에 `Cloud Run API`를 입력 → 나오는 결과 클릭 →
   **사용 설정(Enable)** 버튼 클릭. 이미 켜져 있으면 이 버튼 대신 "관리"가
   보이니 그대로 다음으로 넘어가면 됩니다.
2. 같은 방식으로 `Cloud Build API`, `Artifact Registry API`도 검색해서
   각각 사용 설정합니다.

**CLI**

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

### 1B-4. Cloud Run 서비스 만들기 (실제 배포)

**GUI**

1. 검색창에 `Cloud Run`을 입력 → **Cloud Run** 클릭.
2. **서비스 만들기(Create Service)** 버튼 클릭.
3. 배포 방식으로 **"저장소에서 지속적으로 새 리비전 배포"**
   (Continuously deploy new revisions from a source repository)를
   선택합니다.
4. **설정(Set up with Cloud Build)** 버튼 클릭:
   - 저장소 공급자: **GitHub** 선택.
   - GitHub 계정 인증 창이 뜨면 로그인하고 권한을 승인합니다.
   - 저장소 목록에서 **`jin-1119/plato_mcp`**를 선택합니다.
   - 브랜치: `main` (기본값 그대로 두면 됩니다).
   - 빌드 유형: **Dockerfile**을 선택하고, Dockerfile 위치는 저장소
     루트의 `Dockerfile` (기본값이 이미 그렇게 잡혀있을 것입니다).
   - **저장** 클릭.
5. 서비스 이름: `plato-mcp` 입력.
6. 리전(Region): **`asia-northeast3` (서울)** 선택 (다른 지역이 편하면
   바꿔도 됩니다).
7. **인증(Authentication)** 항목에서 **"인증되지 않은 호출 허용"**
   (Allow unauthenticated invocations)을 선택합니다.
   - 이게 필요한 이유: Smithery의 게이트웨이가 이 주소를 직접 호출해야
     하는데, 여기에 별도의 구글 로그인 인증을 요구하면 Smithery가 접근하지
     못합니다. (PLATO 계정 인증 자체는 이것과 별개로, 매 요청마다
     `pnu_id`/`pnu_password`로 이 서버 스스로가 처리합니다.)
8. **"컨테이너, 볼륨, 네트워킹, 보안"** 부분을 펼치고 **"컨테이너"** 탭 →
   **"변수 및 보안 비밀"** 탭으로 이동 → **"변수 추가"** 클릭:
   - 이름: `MCP_TRANSPORT`
   - 값: `streamable-http`
9. 맨 아래 **만들기(Create)** 버튼 클릭.
10. 몇 분 정도 빌드+배포가 진행됩니다 (진행 상황이 화면에 표시됩니다). 끝나면
    서비스 상세 페이지 맨 위에 **URL** (예:
    `https://plato-mcp-xxxxx-xx.a.run.app`)이 표시됩니다.
    **이 주소를 복사해두세요 — 3단계에서 씁니다.**

**CLI**

저장소 루트(`D:\1.gemini\PLATO_MCP`)에서 실행:

```bash
gcloud run deploy plato-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=streamable-http
```

- GitHub 연결 없이 지금 이 폴더에 있는 코드를 바로 올려서 빌드합니다 (Cloud
  Build를 자동으로 사용). 몇 분 정도 걸리며, 중간에 "이 소스를 업로드할까요?"
  같은 확인 프롬프트가 뜨면 `y`를 입력하세요.
- 끝나면 `Service URL: https://plato-mcp-xxxxx-xx.a.run.app` 같은 줄이
  출력됩니다. **이 주소를 복사해두세요 — 3단계에서 씁니다.**

### 1B-5. 배포가 실제로 됐는지 확인

**GUI (브라우저)**

방금 복사한 주소 뒤에 `/mcp`를 붙여서 새 브라우저 탭에 그대로 입력해보세요
(예: `https://plato-mcp-xxxxx-xx.a.run.app/mcp`). MCP 프로토콜은 원래
`POST` 요청으로만 응답하므로, 이렇게 주소창에 직접 쳐서 들어가면(=GET
요청) **"Method Not Allowed" 같은 에러 화면이 뜨는 게 정상**입니다 — 이건
"서버가 살아있고, 응답은 하는데 이 방식의 요청은 안 받는다"는 뜻이라
오히려 성공 신호입니다. 반대로 페이지가 아예 안 뜨거나 "사이트에 연결할 수
없음" 같은 에러가 나오면 배포에 문제가 있는 것이니 아래 1-6을 확인하세요.

**CLI**

```bash
curl -i https://<복사해둔 주소>/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0.0.1"}}}'
```

에러 없이 JSON 응답(`serverInfo`에 `plato-mcp`가 보이는 응답)이 오면 성공입니다.

### 1B-6. 문제가 있을 때 로그 보기

**GUI**

Cloud Run 서비스 상세 페이지에서 위쪽 탭 중 **"로그(Logs)"**를 클릭하면
최근 요청/에러 로그를 볼 수 있습니다.

**CLI**

```bash
gcloud run services logs read plato-mcp --region asia-northeast3 --limit 20
```

---

## 2단계: 자격증명이 로그에 남는지 확인 (보안 점검)

이 서버는 PLATO 학번/비밀번호를 매 요청의 쿼리 파라미터(`?pnu_id=...&pnu_password=...`)
또는 헤더로 받습니다 (Smithery의 URL 배포 방식이 그렇게 동작하기 때문에 어쩔 수
없습니다 — 자세한 배경은 `docs/smithery_deployment_model.md` 참고). 이 프로젝트
자체 코드(uvicorn)는 이미 쿼리스트링을 로그에 남기지 않도록 고쳐져 있지만
(#63), **호스팅 서비스 자체의 기본 요청 로그**가 쿼리스트링까지 남기는지는
별개로 확인이 필요합니다:

1. 1단계(또는 1B단계)에서 확인차 접속했던 것처럼, `/mcp` 뒤에 아무 쿼리
   파라미터나 붙여서 (예: `?pnu_id=test&pnu_password=test123`) 한 번
   접속해봅니다 — 테스트용 가짜 값이니 안전합니다.
2. 방금 그 요청이 로그에 어떻게 찍혔는지 확인합니다:
   - **Render**: 대시보드 → 해당 서비스 → **"Logs"** 탭.
   - **Cloud Run — GUI**: 서비스 페이지 → **"로그(Logs)"** 탭.
   - **Cloud Run — CLI**: `gcloud run services logs read plato-mcp --region asia-northeast3 --limit 20`
   요청 URL이 로그에 **쿼리 파라미터까지 그대로** 찍혀 있는지 확인하세요.
3. 만약 나중에 실제 `pnu_password`가 포함된 요청의 전체 URL이 이 로그에
   그대로 찍힌다면, 호스팅 서비스의 로그 수준 설정을 낮추거나 별도 이슈로
   추적해야 합니다 — 지금 당장 막을 방법이 마땅치 않다면 최소한 **알고
   있는 상태로 진행**하는 것이 중요합니다.

---

## 3단계: smithery.ai에 등록하기

1. 브라우저로 https://smithery.ai/new 접속 (로그인 필요 — 이미 로그인되어
   있다면 바로 폼이 뜹니다).
2. **Namespace / Server ID** 칸: 본인 계정명(예: `jinyeonggim844`) 뒤에
   서버 이름을 정해서 넣습니다 (예: `plato-mcp`).
3. **MCP Server URL** 칸: 1단계에서 복사해둔 주소(Render라면
   `https://plato-mcp.onrender.com`, Cloud Run이라면
   `https://plato-mcp-xxxxx-xx.a.run.app`) 뒤에 `/mcp`를 붙여서 넣습니다.
   예: `https://plato-mcp.onrender.com/mcp`
4. **Continue** 버튼 클릭.
5. Smithery가 자동으로 서버에 접속해서 어떤 도구(tool)들이 있는지 스캔합니다
   (이 서버는 로그인 없이도 도구 목록 조회는 되므로 자동 스캔이 될 것으로
   예상됩니다). 스캔이 끝나면 14개 도구(`list_courses`, `submit_assignment`
   등)가 리스팅 페이지에 나오는지 확인하세요.
   - **스캔이 실패하면(403 등)**: `docs/build/publish` 문서에 나온
     트러블슈팅을 참고하거나, 이 저장소 이슈([#67](https://github.com/jin-1119/plato_mcp/issues/67))에
     상황을 남겨주세요 — 정적 서버 카드(`/.well-known/mcp/server-card.json`)로
     우회하는 방법을 추가로 검토해야 할 수 있습니다.

---

## 4단계: 실제로 설치해서 확인하기

리스팅 페이지가 뜨면, 개발 환경이 아닌 실제 설치 경로로 최소 도구 1개를 호출해
봅니다 — 예를 들어 Claude.ai에서 이 서버를 커넥터로 추가하고, 실제 PLATO 계정
정보를 입력한 뒤 "내 강좌 목록 보여줘" 같은 요청으로 `list_courses`를 호출해
성공하는지 확인합니다. 여기까지 되면 배포가 완전히 끝난 것입니다.

---

## 막히면

- Render 배포 자체가 안 될 때: 서비스 페이지의 **"Logs"** 탭에서 원인 확인.
- Cloud Run 배포 자체가 안 될 때: 서비스 페이지의 **"로그(Logs)"** 탭에서
  원인 확인 (1B-6 참고).
- Smithery 스캔이 실패할 때: `docs/build/publish` 문서의 "403 Forbidden during
  scan" 항목 참고.
- 그 외 이상하게 막히는 부분은 그대로 캡처해서 이슈 [#67](https://github.com/jin-1119/plato_mcp/issues/67)에
  남겨주시면 다음 단계를 같이 정리하겠습니다.
