import json
from pathlib import Path
from unittest.mock import patch, MagicMock

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

    assert message == (
        "🌙 야간 김예빈 (2026-09-08)\n"
        "요약: 서보 다 전원 나간 이유..\n"
        "체크할것: 알람 없음 확인필요...\n"
        "[노션에서 보기](https://www.notion.so/abcdef1234567890)"
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

    assert message == (
        "☀️ 주간 백규균 (2026-09-09)\n"
        "[노션에서 보기](https://www.notion.so/1122334455667788)"
    )


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
    assert called_payload["parse_mode"] == "Markdown"


@patch("notify.requests.post")
def test_send_telegram_message_failure_returns_false(mock_post):
    mock_post.side_effect = requests.RequestException("network error")

    result = send_telegram_message("fake-bot-token", "fake-chat-id", "hello")

    assert result is False
