"""Asynchronous client for agenda.sime.md."""

from __future__ import annotations

import json
import logging
import re
from typing import Self

import aiohttp
from bs4 import BeautifulSoup

from .auth import BASE_URL, SimeAuthManager
from .exceptions import SimeConnectionError
from .models import (
    SimeAccountRole,
    SimeStudent,
    SimeStudentData,
    SimeSubjectGrades,
)
from .parser import (
    get_input_value,
    parse_absences_summary,
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

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or initialize the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
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

        students = [primary_student]

        # Check for multiple children in side navigation tree
        # <a href="/ords/r/agenda/main/main-page?user_eleve_id=...&session=...">
        tree_nav = soup.find(id="t_TreeNav")
        if tree_nav:
            for a in tree_nav.find_all("a", href=True):
                href = a["href"]
                if "user_eleve_id=" in href:
                    m = re.search(r"user_eleve_id=([^&]+)", href)
                    if m:
                        student_id = m.group(1)
                        student_name = a.get_text(strip=True)
                        if student_id != primary_student.id:
                            students.append(
                                SimeStudent(
                                    id=student_id,
                                    name=student_name,
                                )
                            )

        return students

    async def get_student_data(self, student_id: str | None = None) -> SimeStudentData:
        """Fetch complete school data (grades, absences, homework) for a student."""
        session = await self._ensure_logged_in()

        target_url = self.auth.portal_url
        if student_id:
            # If a specific child is requested, switch student context if needed
            target_url = f"{self.auth.portal_url}&user_eleve_id={student_id}"

        try:
            async with session.get(target_url) as resp:
                if resp.status != 200:
                    raise SimeConnectionError(f"Failed to fetch student data: HTTP {resp.status}")
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Network error loading student dashboard: {err}") from err

        soup = BeautifulSoup(html, "html.parser")

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

        return SimeStudentData(
            student=student,
            recent_grades=recent_grades,
            subjects=subjects,
            general_average=general_avg,
            absence_summary=absence_summary,
            homework=homework,
        )
