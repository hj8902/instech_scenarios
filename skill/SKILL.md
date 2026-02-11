---
name: instech-scenario-test
description: instech 웹앱 시나리오 테스트 실행 도구. 원격 서버(개발/스테이징)에 대해 사전 정의된 E2E 시나리오를 Playwright로 실행하고 결과를 스크린샷과 함께 보고한다. 레포 접근 없이 Claude Code만으로 PM, 디자이너, 백엔드 직군이 사용할 수 있다. /instech-scenario-test 또는 시나리오 테스트 요청 시 트리거.
---

# instech 시나리오 테스트

원격 서버에 대해 E2E 시나리오를 실행하고 결과를 보고하는 스킬.

## 실행 흐름

### Step 1. 시나리오 목록 가져오기

WebFetch로 시나리오 목록을 가져온다:

```
URL: https://hj8902.github.io/instech_scenarios/scenarios/index.json
```

시나리오를 폴더(기능) 단위로 그룹핑한다:
- `path`의 첫 번째 세그먼트가 기능 폴더 (예: `age-calculation/`, `feature-b/`)
- `type: "setup"`은 사전설정, `type: "state-setup"`은 상태설정으로 별도 분류

### Step 2. 사용자 입력 수집

AskUserQuestion으로 아래 정보를 **순서대로** 수집한다:

#### 2-1. 테스트 URL + 로그인 옵션

**하나의 AskUserQuestion에 2개 질문**으로 수집한다 (환경과 로그인은 별도 질문):

**질문 1 — 테스트 환경** (header: "환경"):
- 개발: `https://instech.dev.3o3.co.kr`
- 스테이징: `https://instech.stg.3o3.co.kr`
- 기타 (직접 입력): 피쳐 브랜치 환경 등 (예: `https://feature-abc.dev.3o3.co.kr`)

**질문 2 — 로그인 옵션** (header: "로그인"):
- 기존 로그인 유지 (Recommended): 저장된 인증 상태가 있으면 그대로 사용
- 새로 로그인: 기존 인증 상태를 삭제하고 headed 브라우저로 재로그인 진행

새로 로그인 선택 시: 해당 환경의 인증 상태 파일을 삭제한 뒤, headed 모드로 로그인 절차 진행

#### 2-2. 기능 선택
- Step 1에서 그룹핑한 기능 목록을 선택지로 제공
- 예: "보험 나이 계산" (age-calculation)

#### 2-2a. counsel 기능 전용 추가 입력

counsel(보험 상담) 기능 선택 시, 아래 정보를 **추가로** 수집한다:

##### 유저 정보 (필수)

테스트 시작 전에 로그인한 유저의 정보를 입력받는다. gender-o 시나리오(유저 정보 있음)에서 store에 주입하는 데 사용된다.

- 수집 방법: **"/me API 응답을 붙여넣어 주세요"** 형태로 요청
- 유저가 브라우저 개발자 도구에서 복사한 /me 응답을 그대로 붙여넣으면 됨
- 어떤 형식이든 (JSON, devtools 복사, key:value 등) 아래 필드를 파싱하여 추출:

| /me 응답 필드 | 러너 변수명 | 매핑 |
|---|---|---|
| `userId` | `userId` | 그대로 |
| `name` | `userName` | 그대로 |
| `phone` | `userPhone` | 그대로 |
| `fullBirth` | `userBirthDate` | 그대로 (YYYYMMDD) |
| `genderCode` | `userGender` | 그대로 (옵셔널 — 빈 문자열이면 gender-x 시나리오용) |

- 파싱한 값을 `--var userId=xxx --var userName=xxx ...` 형식으로 러너에 전달

##### 진입 유형 선택

| 선택지 | EntryType 값 |
|---|---|
| 보험나이 | `INSURANCE_AGE` |
| 건강나이 (낮음) | `HEALTH_AGE_LOW` |
| 건강나이 (동일) | `HEALTH_AGE_SAME` |
| 건강나이 (높음) | `HEALTH_AGE_HIGH` |
| 또래보험료 (낮음) | `PEER_PREMIUM_LOW` |
| 또래보험료 (동일) | `PEER_PREMIUM_SAME` |
| 또래보험료 (높음) | `PEER_PREMIUM_HIGH` |
| 보험 없음 | `NO_INSURANCE` |
| 기타 (Recommended) | `OTHER` |

