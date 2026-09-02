"""Reusable tool for exploring PLATO's ubboard (Notices/Q&A) HTML structure.

Logs in via cookie session (not the Moodle webservice token -- ubboard has
no official API), scans every enrolled course's ubboard modules for post
counts, and can dump the list/detail/write-form HTML for a given board so
its structure can be inspected or saved as a test fixture.

See docs/ubboard_structure.md for the findings this tool was used to produce.

Usage:
    python scripts/analyze_ubboard.py scan
    python scripts/analyze_ubboard.py dump --board-id 37082 --out-dir tests/fixtures/ubboard
"""

import argparse
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values

BASE_URL = "https://plato.pusan.ac.kr"


def load_credentials():
    values = dotenv_values(Path(__file__).parent.parent / ".env")
    return values["PNU_STUDENTS_ID"], values["PNU_STUDENTS_PASSWORD"]


def cookie_login(username: str, password: str) -> requests.Session:
    session = requests.Session()
    resp = session.get(f"{BASE_URL}/login/index.php", timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form", id="form-login-sso")
    logintoken = form.find("input", {"name": "logintoken"})["value"]
    session.post(
        f"{BASE_URL}/login/index.php",
        data={
            "anchor": "",
            "logintoken": logintoken,
            "logintab": "univ",
            "username": username,
            "password": password,
            "rememberusername": 1,
        },
        timeout=15,
    )
    return session


def get_sesskey(session: requests.Session) -> str:
    resp = session.get(BASE_URL, timeout=15)
    match = re.search(r'"sesskey":"(\w+)"', resp.text)
    return match.group(1) if match else None


def iter_ubboard_modules(moodle_client, course_ids):
    """Yield (course, module) for every ubboard module across the given courses.

    Requires an already-authenticated MoodleClient (from moodle_client.py).
    """
    for course_id in course_ids:
        contents = moodle_client.call("core_course_get_contents", courseid=course_id)
        for section in contents:
            for module in section.get("modules", []):
                if module.get("modname") == "ubboard":
                    yield course_id, module


def scan():
    from plato_mcp.auth import SessionManager
    from plato_mcp.moodle_client import MoodleClient

    username, password = load_credentials()
    manager = SessionManager()
    client = MoodleClient(manager, "ubboard-scan", username, password)
    info = client.call("core_webservice_get_site_info")
    courses = client.call("core_enrol_get_users_courses", userid=info["userid"])
    course_ids = [c["id"] for c in courses]

    session = cookie_login(username, password)

    print(f"{'course':>7} {'module_id':>10} {'type':<8} {'name':<14} count")
    for course_id, module in iter_ubboard_modules(client, course_ids):
        resp = session.get(f"{BASE_URL}/mod/ubboard/view.php", params={"id": module["id"]}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        total_div = soup.find("div", class_="totalcount")
        count = total_div.get_text(strip=True) if total_div else "?"
        try:
            board_type = json.loads(module.get("customdata") or "{}").get("type", "?")
        except json.JSONDecodeError:
            board_type = "?"
        print(f"{course_id:>7} {module['id']:>10} {board_type:<8} {module['name']:<14} {count}")


def dump(board_id: int, out_dir: str):
    username, password = load_credentials()
    session = cookie_login(username, password)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    list_resp = session.get(f"{BASE_URL}/mod/ubboard/view.php", params={"id": board_id}, timeout=15)
    (out_path / f"list_{board_id}.html").write_text(list_resp.text, encoding="utf-8")
    print(f"saved list_{board_id}.html ({len(list_resp.text)} bytes)")

    write_resp = session.get(f"{BASE_URL}/mod/ubboard/write.php", params={"id": board_id}, timeout=15)
    (out_path / f"write_{board_id}.html").write_text(write_resp.text, encoding="utf-8")
    print(f"saved write_{board_id}.html ({len(write_resp.text)} bytes)")

    print("Note: dumped files may contain the logged-in account's display name and a")
    print("live sesskey -- scrub both before committing as a fixture (see docs/ubboard_structure.md).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scan", help="List every ubboard module across all enrolled courses with post counts")

    dump_parser = sub.add_parser("dump", help="Dump list + write-form HTML for one board")
    dump_parser.add_argument("--board-id", type=int, required=True)
    dump_parser.add_argument("--out-dir", default="tests/fixtures/ubboard")

    args = parser.parse_args()
    if args.command == "scan":
        scan()
    elif args.command == "dump":
        dump(args.board_id, args.out_dir)
