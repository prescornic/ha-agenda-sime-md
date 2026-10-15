"""Test the lib.agenda_sime_md library end-to-end with live credentials."""

import asyncio
import os
import sys

# Ensure lib is on path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from dotenv import load_dotenv

from lib.agenda_sime_md import SimeAccountRole, SimeClient

load_dotenv()

USERNAME = os.getenv("SIME_USERNAME")
PASSWORD = os.getenv("SIME_PASSWORD")


async def main():
    print("=== TESTING LIB.AGENDA_SIME_MD CLIENT ===")
    async with SimeClient(USERNAME, PASSWORD, role=SimeAccountRole.PARENT) as client:
        print("1. Performing login...")
        await client.login()
        print("   Login successful!")

        print("\n2. Fetching students...")
        students = await client.get_students()
        for i, s in enumerate(students, 1):
            print(f"   Student #{i}: {s.name} (id={s.id}, class={s.classroom}, school={s.school_name})")

        print("\n3. Fetching student data...")
        data = await client.get_student_data()

        print(f"\n--- Student: {data.student.name} ---")
        print(f"  Class: {data.student.classroom}")
        print(f"  Class Master: {data.student.class_master}")
        print(f"  Overall GPA: {data.general_average}")

        print("\n--- Recent Grades ---")
        for g in data.recent_grades:
            print(f"  [{g.date_str}] {g.subject}: {g.grade}")

        print("\n--- Subjects & Averages ---")
        for subj_name, subj_info in data.subjects.items():
            print(f"  {subj_name:30} Grades: {subj_info.grades} -> Avg: {subj_info.average}")

        print("\n--- Absences Summary ---")
        print(f"  Presence: {data.absence_summary.presence_percent}%")
        print(f"  Motivated: {data.absence_summary.total_motivated} (sem1: {data.absence_summary.sem1_motivated}, sem2: {data.absence_summary.sem2_motivated})")
        print(f"  Unmotivated: {data.absence_summary.total_unmotivated} (sem1: {data.absence_summary.sem1_unmotivated}, sem2: {data.absence_summary.sem2_unmotivated})")

        print("\n--- Active Homework ---")
        for hw in data.homework:
            print(f"  Due: {hw.due_date_str} | Subject: {hw.subject}")
            print(f"    Task: {hw.description}")

        print(f"\n--- Timetable Lessons ({len(data.timetable)} total) ---")
        from datetime import datetime
        today = datetime.now().date()
        today_lessons = [l for l in data.timetable if l.start_time.date() == today]
        print(f"  Today's Lessons ({len(today_lessons)}):")
        for l in today_lessons:
            print(f"    [{l.start_time.strftime('%H:%M')}-{l.end_time.strftime('%H:%M')}] {l.subject} (Room: {l.classroom}, Teacher: {l.teacher})")
            if l.topic:
                print(f"      Topic/HW: {l.topic}")

        future_lessons = [l for l in data.timetable if l.start_time.date() > today]
        if future_lessons:
            next_date = future_lessons[0].start_time.date()
            next_lessons = [l for l in future_lessons if l.start_time.date() == next_date]
            print(f"  Next School Day ({next_date}) Lessons ({len(next_lessons)}):")
            for l in next_lessons:
                print(f"    [{l.start_time.strftime('%H:%M')}-{l.end_time.strftime('%H:%M')}] {l.subject} (Room: {l.classroom}, Teacher: {l.teacher})")
                if l.topic:
                    print(f"      Topic/HW: {l.topic}")

    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(main())
