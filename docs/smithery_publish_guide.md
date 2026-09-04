# plato-mcp를 Smithery에 공개 배포하기 — 비전공자용 단계별 가이드

이 문서는 [#67](https://github.com/jin-1119/plato_mcp/issues/67) 작업(Smithery
배포 모델 변경 대응)을 실제로 따라 하기 위한 가이드입니다. 프로그래밍을 잘 몰라도
그대로 따라 할 수 있도록, **터미널에 그대로 붙여넣을 명령어**와 **브라우저에서
클릭할 버튼**을 구분해서 적었습니다.

> 이 가이드에 나오는 화면/문구는 2026-09-04 기준으로 실제 로그인해서 직접 확인한
> 내용입니다. Smithery나 Google Cloud가 UI를 바꾸면 달라질 수 있습니다.

## 전체 그림

```
1) Google Cloud에 이 서버를 올려서 "공개 인터넷 주소"를 하나 만든다
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

---

## 1단계: Google Cloud Run에 배포하기

Google Cloud Run은 "Dockerfile 하나만 있으면 인터넷 주소를 만들어주는" 구글의
서비스입니다. 이 프로젝트는 이미 `Dockerfile`이 준비되어 있어서 **코드를 하나도
고칠 필요 없이** 그대로 올릴 수 있습니다.

### 1-1. (본인이 직접) Google Cloud 계정 및 결제 준비

> ⚠️ **이 부분은 Claude가 대신 할 수 없습니다.** 계정 생성이나 결제 카드 등록은
> 보안상 본인이 직접 해야 하는 영역입니다.

1. https://console.cloud.google.com 접속 후 구글 계정으로 로그인 (이미 되어
   있다면 생략).
2. **결제 계정 확인**: 실제로 확인해보니 기존에 "내 결제 계정"이라는 결제 계정이
   있지만 **닫혀(closed) 있는 상태**입니다. https://console.cloud.google.com/billing
   에서:
   - 기존 결제 계정을 다시 열 수 있는지 확인해보고, 안 되면
   - **"결제 계정 만들기"**로 새 결제 계정을 하나 만들고 카드를 등록하세요.
   - 개인 저빈도 사용 기준으로는 Cloud Run 무료 한도(월 200만 요청) 안에서
     충분히 돌아가므로 **실제로 청구될 가능성은 거의 없습니다.** 다만 카드
     등록 자체는 필수입니다 (구글의 정책).

### 1-2. GCP 프로젝트 준비 (결정 필요)

Cloud Run 서비스는 "프로젝트"라는 폴더 같은 단위 안에 들어갑니다. 실제로 확인해
보니 현재 계정에는 이미 5개 프로젝트(`armygo`, `TOEFL`, `TOEFL-words-bot`,
`TOEFL reading`, `predictive-dragon-h6shk`)가 있고, **무료 계정의 "새 프로젝트
생성 한도"를 이미 다 써서 새 프로젝트를 만들 수 없는 상태**였습니다. 아래 둘 중
하나를 선택하세요:

**옵션 A — 기존 프로젝트 재사용 (더 간단함)**

지금 안 쓰는 프로젝트 하나를 그대로 씁니다. 터미널에서:

```bash
gcloud config set project <프로젝트ID>
# 예: gcloud config set project predictive-dragon-h6shk
```

**옵션 B — 안 쓰는 프로젝트를 지우고 새로 만들기**

1. https://console.cloud.google.com/cloud-resource-manager 에서 안 쓰는
   프로젝트를 선택 → **삭제**. (⚠️ 그 프로젝트 안의 다른 데이터가 있다면 같이
   지워지니 먼저 확인하세요.)
2. 삭제 후 터미널에서:
   ```bash
   gcloud projects create plato-mcp --name="plato-mcp"
   gcloud config set project plato-mcp
   ```

어느 쪽이든, 선택한 프로젝트에 **1-1에서 만든 결제 계정을 연결**해야 합니다:

```bash
gcloud billing accounts list
# 위에서 나온 ACCOUNT_ID를 아래에 넣기
gcloud billing projects link <프로젝트ID> --billing-account=<ACCOUNT_ID>
```

### 1-3. 필요한 구글 API 켜기

터미널에서 (프로젝트 폴더, 즉 `D:\1.gemini\PLATO_MCP`에서 실행):

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

### 1-4. 실제로 배포하기

같은 터미널에서, 저장소 루트(`D:\1.gemini\PLATO_MCP`)에서:

```bash
gcloud run deploy plato-mcp \
  --source . \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=streamable-http
