import json

from notify import load_state, save_state


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
