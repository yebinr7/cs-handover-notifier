import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from notify import load_state, save_state, parse_page, build_notion_query_payload, fetch_new_pages

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_load_state_reads_json(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"last_checked": "2026-09-01T00:00:00.000Z"}', encoding="utf-8")

    result = load_state(str(state_file))

    assert result == {"last_checked": "2026-09-01T00:00:00.000Z"}


def test_save_state_writes_json(tmp_path):
    state_file = tmp_path / "state.json"

    save_state({"last_checked": "2026-09-09T12:00:00.000Z"}, str(state_file))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-09T12:00:00.000Z"}


def load_fixture_pages():
    data = json.loads((FIXTURES_DIR / "notion_query_response.json").read_text(encoding="utf-8"))
    return data["results"]


def test_parse_page_extracts_fields():
    pages = load_fixture_pages()

    result = parse_page(pages[0])

    assert result == {
        "name": "야간 김예빈",
        "summary": "서보 다 전원 나간 이유..",
        "checklist": "알람 없음 확인필요...",
        "created_time": "2026-09-09T03:00:00.000Z",
        "url": "https://www.notion.so/abcdef1234567890",
    }


def test_parse_page_handles_empty_fields():
    pages = load_fixture_pages()

    result = parse_page(pages[1])

    assert result["summary"] == ""
    assert result["checklist"] == ""
    assert result["name"] == "주간 백규균"


def test_parse_page_concatenates_multi_element_rich_text():
    # Notion은 굵게/링크/줄바꿈 등 서식이 바뀌는 지점마다 rich_text를 여러 조각으로 쪼갠다.
    # 첫 번째 조각만 읽으면 나머지 텍스트가 조용히 사라지므로 전부 이어붙여야 한다.
    page = {
        "created_time": "2026-09-09T03:00:00.000Z",
        "url": "https://www.notion.so/abcdef1234567890",
        "properties": {
            "이름": {"title": [{"plain_text": "야간 "}, {"plain_text": "김예빈"}]},
            "요약": {"rich_text": [{"plain_text": "서보 "}, {"plain_text": "전원 나간 이유"}]},
            "체크할것": {"rich_text": [{"plain_text": "알람 "}, {"plain_text": "확인"}]},
        },
    }

    result = parse_page(page)

    assert result["name"] == "야간 김예빈"
    assert result["summary"] == "서보 전원 나간 이유"
    assert result["checklist"] == "알람 확인"


def test_build_notion_query_payload_filters_by_created_time():
    payload = build_notion_query_payload("2026-09-09T00:00:00.000Z")

    assert payload == {
        "filter": {
            "property": "생성일",
            "created_time": {"after": "2026-09-09T00:00:00.000Z"},
        },
        "sorts": [{"timestamp": "created_time", "direction": "ascending"}],
    }


@patch("notify.requests.post")
def test_fetch_new_pages_returns_results_list(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"id": "page-1"}]}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = fetch_new_pages("fake-token", "fake-db-id", "2026-09-09T00:00:00.000Z")

    assert result == [{"id": "page-1"}]
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.notion.com/v1/databases/fake-db-id/query"
    called_headers = mock_post.call_args.kwargs["headers"]
    assert called_headers["Authorization"] == "Bearer fake-token"
    assert called_headers["Notion-Version"] == "2022-06-28"
    # build_notion_query_payload가 만든 바디를 그대로 실어 보내는지(하드코딩/누락이 아닌지) 확인
    assert mock_post.call_args.kwargs["json"] == build_notion_query_payload(
        "2026-09-09T00:00:00.000Z"
    )


from notify import format_message


def test_format_message_night_shift_with_content():
    page = {
        "name": "야간 김예빈",
        "summary": "서보 다 전원 나간 이유..",
        "checklist": "알람 없음 확인필요...",
        "created_time": "2026-09-08T15:00:00.000Z",
        "url": "https://www.notion.so/abcdef1234567890",
    }

    message = format_message(page)

    # created_time 2026-09-08T15:00Z = KST 2026-09-09 00:00 → 표시 날짜는 09-09 (야간조 날짜 밀림 수정)
    assert message == (
        "🌙 야간 김예빈 (2026-09-09)\n"
        "요약: 서보 다 전원 나간 이유..\n"
        "체크할것: 알람 없음 확인필요...\n"
        '<a href="https://www.notion.so/abcdef1234567890">노션에서 보기</a>'
    )


def test_format_message_day_shift_without_content():
    page = {
        "name": "주간 백규균",
        "summary": "",
        "checklist": "",
        "created_time": "2026-09-09T00:00:00.000Z",
        "url": "https://www.notion.so/1122334455667788",
    }

    message = format_message(page)

    # created_time 2026-09-09T00:00Z = KST 2026-09-09 09:00 → 날짜는 09-09 그대로
    assert message == (
        "☀️ 주간 백규균 (2026-09-09)\n"
        '<a href="https://www.notion.so/1122334455667788">노션에서 보기</a>'
    )


