import json

STATE_FILE = "state.json"


def load_state(path=STATE_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state, path=STATE_FILE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def parse_page(page):
    props = page["properties"]

    title_list = props["이름"]["title"]
    name = title_list[0]["plain_text"] if title_list else "(제목 없음)"

    summary_list = props["요약"]["rich_text"]
    summary = summary_list[0]["plain_text"] if summary_list else ""

    checklist_list = props["체크할것"]["rich_text"]
    checklist = checklist_list[0]["plain_text"] if checklist_list else ""

    return {
        "name": name,
        "summary": summary,
        "checklist": checklist,
        "created_time": page["created_time"],
        "url": page["url"],
    }
