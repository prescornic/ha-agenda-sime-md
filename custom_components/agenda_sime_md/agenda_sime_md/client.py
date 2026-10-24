"""Asynchronous client for agenda.sime.md."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Self

import aiohttp

from .auth import BASE_URL, SimeAuthManager
from .exceptions import SimeConnectionError
from .models import (
    SimeAccountRole,
    SimeLesson,
    SimePortalInfo,
    SimeStudent,
    SimeStudentDashboardData,
    SimeStudentData,
    SimeSubjectGrades,
)
from .parser import (
    parse_calendar_events,
    parse_homework,
    parse_portal_info,
    parse_recent_grades,
    parse_semester_grades_table,
    parse_student_dashboard,
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

    def invalidate_session(self) -> None:
        """Invalidate the session and clear cached URLs and cookies."""
        self.auth.invalidate()
        self._student_urls.clear()
        if self._session and not self._session.closed:
            self._session.cookie_jar.clear()

    async def login(self) -> bool:
        """Authenticate user against agenda.sime.md."""
        session = await self._get_session()
        self._student_urls.clear()
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
        portal_info: SimePortalInfo | None = None
        for attempt in range(2):
            session = await self._ensure_logged_in()

            try:
                async with session.get(self.auth.portal_url) as resp:
                    if resp.status in (401, 403, 404, 440) and attempt == 0:
                        _LOGGER.warning(
                            "SIME MD session expired (HTTP %s) accessing portal, re-authenticating...",
                            resp.status,
                        )
                        self.invalidate_session()
                        continue
                    if resp.status != 200:
                        raise SimeConnectionError(f"HTTP {resp.status} accessing portal")
                    html = await resp.text()
            except aiohttp.ClientError as err:
                if attempt == 0:
                    _LOGGER.warning("Network error accessing portal, re-authenticating: %s", err)
                    self.invalidate_session()
                    continue
                raise SimeConnectionError(f"Failed to access portal page: {err}") from err

            portal_info = await asyncio.to_thread(parse_portal_info, html)
            current_url = str(resp.url).lower()

            if (
                not portal_info.p1_id
                and not portal_info.has_tree_nav
                or "/public" in current_url
                or "login" in current_url
            ) and attempt == 0:
                _LOGGER.warning(
                    "SIME MD session expired or redirected to login, re-authenticating...",
                )
                self.invalidate_session()
                continue

            break

        if portal_info is None:
            raise SimeConnectionError("Failed to access portal page after re-authentication")

        primary_student = portal_info.primary_student
        student_links = portal_info.student_links

        students: list[SimeStudent] = []
        self._student_urls.clear()

        if student_links:
            for uid, name, href, is_current in student_links:
                full_url = urllib.parse.urljoin(BASE_URL, href)
                self._student_urls[uid] = full_url

                if is_current:
                    primary_student.id = uid
                    if portal_info.p1_id:
                        self._student_urls[portal_info.p1_id] = full_url
                    students.append(primary_student)
                else:
                    students.append(SimeStudent(id=uid, name=name))
        else:
            self._student_urls[primary_student.id] = self.auth.portal_url
            students.append(primary_student)

        return students

    async def get_student_data(self, student_id: str | None = None) -> SimeStudentData:
        """Fetch complete school data (grades, absences, homework) for a student."""
        dashboard: SimeStudentDashboardData | None = None
        html: str = ""
        session: aiohttp.ClientSession | None = None
        target_url: str | None = None

        for attempt in range(2):
            session = await self._ensure_logged_in()

            # Determine target navigation URL
            target_url = self._student_urls.get(student_id) if student_id else None
            if not target_url:
                target_url = self.auth.portal_url

            try:
                async with session.get(target_url) as resp:
                    if resp.status in (401, 403, 404, 440) and attempt == 0:
                        _LOGGER.warning(
                            "SIME MD session expired (HTTP %s) loading student dashboard, re-authenticating...",
                            resp.status,
                        )
                        self.invalidate_session()
                        continue
                    if resp.status != 200:
                        raise SimeConnectionError(
                            f"Failed to fetch student data: HTTP {resp.status}"
                        )
                    html = await resp.text()
            except aiohttp.ClientError as err:
                if attempt == 0:
                    _LOGGER.warning(
                        "Network error loading student dashboard, re-authenticating: %s", err
                    )
                    self.invalidate_session()
                    continue
                raise SimeConnectionError(
                    f"Network error loading student dashboard: {err}"
                ) from err

            dashboard = await asyncio.to_thread(parse_student_dashboard, html)
            current_url = str(resp.url).lower()

            if (
                not dashboard.p1_id
                and not dashboard.has_tree_nav
                or "/public" in current_url
                or "login" in current_url
            ) and attempt == 0:
                _LOGGER.warning(
                    "SIME MD session expired or redirected (P1_ELEVE_ID missing), re-authenticating...",
                )
                self.invalidate_session()
                continue

            break

        if dashboard is None or session is None or target_url is None:
            raise SimeConnectionError("Failed to load student dashboard after re-authentication")

        # Discover or refresh student URLs from TreeNav
        for uid, href in dashboard.student_urls:
            self._student_urls[uid] = urllib.parse.urljoin(BASE_URL, href)

        if dashboard.p1_id:
            self._student_urls[dashboard.p1_id] = target_url

        # If a specific child was requested that is not the active one, navigate to it
        if (
            student_id
            and student_id in self._student_urls
            and self._student_urls[student_id] != target_url
        ):
            target_url = self._student_urls[student_id]
            try:
                async with session.get(target_url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        dashboard = await asyncio.to_thread(parse_student_dashboard, html)
            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to navigate to student %s: %s", student_id, err)

        # 1. Student profile
        student = dashboard.student
        if student_id:
            student.id = student_id

        # 2. Parse recent grades
        recent_grades = await asyncio.to_thread(parse_recent_grades, dashboard.recent_eval_raw)

        # 3. Parse homework
        homework = await asyncio.to_thread(parse_homework, dashboard.homework_raw)

        # 4. Absences summary
        absence_summary = dashboard.absence_summary

        # 5. Fetch Semester 1 and Semester 2 grade reports
        subjects: dict[str, SimeSubjectGrades] = {}
        session_id = self.auth.session_id

        eleve_id = dashboard.eleve_id
        eleve_ck = dashboard.eleve_ck
        salt = dashboard.salt
        protected = dashboard.protected

        if session_id and eleve_id and eleve_ck:
            ajax_url = f"{BASE_URL}/ords/wwv_flow.ajax?p_context=main/main-page/{session_id}"
            ajax_headers = {
                "Referer": target_url,
                "Origin": BASE_URL,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, */*; q=0.01",
            }

            for sem_name, (ajax_id, _region_id) in dashboard.sem_ajax_configs.items():
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
                    async with session.post(
                        ajax_url, data=payload, headers=ajax_headers
                    ) as rep_resp:
                        if rep_resp.status == 200:
                            rep_html = await rep_resp.text()
                            sem_subjects = await asyncio.to_thread(
                                parse_semester_grades_table, rep_html
                            )
                            for subj_name, subj_data in sem_subjects.items():
                                if subj_name not in subjects:
                                    subjects[subj_name] = subj_data
                                else:
                                    # Merge marks across semesters
                                    subjects[subj_name].grades.extend(subj_data.grades)
                                    subjects[subj_name].average = subjects[
                                        subj_name
                                    ].calculate_average()
                except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                    _LOGGER.warning("Failed to fetch %s grades report: %s", sem_name, err)

        # 6. Calculate overall general average
        averages = [s.average for s in subjects.values() if s.average is not None]
        general_avg = round(sum(averages) / len(averages), 2) if averages else None

        # 7. Fetch Timetable / Agenda Calendar
        timetable: list[SimeLesson] = []
        fc_match = re.search(
            r"apex\.widget\.fullCalendar\(\{.*?\"ajaxIdentifier\":\"([^\"]+)\"",
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
                            timetable = await asyncio.to_thread(parse_calendar_events, fc_data)
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