- 기본값: `OTHER` (기타)
- `DRIVER_INSURANCE`, `CAR_INSURANCE`는 보험 상담에서 사용하지 않으므로 **제외**
- 선택된 값을 `--var entryType=<값>` 형식으로 러너에 전달

```bash
# counsel 테스트 실행 예시 (유저 정보 + entry type 지정)
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> counsel/ \
  --var entryType=OTHER \
  --var userId=12345 --var userName=홍길동 \
  --var userPhone=01012345678 --var userBirthDate=19900101 \
  --var userGender=1
```

#### 2-3. 테스트 범위 선택 (라벨 기반 필터링)

index.json의 각 시나리오에 `labels` 배열이 있다. 사용자의 선택에 따라 `--label` 옵션으로 필터링한다.

**라벨 체계:**

| 분류 | 라벨 | 적용 범위 |
|---|---|---|
| 테스트 유형 | `happy-path`, `edge-case` | 모든 기능 |
| 상담 방식 | `phone`, `kakao`, `inperson` | counsel 전용 |
| 유저 상태 | `gender-o`, `gender-x` | counsel 전용 |
| 약관 상태 | `terms-new`, `terms-agreed` | counsel 전용 |

**선택지 구성:**
- **해피패스 전체**: `--label happy-path` — 해당 기능의 모든 해피패스 시나리오 실행
- **엣지케이스 전체**: `--label edge-case` — 해당 기능의 모든 엣지케이스 시나리오 실행
- **특정 시나리오 선택**: 해당 기능의 시나리오 목록에서 개별 선택 → `single` 모드로 실행

**"전체 시나리오" 옵션은 제공하지 않는다.** 해피패스와 엣지케이스는 반드시 분리하여 실행한다.
**러너가 이를 강제한다** — `--label`으로 필터링된 시나리오에 `happy-path`와 `edge-case`가 동시에 포함되면 실행을 거부하고 에러를 출력한다.

**상태설정(`state-setup`) 시나리오는 해피패스/엣지케이스 일괄 실행에 포함되지 않는다.**
상태설정은 반드시 "특정 시나리오 선택"으로 개별 실행한다.

counsel 기능에서 해피패스/엣지케이스 선택 후 **추가 필터**를 물을 수 있다:
- 상담 방식: 대면(`--label inperson`), 전화(`--label phone`), 카카오톡(`--label kakao`)
- 복수 라벨 지정 시 AND 조건 (예: `--label happy-path --label phone` → 해피패스 중 전화 상담만)

### Step 3. 시나리오 실행 + HTML 리포트 생성

**범용 시나리오 러너(`scenario_runner.py`)와 리포트 생성기(`generate_report.py`)를 사용한다.** 시나리오 JSON을 GitHub Pages에서 가져와 모든 step을 자동으로 Playwright 코드로 변환/실행하고, 결과를 HTML 리포트로 생성한다.

#### 러너 위치 및 사용법

**중요: 스크립트 경로는 반드시 `~/.claude/skills/instech-scenario-test/scripts/`이다. `/scripts` 하위 디렉토리를 빠뜨리지 말 것.**

```bash
SCRIPTS=~/.claude/skills/instech-scenario-test/scripts  # 반드시 /scripts 포함!

# 전체 시나리오: 기능 폴더 내 시나리오 일괄 실행
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> <feature_folder>

# 단일 시나리오: 특정 시나리오 1개 실행
python3 $SCRIPTS/generate_report.py single <base_url> <auth_state_path> <scenario_path> [--var key=value]

# 라벨 필터링: --label 간 AND, 쉼표(,)로 OR
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> counsel/ --label happy-path
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> counsel/ --label happy-path --label inperson,phone  # 해피패스 AND (대면 OR 전화)

# 변수 오버라이드: --var key=value (여러 개 가능, all/single 모두 지원)
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> counsel/ --var entryType=OTHER
python3 $SCRIPTS/generate_report.py single <base_url> <auth_state_path> counsel/state-setup-assign-target-ga.json --var targetGaCompanyId=7

# → /tmp/instech_test_report.html 생성
# → open /tmp/instech_test_report.html 로 브라우저에서 열기
```

