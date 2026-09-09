# CS 인수인계 → 텔레그램 알림 봇

Notion "인수인계" DB에 새 글이 올라오면 5분 안에 텔레그램 그룹으로 자동 전달합니다.

## 최초 설정

### 1. Notion Integration 만들기
1. https://www.notion.so/my-integrations 접속 → "New integration" 클릭
2. 이름 아무거나(예: "CS 알림봇") 입력하고 워크스페이스 선택 후 생성
3. "Internal Integration Secret" 값을 복사해둔다 (이게 `NOTION_API_KEY`)
4. Notion에서 "인수인계" 데이터베이스 페이지를 열고 우측 상단 `...` → "연결 추가"에서 방금 만든 통합을 검색해서 연결한다 (이 단계를 빼먹으면 API가 DB를 못 본다)

### 2. Notion Database ID 확인하기
"인수인계" DB를 브라우저에서 열면 주소가 다음과 같은 형태다:
`https://www.notion.so/워크스페이스이름/1234567890abcdef1234567890abcdef?v=...`
`?` 앞, 마지막 슬래시 뒤의 32자리 문자열이 `NOTION_DATABASE_ID`다.

### 3. 텔레그램 봇 만들기
1. 텔레그램에서 `@BotFather` 검색 후 대화 시작
2. `/newbot` 입력 → 봇 이름과 사용자명(끝에 bot이 들어가야 함) 입력
3. 발급받은 토큰이 `TELEGRAM_BOT_TOKEN`
4. 회사 팀 그룹방에 방금 만든 봇을 초대한다

### 4. 텔레그램 Chat ID 확인하기
1. 봇을 그룹에 초대한 뒤, 그룹에 아무 메시지나 하나 남긴다
2. 브라우저에서 다음 주소를 연다 (`<BOT_TOKEN>` 자리에 실제 토큰 입력):
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
3. 응답 JSON에서 `"chat":{"id": -1001234567890, ...}` 값을 찾는다 — 이 숫자(마이너스 포함)가 `TELEGRAM_CHAT_ID`

### 5. GitHub Secrets 등록
이 리포지토리의 Settings → Secrets and variables → Actions → "New repository secret"에서 아래 4개를 등록한다.
- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 6. 최초 state.json 값 확인
`state.json`의 `last_checked` 값이 "지금 배포하는 시점"으로 되어 있는지 확인한다. 이 값보다 이전에 생성된 인수인계 글은 알림이 가지 않는다 (의도된 동작).

## 동작 확인
GitHub 리포지토리의 Actions 탭 → "Notion Handover Notifier" 워크플로우 → "Run workflow" 버튼으로 수동 실행해서 텔레그램에 메시지가 오는지 확인한다. 이후에는 5분마다 자동으로 실행된다.

## 토큰이 만료되었거나 그룹을 바꿔야 할 때
위 1~5번 과정을 다시 밟아서 새 값으로 GitHub Secrets만 갱신하면 된다. 코드를 건드릴 필요는 없다.
