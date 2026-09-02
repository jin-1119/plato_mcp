"""
PLATO(plato.pusan.ac.kr)에서 Moodle Mobile 공식 앱용 Web Service가
실제로 활성화되어 있는지 확인하는 테스트 스크립트.

.env 파일에서 PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD를 읽어
1) login/token.php 로 wstoken 발급을 시도하고
2) 발급된 토큰으로 core_webservice_get_site_info 를 호출해본다.

자격증명은 .env에서만 읽고, 콘솔에는 절대 출력하지 않는다.
"""

import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

BASE_URL = "https://plato.pusan.ac.kr"
TOKEN_ENDPOINT = f"{BASE_URL}/login/token.php"
REST_ENDPOINT = f"{BASE_URL}/webservice/rest/server.php"

# 학교/Moodle 설치에 따라 서비스 shortname이 다를 수 있어 여러 후보를 시도
SERVICE_CANDIDATES = ["moodle_mobile_app", "local_mobile", "core"]


def load_credentials() -> tuple[str, str]:
    env_path = Path(__file__).parent / ".env"
    values = dotenv_values(env_path)
    username = values.get("PNU_STUDENTS_ID")
    password = values.get("PNU_STUDENTS_PASSWORD")
    if not username or not password:
        print("[오류] .env에서 PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD를 찾지 못했습니다.")
        sys.exit(1)
    return username, password


def try_get_token(username: str, password: str, service: str) -> dict:
    resp = requests.get(
        TOKEN_ENDPOINT,
        params={"username": username, "password": password, "service": service},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def try_site_info(token: str) -> dict:
    resp = requests.get(
        REST_ENDPOINT,
        params={
            "wstoken": token,
            "wsfunction": "core_webservice_get_site_info",
            "moodlewsrestformat": "json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    username, password = load_credentials()
    print(f"[정보] 계정 {username[:2]}{'*' * max(len(username) - 2, 0)} 로 테스트 시작\n")

    token = None
    used_service = None

    for service in SERVICE_CANDIDATES:
        print(f"--- service='{service}' 로 토큰 발급 시도 ---")
        try:
            result = try_get_token(username, password, service)
        except requests.RequestException as e:
            print(f"[네트워크 오류] {e}\n")
            continue

        if "token" in result:
            token = result["token"]
            used_service = service
            print(f"[성공] 토큰 발급됨 (service={service})\n")
            break
        else:
            errorcode = result.get("errorcode", "unknown")
            error = result.get("error", "")
            print(f"[실패] errorcode={errorcode}, error={error}")
            if errorcode == "invalidlogin":
                print("  -> 웹서비스 자체는 활성화되어 있으나 로그인 정보가 틀렸을 가능성이 있습니다.")
            elif errorcode in ("servicenotavailable", "webservicesnotenabled"):
                print("  -> 이 서비스는 비활성화되어 있는 것으로 보입니다. 다음 후보로 시도합니다.")
            print()

    if not token:
        print("=== 결론: 어떤 service 후보로도 토큰 발급에 실패했습니다. ===")
        print("자격증명이 맞다면, Moodle Mobile 웹서비스가 비활성화되어 있거나")
        print("SSO 연동으로 인해 다른 인증 흐름이 필요한 것으로 보입니다.")
        sys.exit(1)

    print(f"--- core_webservice_get_site_info 호출 (service={used_service}) ---")
    try:
        site_info = try_site_info(token)
    except requests.RequestException as e:
        print(f"[네트워크 오류] {e}")
        sys.exit(1)

    if "errorcode" in site_info:
        print(f"[실패] errorcode={site_info.get('errorcode')}, error={site_info.get('error')}")
        sys.exit(1)

    print("[성공] site info 조회됨:")
    for key in ("sitename", "username", "fullname", "userid", "release", "version"):
        if key in site_info:
            print(f"  {key}: {site_info[key]}")

    print("\n=== 결론: Moodle Mobile 공식 Web Service가 활성화되어 있고, ===")
    print("=== 정상적으로 wstoken 발급 및 REST API 호출이 가능합니다. ===")


if __name__ == "__main__":
    main()
