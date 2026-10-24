"""HTML and APEX response parsers for agenda_sime_md."""

from __future__ import annotations

import logging
import re
import urllib.parse
import zoneinfo
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from .exceptions import SimeAuthError
from .models import (
    SimeAbsenceSummary,
    SimeHomework,
    SimeLesson,
    SimePortalInfo,
    SimeRecentGrade,
    SimeStudent,
    SimeStudentDashboardData,
    SimeSubjectGrades,
)

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://agenda.sime.md"
CHISINAU_TZ = zoneinfo.ZoneInfo("Europe/Chisinau")


def get_input_value(soup: BeautifulSoup, element_id: str, default: str = "") -> str:
    """Helper to extract value of an input element by ID or name."""
    inp = soup.find("input", id=element_id) or soup.find("input", attrs={"name": element_id})
    if inp:
        return inp.get("value", default)
    return default


def parse_student_profile(soup: BeautifulSoup) -> SimeStudent:
    """Extract student profile data from main-page page items."""
    student_id = get_input_value(soup, "P1_ELEVE_ID")
    name = get_input_value(soup, "P1_ELEVE")
    birthdate = get_input_value(soup, "P1_BIRTH_DATE") or None
    uk = get_input_value(soup, "P1_ELEVE_UK") or get_input_value(soup, "P1_UK") or None
    classroom = get_input_value(soup, "P1_CLASS_NAME") or None
    school = get_input_value(soup, "P1_INSTITUTION_NAME") or None
    diriginte = get_input_value(soup, "P1_DIRIGINTE") or None
    address = get_input_value(soup, "P1_ADDRESS") or None
    study_year = get_input_value(soup, "P1_STUDY_YEAR") or None
    sem_str = get_input_value(soup, "P1_SEMESTER_ID", "1")
    try:
        semester = int(sem_str)
    except ValueError:
        semester = 1

    return SimeStudent(
        id=student_id,
        name=name,
        birthdate=birthdate,
        permanent_code=uk,
        classroom=classroom,
        school_name=school,
        class_master=diriginte,
        address=address,
        study_year=study_year,
        current_semester=semester,
    )


def parse_recent_grades(html_snippet: str) -> list[SimeRecentGrade]:
    """Parse recent evaluations from P1_LAST_3_EVAL_LIST HTML string."""
    grades = []
    if not html_snippet:
        return grades

    soup = BeautifulSoup(html_snippet, "html.parser")
    for li in soup.find_all("li"):
        date_span = li.find(class_="eval-date")
        disc_span = li.find(class_="eval-discipline")
        grade_span = li.find(class_="grade")

        if date_span and disc_span and grade_span:
            date_str = date_span.get_text(strip=True)
            subject = disc_span.get_text(strip=True).rstrip(":")
            grade_text = grade_span.get_text(strip=True)
            try:
                grade_val = float(grade_text.replace(",", "."))
                grades.append(
                    SimeRecentGrade(
                        date_str=date_str,
                        subject=subject,
                        grade=grade_val,
                    )
                )
            except ValueError:
                continue

    return grades


def parse_semester_grades_table(report_html: str) -> dict[str, SimeSubjectGrades]:
    """Parse semester grade report HTML into subject grades and averages."""
    subjects: dict[str, SimeSubjectGrades] = {}
    if not report_html:
        return subjects

    soup = BeautifulSoup(report_html, "html.parser")
    table = soup.find("table", class_=lambda c: c and "t-Report-report" in c)
    if not table:
        return subjects

    for tr in table.find_all("tr"):
        disc_td = tr.find("td", headers=lambda h: h and "DISCIPLINA" in h)
        eval_td = tr.find("td", headers=lambda h: h and "LISTA_EVALUATION" in h)
        med_td = tr.find("td", headers=lambda h: h and "MED_SEM" in h)

        if not disc_td:
            continue

        subject_name = disc_td.get_text(strip=True)
        if not subject_name:
            continue

        raw_grades = []
        if eval_td:
            eval_text = eval_td.get_text(strip=True)
            for part in re.split(r"[,;]+", eval_text):
                cleaned = part.strip().replace(",", ".")
                if cleaned:
                    try:
                        raw_grades.append(float(cleaned))
                    except ValueError:
                        pass

        semester_grade = None
        if med_td:
            med_text = med_td.get_text(strip=True).replace(",", ".")
            if med_text:
                try:
                    semester_grade = float(med_text)
                except ValueError:
                    pass

        entry = SimeSubjectGrades(
            subject=subject_name,
            grades=raw_grades,
            semester_grade=semester_grade,
        )
        entry.average = entry.calculate_average()
        subjects[subject_name] = entry

    return subjects


