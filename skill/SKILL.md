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
- `type: "setup"`은 사전설정으로 별도 분류

### Step 2. 사용자 입력 수집

AskUserQuestion으로 아래 정보를 **순서대로** 수집한다:

#### 2-1. 테스트 URL + 로그인 옵션
- 환경 선택지:
  - 개발: `https://instech.dev.3o3.co.kr`
  - 스테이징: `https://instech.stg.3o3.co.kr`
  - 기타 (직접 입력): 피쳐 브랜치 환경 등 (예: `https://feature-abc.dev.3o3.co.kr`)
- **새로 로그인** 옵션: 인증 상태 파일이 존재하더라도 강제로 재로그인할지 선택
  - "기존 로그인 유지" (기본값) — 저장된 인증 상태가 있으면 그대로 사용
  - "새로 로그인" — 기존 인증 상태를 삭제하고 headed 브라우저로 재로그인 진행
- 새로 로그인 선택 시: 해당 환경의 인증 상태 파일을 삭제한 뒤, headed 모드로 로그인 절차 진행

#### 2-2. 기능 선택
- Step 1에서 그룹핑한 기능 목록을 선택지로 제공
- 예: "보험 나이 계산" (age-calculation)

#### 2-3. 테스트 범위 선택
- **전체 시나리오**: 선택한 기능의 모든 시나리오를 1회 실행
- **특정 시나리오**: 해당 기능의 시나리오 목록에서 개별 선택

#### 2-4. 반복 횟수 (특정 시나리오 선택 시에만)
- 기본값: 1회
- API 응답이 랜덤하게 달라지는 경우를 위한 반복 테스트 지원

### Step 3. 시나리오 실행 + HTML 리포트 생성

**범용 시나리오 러너(`scenario_runner.py`)와 리포트 생성기(`generate_report.py`)를 사용한다.** 시나리오 JSON을 GitHub Pages에서 가져와 모든 step을 자동으로 Playwright 코드로 변환/실행하고, 결과를 HTML 리포트로 생성한다.

#### 러너 위치 및 사용법

**중요: 스크립트 경로는 반드시 `~/.claude/skills/instech-scenario-test/scripts/`이다. `/scripts` 하위 디렉토리를 빠뜨리지 말 것.**

```bash
SCRIPTS=~/.claude/skills/instech-scenario-test/scripts  # 반드시 /scripts 포함!

# 전체 시나리오: 실행 + HTML 리포트 생성
python3 $SCRIPTS/generate_report.py all <base_url> <auth_state_path> <feature_folder>

# 특정 시나리오 반복: 실행 + HTML 리포트 생성
python3 $SCRIPTS/generate_report.py repeat <base_url> <auth_state_path> <scenario_path> <repeat_count>

# 두 경우 모두 → /tmp/instech_test_report.html 생성
# 두 경우 모두 → open /tmp/instech_test_report.html 로 브라우저에서 열기
```

스크립트가 없으면 사용자에게 설치 안내:
```
설치가 필요합니다. 터미널에서 아래 명령어를 실행해주세요:
curl -sL https://hj8902.github.io/instech_scenarios/install.sh | bash
```

#### 실행 절차 (전체/반복 공통)

1. `generate_report.py`를 실행 — 내부에서 테스트 실행 + HTML 리포트 생성을 한번에 처리
2. `open /tmp/instech_test_report.html`로 브라우저에서 리포트를 자동으로 열어줌
3. 콘솔에도 텍스트 요약을 출력하여 채팅에서도 결과 확인 가능

**모든 테스트는 반드시 HTML 리포트까지 생성하고 브라우저로 열어준다.**

#### 인증 상태 파일

환경별 인증 상태 파일:
- 개발: `/tmp/instech_auth_state.json`
- 스테이징: `/tmp/instech_auth_state_stg.json`

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
| `screenshot` | `page.screenshot(path=path, full_page=True)` |
| `saveState` | `context.storage_state(path=path)` |
| `loadState` | `browser.new_context(storage_state=path)` |
| `launchBrowser` | `p.chromium.launch(headless=headless)` |
| `manualAction` | 사용자에게 안내 메시지 출력 후 다음 액션의 대기 조건 충족까지 대기 |
| `waitForUrl` | `page.wait_for_url(pattern, timeout=timeout)` |
| `handleTermsAgreement` | 약관 체크박스 탐색 후 클릭, 없으면 skip |

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
- 기타 변수 → `defaults` 값 사용 또는 사용자에게 확인

## 주의사항

- 스크린샷 경로:
  - 전체: `/tmp/scenario_{시나리오id}_{step번호}.png`
  - 반복: `/tmp/scenario_{시나리오id}_r{라운드}_{step번호}.png`
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
