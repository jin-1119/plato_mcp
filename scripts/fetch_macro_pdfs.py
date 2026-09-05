"""Fetch every PDF attached to the 'macroeconomics' course into ./downloads.

Uses the real project modules (auth, moodle_client, tools/courses, files) --
not a reimplementation -- so this also doubles as a live check of that code.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import dotenv_values

from plato_mcp.auth import SessionManager
from plato_mcp.moodle_client import MoodleClient
from plato_mcp.tools.courses import list_courses_for, get_course_contents_for
from plato_mcp.files import download_course_file_for

MACRO_KEYWORDS = ["거시경제", "macroeconomic", "macro economics"]


def main():
    env = dotenv_values(Path(__file__).parent.parent / ".env")
    username = env.get("PNU_STUDENTS_ID")
    password = env.get("PNU_STUDENTS_PASSWORD")
    if not username or not password:
        print("PNU_STUDENTS_ID / PNU_STUDENTS_PASSWORD not set in .env")
        sys.exit(1)

    session_manager = SessionManager()
    client = MoodleClient(session_manager, "fetch-macro-pdfs", username, password)

    courses = list_courses_for(client)
    print(f"[강좌 목록] {len(courses)}개 강좌 발견")
    for c in courses:
        print(f"  - id={c.id} fullname={c.fullname!r} shortname={c.shortname!r}")

    matches = [
        c for c in courses
        if any(kw.lower() in c.fullname.lower() or kw.lower() in c.shortname.lower()
               for kw in MACRO_KEYWORDS)
    ]

    if not matches:
        print("\n[실패] '거시경제학' 강좌를 찾지 못했습니다. 위 목록에서 정확한 이름을 확인해주세요.")
        sys.exit(1)

    if len(matches) > 1:
        print("\n[경고] 여러 강좌가 매칭되었습니다:")
        for c in matches:
            print(f"  - id={c.id} fullname={c.fullname!r}")

    for course in matches:
        print(f"\n[대상 강좌] id={course.id} fullname={course.fullname!r}")
        sections = get_course_contents_for(client, course.id)

        pdf_targets = []
        for section in sections:
            for module in section.modules:
                for f in module.contents:
                    if f.filename.lower().endswith(".pdf"):
                        pdf_targets.append((section.name, module.name, f))

        print(f"[PDF 목록] {len(pdf_targets)}개 발견")
        if not pdf_targets:
            continue

        out_dir = Path(__file__).parent.parent / "downloads" / re.sub(r'[\\/:*?"<>|]', "_", course.fullname)
        out_dir.mkdir(parents=True, exist_ok=True)

        for section_name, module_name, f in pdf_targets:
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", f.filename)
            dest = out_dir / safe_name
            print(f"  다운로드 중: [{section_name}] {module_name} -> {f.filename}")
            try:
                result = download_course_file_for(client, f.fileurl, str(dest), max_download_mb=100)
                print(f"    성공: {result.path} ({result.size_bytes} bytes)")
            except Exception as e:
                print(f"    실패: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