def parse_homework(html_snippet: str) -> list[SimeHomework]:
    """Parse active homework from P1_HOMEWORK HTML string."""
    tasks = []
    if not html_snippet:
        return tasks

    soup = BeautifulSoup(html_snippet, "html.parser")
    # Homework lists group by <b>date</b> followed by <li><span>Subject:</span> <span>Description</span></li>
    current_date = ""
    for elem in soup.find_all(["b", "li"]):
        if elem.name == "b":
            current_date = elem.get_text(strip=True)
        elif elem.name == "li":
            spans = elem.find_all("span")
            if len(spans) >= 2:
                subject = spans[0].get_text(strip=True).rstrip(":")
                desc = spans[1].get_text(strip=True)
                tasks.append(
                    SimeHomework(
                        due_date_str=current_date,
                        subject=subject,
                        description=desc,
                    )
                )

    return tasks


def parse_absences_summary(soup: BeautifulSoup) -> SimeAbsenceSummary:
    """Extract absence numbers and presence percentage from page items."""
    try:
        presence = int(get_input_value(soup, "P1_PRESENCE_PERCENT", "100"))
    except ValueError:
        presence = 100

    def get_int(val_str: str) -> int:
        try:
            return int(val_str)
        except ValueError:
            return 0

    return SimeAbsenceSummary(
        presence_percent=presence,
        sem1_motivated=get_int(get_input_value(soup, "P1_MOTIVATED", "0")),
        sem1_unmotivated=get_int(get_input_value(soup, "P1_UNMOTIVATED", "0")),
        sem2_motivated=get_int(get_input_value(soup, "P1_MOTIVATED2", "0")),
        sem2_unmotivated=get_int(get_input_value(soup, "P1_UNMOTIVATED2", "0")),
    )


def parse_calendar_events(events_json: list[dict]) -> list[SimeLesson]:
    """Parse FullCalendar JSON events into strongly-typed SimeLesson objects."""
    lessons: list[SimeLesson] = []
    if not events_json:
        return lessons

    for ev in events_json:
        start_raw = ev.get("start")
        end_raw = ev.get("end")
        if not start_raw or not end_raw:
            continue

        try:
            start_time = datetime.fromisoformat(start_raw)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=CHISINAU_TZ)
            end_time = datetime.fromisoformat(end_raw)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=CHISINAU_TZ)
        except (ValueError, TypeError):
            continue

        url = ev.get("url", "")
        m_id = re.search(r"p19_orar_id=([0-9A-Za-z]+)", url)
        m_date = re.search(r"p19_lesson_date=([0-9\.]+)", url)
        if m_id and m_date:
            lesson_id = f"{m_id.group(1)}_{m_date.group(1)}"
        elif m_id:
            lesson_id = m_id.group(1)
        else:
            lesson_id = f"{start_raw}_{len(lessons)}"

        title_html = ev.get("title", "")
        soup = BeautifulSoup(title_html, "html.parser")

        subj_elem = soup.find(class_="lesson-text-wrap")
        subject = subj_elem.get_text(strip=True) if subj_elem else "Lecție"

        room_elem = soup.find(class_="lesson-room")
        classroom = room_elem.get_text(strip=True) if room_elem else None

        teacher_elem = soup.find(class_="lesson-teacher")
        teacher = teacher_elem.get_text(strip=True) if teacher_elem else None

        hw_elem = soup.find(class_="lesson-homework") or soup.find(class_="lesson-line3")
        topic = hw_elem.get_text(" ", strip=True) if hw_elem else None

        lessons.append(
            SimeLesson(
                id=lesson_id,
                subject=subject,
                start_time=start_time,
                end_time=end_time,
                classroom=classroom,
                teacher=teacher,
                topic=topic,
            )
        )

    lessons.sort(key=lambda x: x.start_time)
    return lessons


def parse_login_dialog_url(public_html: str, user_type: str) -> str | None:
    """Extract modal dialog URL for given user type from public portal HTML."""
    if not public_html:
        return None
    soup = BeautifulSoup(public_html, "html.parser")
    pattern = f"p101_user_type={user_type}"
    for a in soup.find_all("a", href=True):
        if "login_desktop" in a["href"] and pattern in a["href"]:
            href = a["href"]
            start = href.find("'")
            end = href.find("'", start + 1)
            if start != -1 and end != -1:
                raw_target = href[start + 1 : end]
                target = raw_target.encode("utf-8").decode("unicode_escape")
                return urllib.parse.urljoin(BASE_URL, target)
    return None