def test_format_message_escapes_html_special_characters():
    # PLC 태그명에 흔한 밑줄/앰퍼샌드가 그대로 나가면 텔레그램이 400을 뱉고 파이프라인이 막힌다.
    page = {
        "name": "야간 Loader_Hoist & DB_1",
        "summary": "M_400_1 <알람> & 확인",
        "checklist": "",
        "created_time": "2026-09-08T15:00:00.000Z",
        "url": "https://www.notion.so/abcdef1234567890",
    }

    message = format_message(page)

    assert "야간 Loader_Hoist &amp; DB_1" in message
    assert "M_400_1 &lt;알람&gt; &amp; 확인" in message
    # 이스케이프 안 된 raw &가 남아있으면 안 된다 (&amp; 형태만 허용)
    assert "Hoist & DB" not in message
    assert "<알람>" not in message


def test_format_message_truncates_long_fields():
    # 텔레그램 4096자 제한을 넘기면 400으로 영구히 막히므로 방어적으로 자른다.
    page = {
        "name": "주간 백규균",
        "summary": "가" * 1500,
        "checklist": "나" * 1500,
        "created_time": "2026-09-09T00:00:00.000Z",
        "url": "https://www.notion.so/1122334455667788",
    }

    message = format_message(page)

    assert "요약: " + "가" * 1000 + "…" in message
    assert "체크할것: " + "나" * 1000 + "…" in message
    assert "가" * 1001 not in message


import requests

from notify import send_telegram_message


@patch("notify.requests.post")
def test_send_telegram_message_success_returns_true(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = send_telegram_message("fake-bot-token", "fake-chat-id", "hello")

    assert result is True
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.telegram.org/botfake-bot-token/sendMessage"
    called_payload = mock_post.call_args.kwargs["json"]
    assert called_payload["chat_id"] == "fake-chat-id"
    assert called_payload["text"] == "hello"
    # Markdown → HTML 전환 (사용자 텍스트의 밑줄/별표로 인한 파싱 400 방지)
    assert called_payload["parse_mode"] == "HTML"


@patch("notify.requests.post")
def test_send_telegram_message_failure_returns_false(mock_post):
    mock_post.side_effect = requests.RequestException("network error")

    result = send_telegram_message("fake-bot-token", "fake-chat-id", "hello")

    assert result is False


@patch("notify.requests.post")
def test_send_telegram_message_redacts_bot_token_in_error_log(mock_post, capsys):
    # requests 예외 메시지에는 실패한 URL이 붙는데, 텔레그램 URL에는 봇 토큰이 들어있다.
    fake_token = "123456:AAH-SECRET-TOKEN-VALUE"
    mock_post.side_effect = requests.RequestException(
        f"HTTPSConnectionPool: url https://api.telegram.org/bot{fake_token}/sendMessage failed"
    )

    result = send_telegram_message(fake_token, "fake-chat-id", "hello")

    assert result is False
    captured = capsys.readouterr()
    assert fake_token not in captured.err
    assert fake_token not in captured.out
    assert "***" in captured.err


from notify import run

FIXTURE_PAGES = [
    {
        "created_time": "2026-09-09T03:00:00.000Z",
        "url": "https://www.notion.so/abcdef1234567890",
        "properties": {
            "이름": {"title": [{"plain_text": "야간 김예빈"}]},
            "요약": {"rich_text": [{"plain_text": "서보 다 전원 나간 이유.."}]},
            "체크할것": {"rich_text": [{"plain_text": "알람 없음 확인필요..."}]},
        },
    },
    {
        "created_time": "2026-09-09T09:00:00.000Z",
        "url": "https://www.notion.so/1122334455667788",
        "properties": {
            "이름": {"title": [{"plain_text": "주간 백규균"}]},
            "요약": {"rich_text": []},
            "체크할것": {"rich_text": []},
        },
    },
]


def make_state_file(tmp_path, last_checked):
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"last_checked": last_checked}), encoding="utf-8")
    return state_file


@patch("notify.send_telegram_message")
@patch("notify.fetch_new_pages")
def test_run_advances_state_to_latest_on_full_success(mock_fetch, mock_send, tmp_path):
    mock_fetch.return_value = FIXTURE_PAGES
    mock_send.return_value = True
    state_file = make_state_file(tmp_path, "2026-09-01T00:00:00.000Z")

    result = run("token", "db-id", "bot-token", "chat-id", state_path=str(state_file))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-09T09:00:00.000Z"}
    assert mock_send.call_count == 2
    assert result is True


