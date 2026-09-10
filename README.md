# CS 인수인계 → 텔레그램 알림 봇

Notion "인수인계" DB에 새 글이 올라오면 하루 2번(오전 9시, 오후 9시 KST) 텔레그램 그룹으로 자동 전달합니다.

## 어떻게 동작하나요?

- **주기**: 상시 켜진 서버나 PC 없이, GitHub Actions가 하루 2번(한국시간 오전 9시, 오후 9시) 저장소를 체크아웃해서 `notify.py`를 대신 실행해줍니다. 이 시각은 랜싱(미국 동부시간) 기준으로 각각 전날 저녁 8시경, 당일 아침 8시경에 도착하도록 맞춘 것입니다.
- **감지 방식**: 마지막으로 확인한 시각(`state.json`의 `last_checked`) 이후에 "인수인계" DB에 새로 생성된 페이지가 있는지 Notion API로 조회합니다. 새 글이 없으면 아무 일도 안 하고 조용히 끝납니다.
- **"요약"이 어떻게 만들어지나요**: "요약"/"체크할것" 속성은 사람이 대충 적는 메모라 그대로 보내기엔 부족합니다. 대신 그 노션 페이지의 **본문**(문단, 목록, 체크박스 등에 적힌 실제 내용)을 전부 읽어서 Claude(AI)에게 "핵심만 간결하게" 요약해달라고 요청합니다. 본문이 비어있으면 "요약"/"체크할것" 속성을 대신 쓰고, 그마저도 없으면 요약 줄 자체가 빠집니다. AI 요약이 실패하면(일시적 오류 등) 다듬어지지 않은 원문이라도 그대로 보내서, 알림 자체가 안 가는 일은 없게 합니다.
- **스크린샷**: 본문에 붙여놓은 이미지가 있으면 텍스트 메시지 다음에 그대로 사진으로 첨부합니다. AI가 이미지 내용을 분석하지는 않고, 원본 그대로 전달만 합니다. 이미지 전송이 실패해도(드묾) 텍스트 메시지는 이미 갔으므로 그 글은 정상 처리된 것으로 간주합니다.
- **가져오는 항목**: "이름"(제목, 예: "야간 김예빈"), 본문 기반 AI 요약, 본문 이미지, 그리고 해당 노션 페이지로 바로 이동하는 링크.
- **메시지 예시**:
  ```
  🌙 야간 김예빈 (2026-09-08)
  요약: 서보 알람 반복 발생, 케이블 점검 후 재가동함. 야간조 특이사항 없음.
  [노션에서 보기 링크]
  (본문에 스크린샷이 있으면 이어서 사진 전송)
  ```
  - "이름"이 "야간"으로 시작하면 🌙, "주간"으로 시작하면 ☀️ 이모지가 붙습니다.
  - 날짜는 한국 시간(KST) 기준으로 표시됩니다.
  - 요약이 1000자를 넘으면 뒷부분이 `…`로 잘려서 표시됩니다(AI가 이미 간결하게 만들지만 안전장치로 유지).
- **여러 건이 한꺼번에 생겼을 때**: 오래된 글부터 순서대로 하나씩 보냅니다. 중간에 텍스트 전송이 실패하면 그 지점에서 멈추고, 실패한 글과 그 뒤에 밀려있던 글들은 전부 다음 실행 주기에 다시 시도합니다.

## 최초 설정

### 1. Notion Integration 만들기
1. https://www.notion.so/my-integrations 접속 → "New integration" 클릭
2. 이름 아무거나(예: "CS 알림봇") 입력하고 워크스페이스 선택 후 생성
3. "Internal Integration Secret" 값을 복사해둔다 (이게 `NOTION_API_KEY`)
4. Notion에서 "인수인계" 데이터베이스 페이지를 열고 우측 상단 `...` → "연결 추가"에서 방금 만든 통합을 검색해서 연결한다 (이 단계를 빼먹으면 API가 DB를 못 본다)

### 2. Notion Database ID 확인하기
"인수인계" DB를 브라우저에서 열면 주소창에 다음 두 형태 중 하나가 뜬다 (Notion 버전에 따라 다름):

- 신형: `https://app.notion.com/p/1234567890abcdef1234567890abcdef?v=...`
- 구형: `https://www.notion.so/워크스페이스이름/인수인계-1234567890abcdef1234567890abcdef?v=...`

**주의:** 구형 URL에는 데이터베이스 이름(이 경우 "인수인계")이 같이 붙어 있습니다. `NOTION_DATABASE_ID`로는 **이름을 제외한, `?` 바로 앞의 마지막 32자리 16진수 문자열만** 복사합니다. `?v=` 뒤에 오는 값은 "뷰(view) ID"라서 필요 없습니다.
- ❌ 잘못된 예: `인수인계-1234567890abcdef1234567890abcdef`
- ✓ 올바른 예: `1234567890abcdef1234567890abcdef`

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

### 5. Anthropic(Claude) API 키 발급

1. https://console.anthropic.com 접속 후 로그인/가입
2. 좌측 메뉴에서 "API Keys" → "Create Key"
3. 발급받은 키(`sk-ant-...`로 시작)가 `ANTHROPIC_API_KEY`
4. 사용량에 따라 소액 과금됨(짧은 텍스트를 하루 몇 번 요약하는 수준이라 매우 저렴함) — 결제 수단 등록이 필요할 수 있음

### 6. GitHub Secrets 등록
이 리포지토리의 Settings → Secrets and variables → Actions → "New repository secret"에서 아래 5개를 등록한다.
- `NOTION_API_KEY`
- `NOTION_DATABASE_ID`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ANTHROPIC_API_KEY`

### 7. 최초 state.json 만들기 (배포 전 반드시 직접 실행)
`state.json`은 리포지토리에 들어있지 않습니다. 저절로 생기지 않으므로, **배포 첫 단계로 아래 명령을 직접 실행해서 만들어야 합니다.** 이 파일이 없으면 봇은 동작하지 않습니다.

명령을 실행하면 `last_checked` 값이 실행 시점(UTC)으로 기록되며, 그보다 이전에 생성된 인수인계 글은 알림이 가지 않습니다 (의도된 동작).

**아래 명령을 실행해 `state.json`을 생성하고 커밋합니다 (나중에 재시딩이 필요할 때도 같은 명령을 씁니다):**
```bash
python -c "from datetime import datetime, timezone; import json; json.dump({'last_checked': datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')}, open('state.json','w'))"
git add state.json
git commit -m "chore: state.json 재시딩"
git push
```

### 8. 동작 확인
GitHub 리포지토리의 Actions 탭 → "Notion Handover Notifier" 워크플로우 → "Run workflow" 버튼으로 수동 실행해서 텔레그램에 메시지가 오는지 확인한다. 이후에는 정해진 시각마다 자동으로 실행된다.

### 9. 토큰이 만료되었거나 그룹을 바꿔야 할 때
위 1~6번 과정을 다시 밟아서 새 값으로 GitHub Secrets만 갱신하면 된다. 코드를 건드릴 필요는 없다.
