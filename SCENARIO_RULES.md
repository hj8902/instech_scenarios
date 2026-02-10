# 시나리오 작성 규칙

## 시나리오 타입

| type | 설명 | 뷰어 배지 |
|------|------|-----------|
| `setup` | 로그인 등 사전설정 시나리오 | 사전설정 |
| `test` | 동작 검증 시나리오 (happy-path, edge-case) | (없음) |
| `state-setup` | 특정 상태를 만들기 위한 시나리오 (예: 원하는 GA 배정) | 상태설정 |

## 시나리오 분류

### Happy Path
- 시작부터 **완료 화면까지 도달**하는 전체 플로우
- 유저가 정상적으로 모든 단계를 거치는 경우를 테스트
- 예: 주제 선택 → 상담 방식 선택 → 정보 확인 → 상담 신청 완료

### Edge Case
- 플로우의 **특정 지점에서 특정 동작**을 검증하는 시나리오
- 완료까지 가는 게 목적이 아니라, 특정 조건에서 UI가 올바르게 반응하는지 확인
- 유형:
  - **유효성 검증**: 잘못된 입력 → 에러 메시지 표시
  - **버튼 상태**: 조건 미충족 → disabled
  - **가드/리다이렉트**: 잘못된 접근 → 이전 페이지로 복귀
  - **특수 UI 동작**: 특정 조건에서만 발생하는 UI 변화

### Edge Case가 아닌 것
- **제공된 UI를 사용한 정상 동작**은 엣지 케이스가 아니다
  - 예: 바텀시트의 X 버튼으로 닫기 → 다시 시도 (정상 플로우)
  - 예: "정보 수정" 버튼 클릭 → user-edit 이동 (정상 플로우)
- 이런 동작은 happy-path 시나리오에서 자연스럽게 커버된다

## 네비게이션 규칙

### 순차적 플로우 필수
- **중간 페이지에 URL로 직접 접근하지 않는다**
- 각 페이지에는 route guard가 있어서, store에 필요한 데이터(topics, userInfo, type)가 없으면 `history.back()`으로 튕겨남
- 반드시 실제 유저 플로우를 따라 순차적으로 접근한다

```
❌ navigate → /counsel/schedule
❌ navigate → /counsel/user-edit/InPerson

✅ topics → types → schedule → user-edit (순차적 접근)
```

### history.back() 테스트 시
- 직접 URL 접근으로 `history.back()`을 테스트하려면, **이전 페이지를 먼저 방문**하여 히스토리를 생성해야 한다
- 히스토리가 없으면 `about:blank`으로 이동함

```
✅ navigate → /counsel/topics → navigate → /counsel/user-edit/invalid → history.back() → topics
```

## BE 의존성 규칙

### BE 응답 상태에 의존하는 시나리오를 만들지 않는다
- BE 응답에 따라 성공/실패가 갈리는 시나리오는 happy-path와 상호 배타적이 됨
- 한쪽이 성공하면 다른 쪽이 반드시 실패하는 구조는 테스트로서 가치가 없다
- 예시:
  - ❌ GA 이용불가 시 알림 표시 (GA 가용하면 실패)
  - ❌ API 실패 시 스낵바 표시 (API 성공하면 실패)

### 시간대 의존성 주의
- 전화/카카오톡 상담은 평일 10~17시만 이용 가능
- 시간대에 따라 실패할 수 있는 시나리오는 이를 명시한다

## 상담 플로우별 접근 패턴

### InPerson (만나서 상담)

#### gender-o (성별 있음)
```
topics → types → 다음 → [GA check] → ConfirmBottomSheet → 확인했어요 → schedule → ...
                                                          → 정보 수정 → user-edit → ...
```

#### gender-x (성별 없음)
```
topics → types → 다음 → [GA check] → schedule (직접 진입) → user-edit → ...
```
- ConfirmBottomSheet를 거치지 않으므로 GA 가용성 이슈에 덜 민감
- user-edit 테스트 시 권장하는 플로우

### Phone / Chat (전화 / 카카오톡)

#### gender-o (성별 있음)
```
topics → types → 다음 → [GA check] → ConfirmBottomSheet → 확인했어요 → [terms] → complete
                                                          → 정보 수정 → user-edit → ...
```

#### gender-x (성별 없음)
```
topics → types → 다음 → [GA check] → user-edit (직접 진입) → ...
```

### 지역 선택 (InPerson 전용)
- **항상 서울특별시 강남구를 기본 지역으로 사용한다** — GA 이용불가 확률이 가장 낮아 안정적
- 다른 지역을 테스트하는 특수 케이스(예: 세종특별자치시 시/군/구 생략)만 예외

## 시나리오 JSON 작성 규칙

### 변수 (variables)
- 시나리오에서 사용하는 모든 `{{변수}}`를 `variables` 배열에 선언
- 하드코딩하지 않는 값만 변수로 추출 (baseUrl, userId 등)
- 사용하지 않는 변수는 선언하지 않는다

### precondition
- 시나리오가 유효하려면 충족해야 하는 전제조건을 명시
- 예: "유저 프로필에 성별 정보가 없는 상태", "상담 약관에 동의하지 않은 상태"

### userData 주입
- `fetchAndInjectUserInfo`의 `userData`에 명시적으로 유저 데이터를 지정
- gender-x 테스트: `"gender": ""`
- gender-o 테스트: `"gender": "{{userGender}}"`

### 대기 시간 (waitForTimeout)
- 네비게이션 전환: 1000ms
- API 응답 대기: 2000~3000ms
- UI 애니메이션: 500ms
- 불필요한 대기를 넣지 않는다 — `waitForNavigation`으로 충분한 경우 timeout 불필요

### blur 필수
- `fill()` 후 validation을 트리거하려면 반드시 `blur()` 호출
- Playwright의 `fill()`은 blur 이벤트를 발생시키지 않음

## 전처리 액션

### cancelExistingCounsel
- **용도**: 상담 완료까지 진행하는 시나리오에서, 기존 상담 신청이 남아있으면 충돌하므로 사전에 취소
- **동작**: `/car-insurance/history` 페이지에서 "상담 취소하기" 버튼 → 모달 "상담 취소" 버튼으로 모든 기존 상담 취소
- **필수 속성**: `baseUrl` — 테스트 환경 URL
- **적용 대상**: 상담 신청 완료까지 진행하는 모든 해피패스/상태설정 시나리오
- **배치 위치**: `loadState` 바로 다음

```json
{
  "action": "cancelExistingCounsel",
  "baseUrl": "{{baseUrl}}",
  "description": "기존 상담 신청이 있으면 취소"
}
```

### retryUntilGa
- **용도**: 원하는 GA(보험대리점)가 배정될 때까지 반복 시도
- **동작**: "다음" 버튼 클릭 → `/available-ga` API 응답 확인 → 불일치 시 뒤로가기 → 재시도 (최대 N회)
- **필수 속성**: `targetGaCompanyId` — 원하는 GA ID (6=한화, 7=링크투테크놀로지스)
- **선택 속성**: `maxRetries` (기본 20), `clickSelector` (기본 `button:has-text('다음')`)
- **주의**: `targetGaCompanyId`는 변수 치환 후 문자열이 되므로 러너에서 int 변환 처리

```json
{
  "action": "retryUntilGa",
  "targetGaCompanyId": "{{targetGaCompanyId}}",
  "clickSelector": "button:has-text('다음')",
  "maxRetries": 20,
  "description": "원하는 GA가 배정될 때까지 '다음' 버튼 반복 클릭"
}
```
