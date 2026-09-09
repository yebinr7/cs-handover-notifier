import json
from pathlib import Path

from notify import load_state, save_state, parse_page

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
