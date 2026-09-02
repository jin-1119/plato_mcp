"""
PLATO Moodle Web Service 로 실제 어디까지 가능한지 탐색하는 스크립트.

1) 토큰 발급 + site_info 로 이 토큰에 허용된 wsfunction 전체 목록 덤프
2) 강좌 목록 조회 (core_enrol_get_users_courses)
3) 첫 번째 강좌를 대상으로 아래 기능들을 하나씩 호출해보고 성공/실패 기록:
   - 강좌 콘텐츠(주차별 자료) : core_course_get_contents
   - 과제 목록                 : mod_assign_get_assignments
   - 공지사항(뉴스포럼)         : mod_forum_get_forums_by_courses / mod_forum_get_forum_discussions
   - 성적                      : gradereport_user_get_grade_items
   - 캘린더 이벤트              : core_calendar_get_calendar_events
   - 알림/메시지                : core_message_get_messages (내 알림함)

결과를 콘솔에 출력하고 마지막에 요약 표를 보여준다.
자격증명은 .env 에서만 읽는다.
"""

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
    username = values.get("PNU_STUDENTS_ID")
    password = values.get("PNU_STUDENTS_PASSWORD")
    if not username or not password:
        print("[오류] .env에서 자격증명을 찾지 못했습니다.")
        sys.exit(1)
    return username, password


def get_token(username, password):
    resp = requests.get(
        TOKEN_ENDPOINT,
        params={"username": username, "password": password, "service": SERVICE},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "token" not in data:
        print(f"[오류] 토큰 발급 실패: {data}")
        sys.exit(1)
    return data["token"]


def call(token, wsfunction, **extra_params):
    params = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
    }
    params.update(extra_params)
    resp = requests.get(REST_ENDPOINT, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def summarize(data, max_len=300):
    text = json.dumps(data, ensure_ascii=False)
    if len(text) > max_len:
        return text[:max_len] + f"... (총 {len(text)}자)"
    return text


def main():
    username, password = load_credentials()
    token = get_token(username, password)
    print(f"[OK] 토큰 발급 완료\n")

    site_info = call(token, "core_webservice_get_site_info")
    userid = site_info.get("userid")
    functions = site_info.get("functions", [])
    fn_names = sorted(f["name"] for f in functions)

    print(f"=== 이 토큰에 허용된 wsfunction 개수: {len(fn_names)} ===")
    for name in fn_names:
        print(f"  - {name}")
    print()

    # 강좌 목록
    print("=== 강좌 목록 조회 (core_enrol_get_users_courses) ===")
    courses = call(token, "core_enrol_get_users_courses", userid=userid)
    if isinstance(courses, dict) and "errorcode" in courses:
        print(f"[실패] {courses}")
        courses = []
    else:
        for c in courses:
            print(f"  id={c.get('id')}, shortname={c.get('shortname')}, fullname={c.get('fullname')}")
    print()

    if not courses:
        print("강좌가 없어 이후 테스트를 건너뜁니다.")
        return

    course_id = courses[0]["id"]
    print(f"=== 대상 강좌: id={course_id} ({courses[0].get('fullname')}) ===\n")

    results = {}

    tests = [
        ("core_course_get_contents", {"courseid": course_id}),
        ("mod_assign_get_assignments", {"courseids[0]": course_id}),
        ("mod_forum_get_forums_by_courses", {"courseids[0]": course_id}),
        ("gradereport_user_get_grade_items", {"courseid": course_id, "userid": userid}),
        ("core_calendar_get_calendar_events", {}),
        ("core_message_get_messages", {
            "useridto": userid, "useridfrom": 0, "type": "notifications",
            "read": 0, "newestfirst": 1, "limitfrom": 0, "limitnum": 5,
        }),
        ("core_notes_get_course_notes", {"courseid": course_id}),
    ]

    for wsfunction, params in tests:
        print(f"--- {wsfunction} ---")
        try:
            data = call(token, wsfunction, **params)
        except requests.RequestException as e:
            print(f"[네트워크 오류] {e}\n")
            results[wsfunction] = "네트워크 오류"
            continue

        if isinstance(data, dict) and "errorcode" in data:
            print(f"[실패] errorcode={data.get('errorcode')}, error={data.get('error')}")
            results[wsfunction] = f"실패: {data.get('errorcode')}"
        else:
            print(f"[성공] {summarize(data)}")
            results[wsfunction] = "성공"
        print()

    print("=== 요약 ===")
    for fn, status in results.items():
        print(f"  {fn}: {status}")


if __name__ == "__main__":
    main()