```

- `--region asia-northeast3`는 서울 리전입니다. 다른 지역이 편하면 바꿔도
  됩니다.
- `--allow-unauthenticated`가 필요한 이유: Smithery의 게이트웨이가 이 주소를
  직접 호출해야 하는데, 여기에 별도의 구글 로그인 인증을 요구하면 Smithery가
  접근하지 못합니다. (PLATO 계정 인증 자체는 이것과 별개로, 매 요청마다
  `pnu_id`/`pnu_password`로 이 서버 스스로가 처리합니다.)
- 몇 분 정도 걸리며, 끝나면 `Service URL: https://plato-mcp-xxxxx-xx.a.run.app`
  같은 줄이 출력됩니다. **이 주소를 복사해두세요 — 3단계에서 씁니다.**

### 1-5. 배포가 실제로 됐는지 확인

```bash
curl -i https://<복사해둔 주소>/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0.0.1"}}}'
```

에러 없이 JSON 응답(`serverInfo`에 `plato-mcp`가 보이는 응답)이 오면 성공입니다.
`Connection refused`나 5xx 에러가 나오면 `gcloud run services logs read
plato-mcp --region asia-northeast3`로 로그를 확인하세요.

---

## 2단계: 자격증명이 로그에 남는지 확인 (보안 점검)

이 서버는 PLATO 학번/비밀번호를 매 요청의 쿼리 파라미터(`?pnu_id=...&pnu_password=...`)
또는 헤더로 받습니다 (Smithery의 URL 배포 방식이 그렇게 동작하기 때문에 어쩔 수
없습니다 — 자세한 배경은 `docs/smithery_deployment_model.md` 참고). 이 프로젝트
자체 코드(uvicorn)는 이미 쿼리스트링을 로그에 남기지 않도록 고쳐져 있지만
(#63), **Cloud Run 자체의 기본 요청 로그**가 쿼리스트링까지 남기는지는 별개로
확인이 필요합니다:

```bash
gcloud run services logs read plato-mcp --region asia-northeast3 --limit 20
```

배포 직후 위 1-5의 curl 테스트를 한 번 실행한 다음 로그를 보면 됩니다 (테스트
호출에는 실제 비밀번호가 없으니 안전합니다). 만약 나중에 실제 `pnu_password`가
포함된 요청의 전체 URL이 이 로그에 그대로 찍힌다면, Cloud Run의 요청 로그
수준을 낮추거나(Cloud Logging 설정) 별도 이슈로 추적해야 합니다 — 지금 당장
막을 방법이 마땅치 않다면 최소한 **알고 있는 상태로 진행**하는 것이 중요합니다.

---

## 3단계: smithery.ai에 등록하기

1. 브라우저로 https://smithery.ai/new 접속 (로그인 필요 — 이미 로그인되어
   있다면 바로 폼이 뜹니다).
2. **Namespace / Server ID** 칸: 본인 계정명(예: `jinyeonggim844`) 뒤에
   서버 이름을 정해서 넣습니다 (예: `plato-mcp`).
3. **MCP Server URL** 칸: 1단계에서 복사해둔 Cloud Run 주소 뒤에 `/mcp`를
   붙여서 넣습니다. 예: `https://plato-mcp-xxxxx-xx.a.run.app/mcp`
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

- Cloud Run 배포 자체가 안 될 때: `gcloud run services logs read plato-mcp
  --region asia-northeast3`로 원인 확인.
- Smithery 스캔이 실패할 때: `docs/build/publish` 문서의 "403 Forbidden during
  scan" 항목 참고.
- 그 외 이상하게 막히는 부분은 그대로 캡처해서 이슈 [#67](https://github.com/jin-1119/plato_mcp/issues/67)에
  남겨주시면 다음 단계를 같이 정리하겠습니다.