def parse_login_form_tokens(dialog_html: str) -> dict[str, Any]:
    """Extract required APEX tokens, form action, and checksums from login dialog HTML."""
    if not dialog_html:
        raise SimeAuthError("Login dialog returned empty response")
    dsoup = BeautifulSoup(dialog_html, "html.parser")
    form = dsoup.find("form")
    if not form:
        raise SimeAuthError("Login dialog did not return a valid HTML form")

    action = form.get("action")
    p_flow_id = dsoup.find("input", id="pFlowId")
    p_flow_step_id = dsoup.find("input", id="pFlowStepId")
    p_instance = dsoup.find("input", id="pInstance")
    p_page_submission_id = dsoup.find("input", id="pPageSubmissionId")
    p_reload_on_submit = dsoup.find("input", id="pReloadOnSubmit")
    p_salt = dsoup.find("input", id="pSalt")
    p_protected = dsoup.find("input", id="pPageItemsProtected")

    if not all(
        [action, p_flow_id, p_flow_step_id, p_instance, p_page_submission_id, p_salt, p_protected]
    ):
        raise SimeAuthError("Missing required APEX tokens in login form")

    checksums = {
        inp["data-for"]: inp.get("value", "")
        for inp in dsoup.find_all("input", attrs={"data-for": True})
    }

    return {
        "action": action,
        "p_flow_id": p_flow_id["value"],
        "p_flow_step_id": p_flow_step_id["value"],
        "p_instance": p_instance["value"],
        "p_page_submission_id": p_page_submission_id["value"],
        "p_reload_on_submit": p_reload_on_submit["value"] if p_reload_on_submit else "S",
        "salt": p_salt["value"],
        "protected": p_protected["value"],
        "checksums": checksums,
    }


def parse_portal_info(html: str) -> SimePortalInfo:
    """Parse student profile and tree navigation links from portal HTML."""
    if not html:
        return SimePortalInfo(
            p1_id="",
            has_tree_nav=False,
            primary_student=SimeStudent(id="", name=""),
            student_links=[],
        )
    soup = BeautifulSoup(html, "html.parser")
    p1_id = get_input_value(soup, "P1_ELEVE_ID")
    tree_nav = soup.find(id="t_TreeNav")
    has_tree_nav = tree_nav is not None
    primary_student = parse_student_profile(soup)

    student_links: list[tuple[str, str, str, bool]] = []
    if tree_nav:
        nav_lis = tree_nav.find_all("li")
        for li in nav_lis:
            a = li.find("a", href=True)
            if a and "user_eleve_id=" in a["href"]:
                m = re.search(r"user_eleve_id=([^&]+)", a["href"])
                uid = m.group(1) if m else primary_student.id
                name = a.get_text(strip=True) or primary_student.name
                href = a["href"]
                is_current = li.get("data-current") == "true" or len(nav_lis) == 1
                student_links.append((uid, name, href, is_current))

    return SimePortalInfo(
        p1_id=p1_id,
        has_tree_nav=has_tree_nav,
        primary_student=primary_student,
        student_links=student_links,
    )


def parse_student_dashboard(html: str) -> SimeStudentDashboardData:
    """Parse student dashboard HTML into profile, items, and AJAX configurations."""
    if not html:
        return SimeStudentDashboardData(
            p1_id="",
            has_tree_nav=False,
        )

    soup = BeautifulSoup(html, "html.parser")
    p1_id = get_input_value(soup, "P1_ELEVE_ID")
    tree_nav = soup.find(id="t_TreeNav")
    has_tree_nav = tree_nav is not None

    student_urls: list[tuple[str, str]] = []
    if tree_nav:
        for li in tree_nav.find_all("li"):
            a = li.find("a", href=True)
            if a and "user_eleve_id=" in a["href"]:
                m = re.search(r"user_eleve_id=([^&]+)", a["href"])
                if m:
                    uid = m.group(1)
                    student_urls.append((uid, a["href"]))

    student = parse_student_profile(soup)
    recent_eval_raw = get_input_value(soup, "P1_LAST_3_EVAL_LIST")
    homework_raw = get_input_value(soup, "P1_HOMEWORK")
    absence_summary = parse_absences_summary(soup)

    eleve_ck = None
    ck_inp = soup.find("input", attrs={"data-for": "P1_ELEVE_ID"})
    if ck_inp:
        eleve_ck = ck_inp.get("value")

    salt = get_input_value(soup, "pSalt")
    protected = get_input_value(soup, "pPageItemsProtected")

    sem_configs = [
        (
            "sem1",
            r'apex\.widget\.report\.init\("sem1","([^"]+)",\{"pageItems":"#P1_ELEVE_ID","lazyLoading":true,"internalRegionId":"([^"]+)"\}',
        ),
        (
            "sem2",
            r'apex\.widget\.report\.init\("sem2","([^"]+)",\{"pageItems":"#P1_ELEVE_ID","lazyLoading":true,"internalRegionId":"([^"]+)"\}',
        ),
    ]
    sem_ajax_configs: dict[str, tuple[str, str]] = {}
    for sem_name, pattern in sem_configs:
        match = re.search(pattern, html)
        if match:
            ajax_id = match.group(1).encode().decode("unicode_escape")
            region_id = match.group(2)
            sem_ajax_configs[sem_name] = (ajax_id, region_id)

    return SimeStudentDashboardData(
        p1_id=p1_id,
        has_tree_nav=has_tree_nav,
        student_urls=student_urls,
        student=student,
        recent_eval_raw=recent_eval_raw,
        homework_raw=homework_raw,
        absence_summary=absence_summary,
        eleve_id=p1_id,
        eleve_ck=eleve_ck,
        salt=salt,
        protected=protected,
        sem_ajax_configs=sem_ajax_configs,
    )
