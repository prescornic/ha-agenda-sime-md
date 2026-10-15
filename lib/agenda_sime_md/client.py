"""Asynchronous client for agenda.sime.md."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Self

import aiohttp
from bs4 import BeautifulSoup

from .auth import BASE_URL, SimeAuthManager
from .exceptions import SimeConnectionError
from .models import (
    SimeAccountRole,
    SimeLesson,
    SimeStudent,
    SimeStudentData,
    SimeSubjectGrades,
)
from .parser import (
    get_input_value,
    parse_absences_summary,
    parse_calendar_events,
    parse_homework,
    parse_recent_grades,
    parse_semester_grades_table,
    parse_student_profile,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-MD,ro;q=0.9,en-US;q=0.8",
}


class SimeClient:
    """Asynchronous client for interacting with agenda.sime.md."""

    def __init__(
        self,
        username: str,
        password: str,
        role: SimeAccountRole = SimeAccountRole.PARENT,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.role = role
        self.auth = SimeAuthManager(role=role)
        self._session = session
        self._own_session = session is None
        self._student_urls: dict[str, str] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or initialize the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            self._session = aiohttp.ClientSession(
                headers=DEFAULT_HEADERS,
                connector=connector,
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close client session if owned."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def login(self) -> bool:
        """Authenticate user against agenda.sime.md."""
        session = await self._get_session()
        await self.auth.login(session, self.username, self.password)
        return True

    async def _ensure_logged_in(self) -> aiohttp.ClientSession:
        """Verify authentication, re-authenticating if required."""
        session = await self._get_session()
        if not self.auth.is_authenticated:
            await self.login()
        return session

    async def get_students(self) -> list[SimeStudent]:
        """Fetch all enrolled students accessible to the logged-in account."""
        session = await self._ensure_logged_in()

        try:
            async with session.get(self.auth.portal_url) as resp:
                if resp.status != 200:
                    raise SimeConnectionError(f"HTTP {resp.status} accessing portal")
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Failed to access portal page: {err}") from err

        soup = BeautifulSoup(html, "html.parser")
        primary_student = parse_student_profile(soup)

        # Check for children in side navigation tree (#t_TreeNav)
        tree_nav = soup.find(id="t_TreeNav")
        student_links = []
        if tree_nav:
            for li in tree_nav.find_all("li"):
                a = li.find("a", href=True)
                if a and "user_eleve_id=" in a["href"]:
                    student_links.append((li, a))

        students: list[SimeStudent] = []
        self._student_urls.clear()

        if student_links:
            for li, a in student_links:
                m = re.search(r"user_eleve_id=([^&]+)", a["href"])
                uid = m.group(1) if m else primary_student.id
                name = a.get_text(strip=True) or primary_student.name
                full_url = urllib.parse.urljoin(BASE_URL, a["href"])
                self._student_urls[uid] = full_url

                is_current = li.get("data-current") == "true" or len(student_links) == 1
                if is_current:
                    primary_student.id = uid
                    p1_id = get_input_value(soup, "P1_ELEVE_ID")
                    if p1_id:
                        self._student_urls[p1_id] = full_url
                    students.append(primary_student)
                else:
                    students.append(SimeStudent(id=uid, name=name))
        else:
            self._student_urls[primary_student.id] = self.auth.portal_url
            students.append(primary_student)

        return students

    async def get_student_data(self, student_id: str | None = None) -> SimeStudentData:
        """Fetch complete school data (grades, absences, homework) for a student."""
        session = await self._ensure_logged_in()

        # Determine target navigation URL
        target_url = self._student_urls.get(student_id) if student_id else None
        if not target_url:
            target_url = self.auth.portal_url

        try:
            async with session.get(target_url) as resp:
                if resp.status != 200:
                    raise SimeConnectionError(f"Failed to fetch student data: HTTP {resp.status}")
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Network error loading student dashboard: {err}") from err

        soup = BeautifulSoup(html, "html.parser")

        # Discover or refresh student URLs from TreeNav
        tree_nav = soup.find(id="t_TreeNav")
        if tree_nav:
            for li in tree_nav.find_all("li"):
                a = li.find("a", href=True)
                if a and "user_eleve_id=" in a["href"]:
                    m = re.search(r"user_eleve_id=([^&]+)", a["href"])
                    if m:
                        uid = m.group(1)
                        self._student_urls[uid] = urllib.parse.urljoin(BASE_URL, a["href"])

        p1_id = get_input_value(soup, "P1_ELEVE_ID")
        if p1_id:
            self._student_urls[p1_id] = target_url

        # If a specific child was requested that is not the active one, navigate to it
        if student_id and student_id in self._student_urls and self._student_urls[student_id] != target_url:
            target_url = self._student_urls[student_id]
            try:
                async with session.get(target_url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to navigate to student %s: %s", student_id, err)

        # 1. Parse student profile
        student = parse_student_profile(soup)
        if student_id:
            student.id = student_id

        # 2. Parse recent grades
        recent_eval_raw = get_input_value(soup, "P1_LAST_3_EVAL_LIST")
        recent_grades = parse_recent_grades(recent_eval_raw)

        # 3. Parse homework
        homework_raw = get_input_value(soup, "P1_HOMEWORK")
        homework = parse_homework(homework_raw)

        # 4. Parse absences summary
        absence_summary = parse_absences_summary(soup)

        # 5. Fetch Semester 1 and Semester 2 grade reports
        subjects: dict[str, SimeSubjectGrades] = {}
        session_id = self.auth.session_id

        sem_configs = [
            ("sem1", r'apex\.widget\.report\.init\("sem1","([^"]+)",\{"pageItems":"#P1_ELEVE_ID","lazyLoading":true,"internalRegionId":"([^"]+)"\}'),
            ("sem2", r'apex\.widget\.report\.init\("sem2","([^"]+)",\{"pageItems":"#P1_ELEVE_ID","lazyLoading":true,"internalRegionId":"([^"]+)"\}'),
        ]

        eleve_id = get_input_value(soup, "P1_ELEVE_ID")
        eleve_ck = None
        ck_inp = soup.find("input", attrs={"data-for": "P1_ELEVE_ID"})
        if ck_inp:
            eleve_ck = ck_inp.get("value")

        salt = get_input_value(soup, "pSalt")
        protected = get_input_value(soup, "pPageItemsProtected")

        if session_id and eleve_id and eleve_ck:
            ajax_url = f"{BASE_URL}/ords/wwv_flow.ajax?p_context=main/main-page/{session_id}"
            ajax_headers = {
                "Referer": target_url,
                "Origin": BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, */*; q=0.01",
            }

            for sem_name, pattern in sem_configs:
                match = re.search(pattern, html)
                if match:
                    ajax_id = match.group(1).encode().decode("unicode_escape")
                    _region_id = match.group(2)

                    r_obj = {
                        "salt": salt,
                        "pageItems": {
                            "itemsToSubmit": [{"n": "P1_ELEVE_ID", "v": eleve_id, "ck": eleve_ck}],
                            "protected": protected,
                            "rowVersion": "",
                            "formRegionChecksums": [],
                        },
                    }

                    payload = {
                        "p_flow_id": "104",
                        "p_flow_step_id": "1",
                        "p_instance": session_id,
                        "p_request": f"PLUGIN={ajax_id}",
                        "p_json": json.dumps(r_obj),
                    }

                    try:
                        async with session.post(ajax_url, data=payload, headers=ajax_headers) as rep_resp:
                            if rep_resp.status == 200:
                                rep_html = await rep_resp.text()
                                sem_subjects = parse_semester_grades_table(rep_html)
                                for subj_name, subj_data in sem_subjects.items():
                                    if subj_name not in subjects:
                                        subjects[subj_name] = subj_data
                                    else:
                                        # Merge marks across semesters
                                        subjects[subj_name].grades.extend(subj_data.grades)
                                        subjects[subj_name].average = subjects[subj_name].calculate_average()
                    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                        _LOGGER.warning("Failed to fetch %s grades report: %s", sem_name, err)

        # 6. Calculate overall general average
        averages = [s.average for s in subjects.values() if s.average is not None]
        general_avg = round(sum(averages) / len(averages), 2) if averages else None

        # 7. Fetch Timetable / Agenda Calendar
        timetable: list[SimeLesson] = []
        fc_match = re.search(
            r'apex\.widget\.fullCalendar\(\{.*?\"ajaxIdentifier\":\"([^\"]+)\"',
            html,
            re.DOTALL,
        )
        if fc_match and session_id and eleve_id:
            fc_ajax_id = fc_match.group(1).encode().decode("unicode_escape")
            now_dt = datetime.now()
            start_str = (now_dt - timedelta(days=7)).strftime("%Y%m%d000000")
            end_str = (now_dt + timedelta(days=30)).strftime("%Y%m%d235959")

            fc_obj = {
                "salt": salt,
                "pageItems": {
                    "itemsToSubmit": [{"n": "P1_ELEVE_ID", "v": eleve_id, "ck": eleve_ck}]
                    if eleve_ck
                    else [],
                    "protected": protected,
                    "rowVersion": "",
                    "formRegionChecksums": [],
                },
            }

            fc_payload = {
                "p_flow_id": "104",
                "p_flow_step_id": "1",
                "p_instance": session_id,
                "p_request": f"PLUGIN={fc_ajax_id}",
                "x01": "GET",
                "x02": start_str,
                "x03": end_str,
                "p_json": json.dumps(fc_obj),
            }

            try:
                async with session.post(ajax_url, data=fc_payload, headers=ajax_headers) as fc_resp:
                    if fc_resp.status == 200:
                        fc_data = await fc_resp.json(content_type=None)
                        if isinstance(fc_data, list):
                            timetable = parse_calendar_events(fc_data)
            except (aiohttp.ClientError, TimeoutError, ValueError, json.JSONDecodeError) as err:
                _LOGGER.warning("Failed to fetch timetable calendar events: %s", err)

        return SimeStudentData(
            student=student,
            recent_grades=recent_grades,
            subjects=subjects,
            general_average=general_avg,
            absence_summary=absence_summary,
            homework=homework,
            timetable=timetable,
        )