**`single` 모드는 특정 시나리오를 개별 실행할 때 사용한다.** `all` 모드의 라벨 필터로 1개만 남는 경우에도 사용할 수 있지만, 시나리오 path를 직접 지정하는 것이 더 명확하다. 특히 `state-setup` 시나리오처럼 커스텀 변수가 필요한 경우에 유용하다.

스크립트가 없으면 사용자에게 설치 안내:
```
설치가 필요합니다. 터미널에서 아래 명령어를 실행해주세요:
curl -sL https://hj8902.github.io/instech_scenarios/install.sh | bash
```

#### 실행 절차

1. `generate_report.py`를 실행 — 내부에서 테스트 실행 + HTML 리포트 생성을 한번에 처리
2. `open /tmp/instech_test_report.html`로 브라우저에서 리포트를 자동으로 열어줌
3. 콘솔에도 텍스트 요약을 출력하여 채팅에서도 결과 확인 가능

**모든 테스트는 반드시 HTML 리포트까지 생성하고 브라우저로 열어준다.**

#### 인증 상태 파일

환경별 인증 상태 파일:
- 개발: `/tmp/instech_auth_state.json`
- 스테이징: `/tmp/instech_auth_state_stg.json`
- 기타 (release, feature 등): `/tmp/instech_auth_state_<환경명>.json` (예: `/tmp/instech_auth_state_release.json`)

인증 상태 파일이 없거나 만료(세션 만료로 `/web-login` 리다이렉트)된 경우:
1. 사용자에게 "인증이 필요합니다. 로그인 브라우저를 엽니다." 안내
2. headed 모드로 브라우저를 열어 수동 로그인 진행 (카카오 OAuth — 자동화 불가)
3. 인증 상태 저장 후 headless 모드로 시나리오 실행

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/web-login")
    page.wait_for_url(
        lambda url: base_url in url and "/web-login" not in url,
        timeout=120000
    )
    context.storage_state(path=auth_state_path)
    context.close()
    browser.close()
```

#### 세션 만료 처리

시나리오 실행 중 `/web-login`으로 리다이렉트가 감지되면:
1. 사용자에게 "세션이 만료되었습니다. 재로그인이 필요합니다." 안내
2. headed 모드로 브라우저를 다시 열어 수동 로그인 진행
3. 인증 상태 재저장 후 시나리오 이어서 실행

#### 상태 전제조건 (precondition)

시나리오에 `precondition` 필드가 있는 경우, 해당 상태에서만 테스트가 유효하다:
- **신규 유저** 시나리오: 생년월일 미입력 / 약관 미동의 상태에서만 실행 가능
- **기존 유저** 시나리오: 생년월일 입력 완료 / 약관 동의 완료 상태에서만 실행 가능

전체 시나리오 실행 시, 현재 유저 상태와 맞지 않는 시나리오는 실패할 수 있다. 결과 보고 시 이를 명시한다.

#### 액션별 Playwright 매핑

| JSON 액션 | Playwright 코드 |
|---|---|
| `navigate` | `page.goto(url)` |
| `fill` | `page.fill(selector, value)` |
| `blur` | `page.locator(selector).blur()` — onBlur validation 트리거 |
| `click` | `page.click(selector)` |
| `clear` | `page.fill(selector, "")` |
| `waitFor` | `page.wait_for_selector(selector, state=state)` |
| `waitForNavigation` | `page.wait_for_load_state("networkidle")` |
| `waitForResponse` | `page.expect_response(url_pattern)` |
| `waitForTimeout` | `page.wait_for_timeout(timeout)` |
| `expect (url)` | `assert value in page.url` |
| `expect (visible)` | `page.wait_for_selector(selector, state="visible")` |
| `expect (hidden)` | 해당 셀렉터가 보이지 않는지 확인 |
| `expect (disabled)` | 셀렉터가 disabled 상태인지 확인 |
| `expect (enabled)` | 셀렉터가 enabled 상태인지 확인 |
| `screenshot` | `page.screenshot(path=path, full_page=True)` |
| `saveState` | `context.storage_state(path=path)` |
| `loadState` | `browser.new_context(storage_state=path)` |
| `launchBrowser` | `p.chromium.launch(headless=headless)` |
| `manualAction` | 사용자에게 안내 메시지 출력 후 다음 액션의 대기 조건 충족까지 대기 |
| `waitForUrl` | `page.wait_for_url(pattern, timeout=timeout)` |
| `handleTermsAgreement` | 약관 체크박스 탐색 후 클릭, 없으면 skip. `"required": true` 시 바텀시트 미노출이면 FAIL |
| `injectStoreData` | `window.__${store}_STORE__?.setState(data)` — 비프로덕션 빌드에서 Zustand store에 데이터 주입 |
| `fetchAndInjectUserInfo` | 시나리오 JSON의 `userData` 필드(사용자 입력값)를 Zustand store에 주입. API 호출 없음 |
| `setSessionStorage` | `sessionStorage.setItem(key, value)` |
| `cancelExistingCounsel` | 히스토리 페이지에서 기존 상담 전부 취소. 상담 완료 시나리오의 전처리 |
| `retryUntilGa` | `clickSelector` 클릭 → `page.route()`로 `/available-ga` 응답 인터셉트 → GA 일치 시 `route.fulfill()` (통과), 불일치 시 `route.abort()` (요청 중단, 페이지 유지) → 재시도 (최대 N회) |

### Step 4. 결과 보고

`generate_report.py` 실행 후 반드시 다음 두 가지를 수행한다:

1. **HTML 리포트를 브라우저로 열기**: `open /tmp/instech_test_report.html`
2. **채팅에 텍스트 요약 출력**: 마크다운 테이블로 결과 요약

전제조건 불일치로 인한 실패는 별도 안내한다.

## 시나리오 JSON 가져오기

개별 시나리오 JSON은 index.json의 `path` 필드를 사용하여 가져온다:

```
https://hj8902.github.io/instech_scenarios/scenarios/{path}
```

예: `https://hj8902.github.io/instech_scenarios/scenarios/age-calculation/input-to-result.json`

