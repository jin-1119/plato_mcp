"""강좌 자료(파일) 다운로드가 실제로 가능한지 테스트."""
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


def main():
    username, password = load_credentials()
    token = get_token(username, password)

    # 재무관리 강좌(파일 자료가 있어보임)
    course_id = 5973
    contents = call(token, "core_course_get_contents", courseid=course_id)

    file_candidates = []
    for section in contents:
        for m in section.get("modules", []):
            for f in m.get("contents", []) or []:
                if f.get("type") == "file":
                    file_candidates.append((m.get("name"), f))

    if not file_candidates:
        print("파일형 자료를 찾지 못했습니다. 다른 강좌를 확인하세요.")
        return

    mod_name, file_info = file_candidates[0]
    fileurl = file_info["fileurl"]
    filename = file_info["filename"]
    filesize = file_info["filesize"]

    print(f"[대상] 모듈='{mod_name}', 파일명='{filename}', 크기={filesize} bytes")
    print(f"[원본 fileurl] {fileurl}")

    # Moodle 표준: fileurl에 token 파라미터를 붙이면 인증된 다운로드 가능
    download_url = fileurl + ("&" if "?" in fileurl else "?") + f"token={token}"
    print(f"[다운로드 시도] {download_url[:100]}...")

    resp = requests.get(download_url, timeout=30)
    print(f"[응답] status={resp.status_code}, content-type={resp.headers.get('content-type')}, 실제 바이트수={len(resp.content)}")

    if resp.status_code == 200 and len(resp.content) > 0:
        out_path = Path(__file__).parent / f"downloaded_{filename}"
        out_path.write_bytes(resp.content)
        print(f"[성공] 저장됨: {out_path} ({out_path.stat().st_size} bytes)")
    else:
        print("[실패] 다운로드 안됨")
        print(resp.text[:500])


if __name__ == "__main__":
    main()
