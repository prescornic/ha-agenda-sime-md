"""Tests for Agenda SIME MD sensor platform."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.agenda_sime_md.const import (
    CONF_ROLE,
    CONF_STUDENTS,
    DOMAIN,
    ROLE_PARENT,
)
from lib.agenda_sime_md.models import (
    SimeAbsenceSummary,
    SimeHomework,
    SimeLesson,
    SimeRecentGrade,
    SimeStudent,
    SimeStudentData,
    SimeSubjectGrades,
)


def create_sample_student_data() -> SimeStudentData:
    """Create sample mock student data for tests."""
    student = SimeStudent(
        id="UK00000001",
        name="Elev Exemplar",
        classroom="7A",
        school_name="Liceul Teoretic Model",
    )
    recent_grades = [
        SimeRecentGrade(date_str="15.10.2026", subject="Matematică", grade=10.0),
        SimeRecentGrade(date_str="14.10.2026", subject="Limba română", grade=9.0),
    ]
    subjects = {
        "Matematică": SimeSubjectGrades(
            subject="Matematică", grades=[10.0, 9.0, 10.0], average=9.67, semester_grade=10.0
        ),
        "Limba română": SimeSubjectGrades(
            subject="Limba română", grades=[9.0, 8.0, 10.0], average=9.0, semester_grade=9.0
        ),
    }
    absences = SimeAbsenceSummary(
        presence_percent=98,
        sem1_motivated=2,
        sem1_unmotivated=1,
        sem2_motivated=0,
        sem2_unmotivated=0,
    )

    now = dt_util.now()
    today = now.date()
    # Lessons for today: 1 past, 1 current, 1 upcoming
    past_start = now - timedelta(hours=2)
    past_end = now - timedelta(hours=1, minutes=15)

    curr_start = now - timedelta(minutes=10)
    curr_end = now + timedelta(minutes=35)

    up_start = now + timedelta(hours=2)
    up_end = up_start + timedelta(minutes=45)

    # Next school day (2 days ahead)
    next_day = today + timedelta(days=2)
    next_start = datetime.combine(
        next_day, datetime.min.time(), tzinfo=dt_util.DEFAULT_TIME_ZONE
    ) + timedelta(hours=9)
    next_end = next_start + timedelta(minutes=45)

    timetable = [
        SimeLesson(
            id="les_1",
            subject="Matematică",
            start_time=past_start,
            end_time=past_end,
            classroom="101",
            teacher="Prof. Popescu",
            topic="Ecuații de gradul II",
        ),
        SimeLesson(
            id="les_2",
            subject="Fizică",
            start_time=curr_start,
            end_time=curr_end,
            classroom="204",
            teacher="Prof. Ionescu",
            topic="Legile lui Newton",
        ),
        SimeLesson(
            id="les_3",
            subject="Chimie",
            start_time=up_start,
            end_time=up_end,
            classroom="301",
            teacher="Prof. Vasile",
            topic="Reacții chimice",
        ),
        SimeLesson(
            id="les_4",
            subject="Istorie",
            start_time=next_start,
            end_time=next_end,
            classroom="105",
            teacher="Prof. Radu",
            topic="Epoca modernă",
        ),
    ]

    homework = [
        SimeHomework(
            due_date_str="16.10.2026",
            subject="Matematică",
            description="Exercițiile 1-5 de la pagina 45",
        )
    ]

    return SimeStudentData(
        student=student,
        recent_grades=recent_grades,
        subjects=subjects,
        general_average=9.34,
        absence_summary=absences,
        homework=homework,
        timetable=timetable,
    )


async def test_sensors_setup_and_states(hass: HomeAssistant):
    """Test full sensor platform setup and entity states."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Elev Exemplar (parent_user)",
        data={
            CONF_USERNAME: "parent_user",
            CONF_PASSWORD: "secret_password",
            CONF_ROLE: ROLE_PARENT,
            CONF_STUDENTS: ["UK00000001"],
        },
        unique_id="parent_user_parent",
    )
    entry.add_to_hass(hass)

    sample_data = create_sample_student_data()

    with (
        patch("custom_components.agenda_sime_md.SimeClient.login", new_callable=AsyncMock),
        patch(
            "custom_components.agenda_sime_md.SimeClient.get_student_data",
            new_callable=AsyncMock,
            return_value=sample_data,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    # 1. Latest grade sensor
    latest_grade = hass.states.get("sensor.elev_exemplar_latest_grade")
    assert latest_grade is not None
    assert latest_grade.state == "10.0"
    assert latest_grade.attributes["subject"] == "Matematică"
    assert latest_grade.attributes["date"] == "15.10.2026"
    assert latest_grade.attributes["evaluation_date"] == "15.10.2026"

    # 1b. Latest grade date sensor
    latest_grade_date = hass.states.get("sensor.elev_exemplar_latest_grade_date")
    assert latest_grade_date is not None
    assert latest_grade_date.state == "2026-10-15"
    assert latest_grade_date.attributes["date_str"] == "15.10.2026"
    assert latest_grade_date.attributes["subject"] == "Matematică"
    assert latest_grade_date.attributes["grade"] == 10.0

    # 2. General average GPA sensor
    gpa = hass.states.get("sensor.elev_exemplar_general_average")
    assert gpa is not None
    assert gpa.state == "9.34"
    assert gpa.attributes["subjects_count"] == 2

    # 3. Absences sensor
    absences = hass.states.get("sensor.elev_exemplar_total_absences")
    assert absences is not None
    assert absences.state == "3"
    assert absences.attributes["total_motivated"] == 2
    assert absences.attributes["total_unmotivated"] == 1
    assert absences.attributes["presence_percent"] == 98

    # 4. Subject average sensors
    math_avg = hass.states.get("sensor.elev_exemplar_matematica_average")
    assert math_avg is not None
    assert math_avg.state == "9.67"
    assert math_avg.attributes["grades"] == [10.0, 9.0, 10.0]

    rom_avg = hass.states.get("sensor.elev_exemplar_limba_romana_average")
    assert rom_avg is not None
    assert rom_avg.state == "9.0"

    # 5. Today's lessons sensor with dynamic color statuses
    today_lessons = hass.states.get("sensor.elev_exemplar_today_s_lessons")
    assert today_lessons is not None
    assert today_lessons.state == "3"
    lessons_attr = today_lessons.attributes["lessons"]
    assert len(lessons_attr) == 3
    # Check statuses: past, current, upcoming
    statuses = [l["status"] for l in lessons_attr]
    assert "past" in statuses
    assert "current" in statuses
    assert "upcoming" in statuses
    # Check homework attribute
    hw_attr = today_lessons.attributes["homework"]
    assert len(hw_attr) == 1
    assert hw_attr[0]["subject"] == "Matematică"

    # 6. Next active school day lessons sensor
    next_day_lessons = hass.states.get("sensor.elev_exemplar_next_school_day_lessons")
    assert next_day_lessons is not None
    assert next_day_lessons.state == "1"
    next_attr = next_day_lessons.attributes["lessons"]
    assert len(next_attr) == 1
    assert next_attr[0]["subject"] == "Istorie"
    assert next_attr[0]["topic"] == "Epoca modernă"
