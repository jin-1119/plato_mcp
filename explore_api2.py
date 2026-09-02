"""실제 전공 강좌 대상으로 과제/성적/공지(포럼) 상세 테스트."""
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_URL = "https://plato.pusan.ac.kr"
TOKEN_ENDPOINT = f"{BASE_URL}/login/token.php"
REST_ENDPOINT = f"{BASE_URL}/webservice/rest/server.php"
SERVICE = "moodle_mobile_app"


def load_credentials():
    values = dotenv_values(Path(__file__).parent / ".env")
    return values.get("PNU_STUDENTS_ID"), values.get("PNU_STUDENTS_PASSWORD")


def get_token(username, password):
    resp = requests.get(TOKEN_ENDPOINT, params={"username": username, "password": password, "service": SERVICE}, timeout=15)
    return resp.json()["token"]


def call(token, wsfunction, **params):
    params.update({"wstoken": token, "wsfunction": wsfunction, "moodlewsrestformat": "json"})
    resp = requests.get(REST_ENDPOINT, params=params, timeout=20)
    return resp.json()


def summarize(data, max_len=500):
    text = json.dumps(data, ensure_ascii=False)
    return text if len(text) <= max_len else text[:max_len] + f"...(총 {len(text)}자)"


def main():
    username, password = load_credentials()
    token = get_token(username, password)
    site_info = call(token, "core_webservice_get_site_info")
    userid = site_info["userid"]

    # 실제 전공 강좌들
    target_courses = {
        6253: "거시경제학",
        5982: "인적자원관리",
        5973: "재무관리",
        5968: "관리회계",
    }

    for cid, name in target_courses.items():
        print(f"\n{'='*20} 강좌: {name} (id={cid}) {'='*20}")

        print("--- mod_assign_get_assignments ---")
        r = call(token, "mod_assign_get_assignments", **{"courseids[0]": cid})
        print(summarize(r))

        print("--- gradereport_user_get_grade_items ---")
        r = call(token, "gradereport_user_get_grade_items", courseid=cid, userid=userid)
        print(summarize(r))

        print("--- mod_forum_get_forums_by_courses (공지사항 게시판) ---")
        forums = call(token, "mod_forum_get_forums_by_courses", **{"courseids[0]": cid})
        print(summarize(forums))

        if isinstance(forums, list):
            for forum in forums:
                fid = forum.get("id")
                fname = forum.get("name")
                print(f"  -> 포럼 '{fname}' (id={fid}) 의 게시글 조회 시도")
                disc = call(token, "mod_forum_get_forum_discussions", forumid=fid)
                print("     " + summarize(disc, 400))

        print("--- core_course_get_contents (요약만) ---")
        contents = call(token, "core_course_get_contents", courseid=cid)
        if isinstance(contents, list):
            for section in contents:
                mod_names = [m.get("name") for m in section.get("modules", [])]
                print(f"  섹션 '{section.get('name')}': {mod_names}")


if __name__ == "__main__":
    main()

def inspect_notice_module():
    username, password = load_credentials()
    token = get_token(username, password)
    contents = call(token, "core_course_get_contents", courseid=6253)
    for section in contents:
        for m in section.get("modules", []):
            if m.get("name") in ("Notices", "공지사항", "Q&A", "Q&amp;A"):
                print(json.dumps(m, ensure_ascii=False, indent=2)[:1500])
