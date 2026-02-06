# instech_scenarios

instech 웹앱 시나리오 테스트 정의 파일 저장소입니다.

## 구조

```
scenarios/
├── index.json                          # 시나리오 목록
├── _setup/
│   └── login.json                      # 로그인 (Setup)
└── age-calculation/
    ├── landing-redirect.json           # Landing 리다이렉트 확인
    ├── input-to-result.json            # 생년월일 입력 → 결과
    └── edit-birthdate.json             # 생년월일 수정
```

## GitHub Pages URL

배포 후 시나리오 접근:
```
https://hj8902.github.io/instech_scenarios/index.json
```

## 시나리오 JSON 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | string | 시나리오 고유 ID |
| `name` | string | 시나리오 이름 |
| `type` | `"setup"` \| `"test"` | setup은 전제조건, test는 실제 테스트 |
| `requiresAuth` | boolean | 인증 필요 여부 |
| `variables` | string[] | 실행 시 입력받는 변수 목록 |
| `defaults` | object | 변수 기본값 |
| `steps[].action` | string | 실행할 액션 |
| `steps[].description` | string | 사람이 읽을 수 있는 설명 |

### 지원 액션

| 액션 | 설명 |
|---|---|
| `navigate` | URL로 이동 |
| `fill` | 입력 필드에 값 입력 |
| `click` | 요소 클릭 |
| `clear` | 입력 필드 초기화 |
| `waitFor` | 요소가 특정 상태가 될 때까지 대기 |
| `waitForNavigation` | 페이지 이동 대기 |
| `waitForResponse` | API 응답 대기 |
| `expect` | 검증 (URL, visible, hidden 등) |
| `screenshot` | 스크린샷 캡처 |
| `saveState` | 브라우저 인증 상태 저장 |
| `loadState` | 저장된 인증 상태 로드 |
| `handleTermsAgreement` | 약관 동의 처리 |

### 변수 치환

`{{변수명}}` 형식으로 사용. 실행 시 사용자 입력값으로 치환됩니다.
- `{{baseUrl}}` - 테스트 대상 서버 URL
- `{{testEmail}}` - 테스트 계정 이메일
- `{{testPassword}}` - 테스트 계정 비밀번호
