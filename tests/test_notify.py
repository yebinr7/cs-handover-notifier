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
            "timestamp": "created_time",
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


from notify import fetch_page_blocks, extract_body_text, extract_image_urls


def load_fixture_blocks():
    data = json.loads((FIXTURES_DIR / "notion_blocks_response.json").read_text(encoding="utf-8"))
    return data["results"]


def test_extract_body_text_joins_text_blocks_in_order():
    blocks = load_fixture_blocks()

    result = extract_body_text(blocks)

    assert result == "서보 알람이 계속 떠서 확인해봄\n전원 케이블 재확인 필요"


def test_extract_body_text_returns_empty_string_for_no_text_blocks():
    blocks = [{"type": "divider", "divider": {}}]

    result = extract_body_text(blocks)

    assert result == ""


def test_extract_image_urls_handles_file_and_external_types():
    blocks = load_fixture_blocks()

    result = extract_image_urls(blocks)

    assert result == [
        "https://notion-file.example.com/alarm1.png",
        "https://example.com/external.png",
    ]


def test_extract_image_urls_returns_empty_list_when_no_images():
    blocks = [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "hi"}]}}]

    result = extract_image_urls(blocks)

    assert result == []


@patch("notify.requests.get")
def test_fetch_page_blocks_returns_results_list(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": [{"type": "paragraph"}]}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = fetch_page_blocks("fake-token", "fake-page-id")

    assert result == [{"type": "paragraph"}]
    called_url = mock_get.call_args.args[0]
    assert called_url == "https://api.notion.com/v1/blocks/fake-page-id/children"
    called_headers = mock_get.call_args.kwargs["headers"]
    assert called_headers["Authorization"] == "Bearer fake-token"
    assert called_headers["Notion-Version"] == "2022-06-28"


from notify import condense_text


@patch("notify.requests.post")
def test_condense_text_returns_claude_response(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "서보 알람 확인 후 케이블 점검 필요"}]
    }
    mock_post.return_value = mock_response

    result = condense_text("fake-anthropic-key", "긴 원본 텍스트...")

    assert result == "서보 알람 확인 후 케이블 점검 필요"
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.anthropic.com/v1/messages"
    called_headers = mock_post.call_args.kwargs["headers"]
    assert called_headers["x-api-key"] == "fake-anthropic-key"
    called_payload = mock_post.call_args.kwargs["json"]
    assert called_payload["model"] == "claude-haiku-4-5-20251001"
    assert "긴 원본 텍스트..." in called_payload["messages"][0]["content"]


@patch("notify.requests.post")
def test_condense_text_falls_back_to_original_on_failure(mock_post):
    mock_post.side_effect = requests.RequestException("timeout")

    result = condense_text("fake-anthropic-key", "원본 텍스트")

    assert result == "원본 텍스트"


@patch("notify.requests.post")
def test_condense_text_falls_back_when_response_shape_unexpected(mock_post):
    # Anthropic API가 형식이 다른 응답을 주는 경우(예: content가 비어있음)에도
    # 예외로 죽지 말고 원문을 그대로 써야 발송이 막히지 않는다
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"content": []}
    mock_post.return_value = mock_response

    result = condense_text("fake-anthropic-key", "원본 텍스트")

    assert result == "원본 텍스트"


@patch("notify.requests.post")
def test_condense_text_catches_type_error_when_content_is_null(mock_post):
    # 구형 except (RequestException, KeyError, IndexError) 튜플로는 포착 못 했던 버그 사례:
    # response.json()이 {"content": null}을 반환하면 None[0] 시도 시 TypeError 발생.
    # broadened except Exception으로 이를 포착하고 원문 반환하도록 수정.
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"content": None}  # TypeError 발생 지점
    mock_post.return_value = mock_response

    result = condense_text("fake-anthropic-key", "원본 텍스트")

    assert result == "원본 텍스트"


from notify import send_telegram_photo


@patch("notify.requests.post")
def test_send_telegram_photo_success_returns_true(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = send_telegram_photo("fake-bot-token", "fake-chat-id", "https://example.com/photo.png")

    assert result is True
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://api.telegram.org/botfake-bot-token/sendPhoto"
    called_payload = mock_post.call_args.kwargs["json"]
    assert called_payload["chat_id"] == "fake-chat-id"
    assert called_payload["photo"] == "https://example.com/photo.png"


@patch("notify.requests.post")
def test_send_telegram_photo_failure_returns_false_and_redacts_token(mock_post, capsys):
    fake_token = "123456:AAH-SECRET-TOKEN-VALUE"
    mock_post.side_effect = requests.RequestException(
        f"boom https://api.telegram.org/bot{fake_token}/sendPhoto"
    )

    result = send_telegram_photo(fake_token, "fake-chat-id", "https://example.com/photo.png")

    assert result is False
    captured = capsys.readouterr()
    assert fake_token not in captured.err
    assert "***" in captured.err
