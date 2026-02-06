# instech 시나리오 테스트

instech 웹앱의 E2E 시나리오를 Claude Code에서 실행하고, HTML 리포트로 결과를 확인할 수 있는 도구입니다.

**개발자가 아니어도 사용할 수 있습니다.** PM, 디자이너, 백엔드 직군 누구나 Claude Code만 있으면 테스트를 실행할 수 있습니다.

## 설치 (최초 1회)

### 사전 준비

| 필수 항목 | 설치 방법 |
|---|---|
| Claude Code | `npm install -g @anthropic-ai/claude-code` 또는 [공식 문서](https://docs.anthropic.com/en/docs/claude-code) |
| Python 3 | Mac에 기본 설치됨. 없으면 `brew install python3` |

### 원클릭 설치

터미널에 아래 명령어를 붙여넣으면 모든 설정이 자동으로 완료됩니다:

```bash
curl -sL https://hj8902.github.io/instech_scenarios/install.sh | bash
```

이 스크립트가 자동으로 처리하는 것:
- Python3 설치 여부 확인
- Playwright + Chromium 브라우저 설치
- Claude Code 스킬 파일 설치

### 업데이트

시나리오나 스크립트가 업데이트되면 같은 명령어를 다시 실행하면 됩니다:

```bash
curl -sL https://hj8902.github.io/instech_scenarios/install.sh | bash
```

## 사용법

### 1. Claude Code 실행

터미널에서 테스트하려는 프로젝트 디렉토리(또는 아무 디렉토리)에서:

```bash
claude
```

### 2. 스킬 실행

Claude Code 채팅에서 아래 명령어를 입력합니다:

```
/instech-scenario-test
```

### 3. 안내에 따라 선택

Claude가 순서대로 물어봅니다:

1. **테스트 환경 URL** - 개발(`instech.dev.3o3.co.kr`) 또는 스테이징(`instech.stg.3o3.co.kr`)
2. **테스트할 기능** - 예: 보험 나이 계산
3. **테스트 범위** - 전체 시나리오 또는 특정 시나리오
4. **반복 횟수** (특정 시나리오 선택 시) - API 응답 안정성 검증용

### 4. 결과 확인

- 테스트가 끝나면 **HTML 리포트가 브라우저에서 자동으로 열립니다**
- 각 시나리오의 통과/실패 여부, 스크린샷을 확인할 수 있습니다
- Claude Code 채팅에도 텍스트 요약이 표시됩니다

## 첫 실행 시 로그인

최초 실행 또는 세션이 만료되면 로그인이 필요합니다:

1. Claude가 "인증이 필요합니다" 메시지를 표시합니다
2. 브라우저가 자동으로 열립니다
3. **카카오 로그인**을 진행합니다 (2분 이내)
4. 로그인 완료 후 자동으로 테스트가 시작됩니다

로그인 상태는 저장되므로 매번 로그인할 필요 없습니다.

## 시나리오 뷰어

정의된 시나리오 목록을 시각적으로 확인할 수 있습니다:

https://hj8902.github.io/instech_scenarios/

## FAQ

**Q: 테스트가 실패했는데 "전제조건" 안내가 나와요.**
A: 일부 시나리오는 특정 유저 상태(신규/기존)에서만 통과합니다. 결과 리포트에 전제조건이 표시되니 참고해주세요.

**Q: "세션이 만료되었습니다" 메시지가 나와요.**
A: 브라우저가 열리면 카카오 로그인을 다시 진행해주세요.

**Q: 설치 중 에러가 발생했어요.**
A: `python3 --version` 으로 Python3이 설치되어 있는지 확인해주세요. 문제가 계속되면 프론트엔드 팀에 문의해주세요.

**Q: 스킬 업데이트 방법은?**
A: 설치 명령어를 다시 실행하면 최신 버전으로 업데이트됩니다.

---

## 개발자용 정보

### 저장소 구조

```
├── index.html                     # 시나리오 뷰어
├── install.sh                     # 원클릭 설치 스크립트
├── skill/
│   └── SKILL.md                   # Claude Code 스킬 정의
├── scripts/
│   ├── scenario_runner.py         # 시나리오 실행 엔진
│   └── generate_report.py         # HTML 리포트 생성기
└── scenarios/
    ├── index.json                 # 시나리오 목록
    ├── _setup/
    │   └── login.json             # 로그인 (Setup)
    └── age-calculation/
        ├── landing-redirect-to-input.json
        ├── landing-redirect-to-result.json
        ├── input-to-result.json
        ├── invalid-birthdate.json
        ├── terms-masking-new.json
        ├── terms-masking-agreed.json
        └── edit-birthdate.json
```

### 시나리오 JSON 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 시나리오 고유 ID |
| `name` | string | 시나리오 이름 |
| `type` | `"setup"` \| `"test"` | setup은 전제조건, test는 실제 테스트 |
| `requiresAuth` | boolean | 인증 필요 여부 |
| `precondition` | string | 테스트 유효 조건 (선택) |
| `variables` | string[] | 실행 시 입력받는 변수 목록 |
| `defaults` | object | 변수 기본값 |
| `steps[].action` | string | 실행할 액션 |
| `steps[].description` | string | 사람이 읽을 수 있는 설명 |

### 지원 액션

| 액션 | 설명 |
|---|---|
| `navigate` | URL로 이동 |
| `fill` | 입력 필드에 값 입력 |
| `blur` | onBlur validation 트리거 |
| `click` | 요소 클릭 |
| `clear` | 입력 필드 초기화 |
| `waitFor` | 요소가 특정 상태가 될 때까지 대기 |
| `waitForNavigation` | 페이지 이동 대기 |
| `waitForResponse` | API 응답 대기 |
| `waitForTimeout` | 지정 시간 대기 |
| `expect` | 검증 (URL, visible, hidden) |
| `screenshot` | 스크린샷 캡처 |
| `saveState` | 브라우저 인증 상태 저장 |
| `loadState` | 저장된 인증 상태 로드 |
| `handleTermsAgreement` | 약관 동의 처리 |
| `waitForUrl` | 특정 URL 패턴 대기 |

### 변수 치환

`{{변수명}}` 형식으로 사용. 실행 시 사용자 입력값으로 치환됩니다.
- `{{baseUrl}}` - 테스트 대상 서버 URL