@patch("notify.send_telegram_message")
@patch("notify.fetch_new_pages")
def test_run_stops_state_before_failed_message(mock_fetch, mock_send, tmp_path):
    mock_fetch.return_value = FIXTURE_PAGES
    mock_send.side_effect = [True, False]
    state_file = make_state_file(tmp_path, "2026-09-01T00:00:00.000Z")

    result = run("token", "db-id", "bot-token", "chat-id", state_path=str(state_file))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-09T03:00:00.000Z"}
    assert result is False


@patch("notify.fetch_new_pages")
def test_run_keeps_state_when_notion_fetch_fails(mock_fetch, tmp_path):
    mock_fetch.side_effect = requests.RequestException("notion down")
    state_file = make_state_file(tmp_path, "2026-09-01T00:00:00.000Z")

    result = run("token", "db-id", "bot-token", "chat-id", state_path=str(state_file))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-01T00:00:00.000Z"}
    assert result is False


@patch("notify.send_telegram_message")
@patch("notify.fetch_new_pages")
def test_run_returns_true_when_nothing_to_send(mock_fetch, mock_send, tmp_path):
    mock_fetch.return_value = []
    state_file = make_state_file(tmp_path, "2026-09-01T00:00:00.000Z")

    result = run("token", "db-id", "bot-token", "chat-id", state_path=str(state_file))

    assert result is True
    assert mock_send.call_count == 0
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-01T00:00:00.000Z"}


SAME_MINUTE_PAGES = [
    {
        "created_time": "2026-09-09T03:00:00.000Z",
        "url": "https://www.notion.so/aaaa",
        "properties": {
            "이름": {"title": [{"plain_text": "야간 김예빈"}]},
            "요약": {"rich_text": []},
            "체크할것": {"rich_text": []},
        },
    },
    {
        "created_time": "2026-09-09T03:00:00.000Z",
        "url": "https://www.notion.so/bbbb",
        "properties": {
            "이름": {"title": [{"plain_text": "야간 백규균"}]},
            "요약": {"rich_text": []},
            "체크할것": {"rich_text": []},
        },
    },
]


@patch("notify.send_telegram_message")
@patch("notify.fetch_new_pages")
def test_run_rolls_back_state_when_failed_page_shares_created_time(mock_fetch, mock_send, tmp_path):
    # created_time은 분 단위라 같은 분에 만든 두 글의 타임스탬프가 동일할 수 있다.
    # 첫 글 성공 후 그 타임스탬프로 state를 올려버리면, 실패한 둘째 글이
    # 다음 사이클 필터(after, 배타적)에서 영원히 제외되어 유실된다.
    mock_fetch.return_value = SAME_MINUTE_PAGES
    mock_send.side_effect = [True, False]
    state_file = make_state_file(tmp_path, "2026-09-01T00:00:00.000Z")

    result = run("token", "db-id", "bot-token", "chat-id", state_path=str(state_file))

    assert result is False
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved == {"last_checked": "2026-09-01T00:00:00.000Z"}


from notify import main

ENV_OK = {
    "NOTION_API_KEY": "notion-key",
    "NOTION_DATABASE_ID": "db-id",
    "TELEGRAM_BOT_TOKEN": "bot-token",
    "TELEGRAM_CHAT_ID": "chat-id",
}


@patch("notify.run")
def test_main_passes_env_vars_to_run(mock_run):
    mock_run.return_value = True

    with patch.dict(os.environ, ENV_OK, clear=True):
        main()

    assert mock_run.call_args.kwargs == {
        "notion_token": "notion-key",
        "database_id": "db-id",
        "bot_token": "bot-token",
        "chat_id": "chat-id",
    }


@patch("notify.run")
def test_main_exits_1_when_run_returns_false(mock_run):
    mock_run.return_value = False

    with patch.dict(os.environ, ENV_OK, clear=True):
        with pytest.raises(SystemExit) as excinfo:
            main()

    assert excinfo.value.code == 1


@patch("notify.run")
def test_main_exits_1_when_required_env_var_missing(mock_run):
    env = dict(ENV_OK)
    del env["TELEGRAM_BOT_TOKEN"]

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit) as excinfo:
            main()

    assert excinfo.value.code == 1
    # 환경변수가 비면 Notion/텔레그램을 건드리기 전에 즉시 종료해야 한다
    assert mock_run.call_count == 0


@patch("notify.run")
def test_main_exits_1_when_required_env_var_is_empty_string(mock_run):
    # GitHub Actions는 없는 시크릿을 ""로 주입하므로 KeyError가 안 난다
    env = dict(ENV_OK, NOTION_API_KEY="")

    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit) as excinfo:
            main()

    assert excinfo.value.code == 1
    assert mock_run.call_count == 0