## 변수 치환

시나리오 JSON의 `{{변수명}}` 패턴을 사용자 입력값으로 치환한다:

- `{{baseUrl}}` → Step 2-1에서 입력한 테스트 URL
- `{{entryType}}` → Step 2-2a에서 선택한 진입 유형 (counsel 전용)
- `{{userId}}`, `{{userName}}`, `{{userPhone}}`, `{{userBirthDate}}`, `{{userGender}}` → Step 2-2a에서 입력한 유저 정보 (counsel 전용)
- 기타 변수 → `defaults` 값 사용 또는 사용자에게 확인

## 주의사항

- **HTTPS 자동 변환**: `run_all()`과 `single` 모드 모두 `http://` URL을 `https://`로 자동 변환한다. 사용자가 HTTP를 입력해도 안전하게 동작한다.
- **해피패스/엣지케이스 분리 실행 (필수)**: 러너(`scenario_runner.py`)가 강제한다. 한 번의 실행에서 `happy-path`와 `edge-case` 라벨이 동시에 매칭되면 에러로 중단된다. 반드시 `--label happy-path` 또는 `--label edge-case` 중 하나를 명시해야 한다. 특정 기능 라벨(예: `--label over51`)만 지정하면 양쪽 모두 매칭되어 실행이 거부된다.
- 스크린샷 경로: `/tmp/scenario_{시나리오id}_{step번호}.png`
- Playwright는 로그인 시 `headless=False`, 시나리오 실행 시 `headless=True`
- `networkidle` 대기를 충분히 활용하여 동적 렌더링 완료 후 액션 수행
- 셀렉터를 찾지 못하면 DOM을 탐색(reconnaissance)하여 대체 셀렉터를 시도
- 약관 동의(handleTermsAgreement)는 아래 패턴을 따른다:
  1. `[role='dialog'][aria-modal='true']`로 바텀시트 감지
  2. 체크박스 클릭 시 `force=True` 필수 (Emotion CSS-in-JS의 span이 이벤트를 가로챔)
  3. 동의 버튼은 dialog 내 마지막 button: `dialog.locator("button").last`
  4. 바텀시트가 없으면 skip (이미 동의된 상태)
- InputField validation은 `onBlur` 이후에만 에러를 표시한다 (`isTouched && !!error`):
  - `fill()` 후 반드시 `blur()`를 호출해야 validation이 트리거된다
  - Playwright의 `fill()`은 blur 이벤트를 발생시키지 않음

## 시나리오 뷰어

비개발 직군이 시나리오 목록을 시각적으로 확인할 수 있는 뷰어:

```
https://hj8902.github.io/instech_scenarios/
```
