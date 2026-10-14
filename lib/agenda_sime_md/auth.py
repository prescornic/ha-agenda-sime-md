"""Authentication manager for agenda.sime.md Oracle APEX backend."""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup

from .exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeRateLimitError,
)
from .models import SimeAccountRole

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://agenda.sime.md"
PUBLIC_PORTAL_URL = f"{BASE_URL}/ords/r/agenda/main/public"


class SimeAuthManager:
    """Manages APEX session tokens, cookies, and login sequence."""

    def __init__(self, role: SimeAccountRole = SimeAccountRole.PARENT) -> None:
        self.role = role
        self.session_id: str | None = None
        self.portal_url: str | None = None
        self._authenticated: bool = False

    @property
    def is_authenticated(self) -> bool:
        """Return True if session has completed authentication."""
        return self._authenticated and self.session_id is not None

    async def login(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
    ) -> str:
        """Perform 4-step Oracle APEX authentication handshake.

        Returns:
            The authenticated portal URL.
        """
        user_type = self.role.value
        user_type_name = "Autentificare părinte" if self.role == SimeAccountRole.PARENT else "Autentificare elev"

        # Step 1: Fetch public portal
        try:
            async with session.get(PUBLIC_PORTAL_URL) as resp:
                if resp.status != 200:
                    raise SimeConnectionError(f"Failed to access {PUBLIC_PORTAL_URL}: HTTP {resp.status}")
                public_html = await resp.text()
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Network error accessing agenda.sime.md: {err}") from err

        soup = BeautifulSoup(public_html, "html.parser")

        # Step 2: Extract modal dialog URL with matching user_type
        dialog_url = None
        pattern = f"p101_user_type={user_type}"
        for a in soup.find_all("a", href=True):
            if "login_desktop" in a["href"] and pattern in a["href"]:
                href = a["href"]
                start = href.find("'")
                end = href.find("'", start + 1)
                if start != -1 and end != -1:
                    raw_target = href[start + 1 : end]
                    target = raw_target.encode("utf-8").decode("unicode_escape")
                    dialog_url = urllib.parse.urljoin(BASE_URL, target)
                    break

        if not dialog_url:
            raise SimeAuthError(f"Could not locate login dialog URL for user_type={user_type}")

        # Step 3: Fetch login modal dialog
        try:
            async with session.get(dialog_url) as resp:
                if resp.status != 200:
                    raise SimeConnectionError(f"Failed to open login dialog: HTTP {resp.status}")
                dialog_html = await resp.text()
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Network error loading login dialog: {err}") from err

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

        if not all([action, p_flow_id, p_flow_step_id, p_instance, p_page_submission_id, p_salt, p_protected]):
            raise SimeAuthError("Missing required APEX tokens in login form")

        # Map protected item checksums
        checksums = {inp["data-for"]: inp.get("value", "") for inp in dsoup.find_all("input", attrs={"data-for": True})}

        # Step 4: Construct APEX 23.2 p_json payload
        items_to_submit = [
            {"n": "P101_USER_TYPE", "v": user_type, "ck": checksums.get("P101_USER_TYPE")},
            {"n": "P101_USER_TYPE_NAME", "v": user_type_name, "ck": checksums.get("P101_USER_TYPE_NAME")},
            {"n": "P101_USERNAME", "v": username},
            {"n": "P101_PASSWORD", "v": password},
        ]

        r_obj = {
            "salt": p_salt["value"],
            "pageItems": {
                "itemsToSubmit": items_to_submit,
                "protected": p_protected["value"],
                "rowVersion": "",
                "formRegionChecksums": [],
            },
        }

        post_payload = {
            "p_flow_id": p_flow_id["value"],
            "p_flow_step_id": p_flow_step_id["value"],
            "p_instance": p_instance["value"],
            "p_page_submission_id": p_page_submission_id["value"],
            "p_request": "LOGIN",
            "p_reload_on_submit": p_reload_on_submit["value"] if p_reload_on_submit else "S",
            "p_json": json.dumps(r_obj),
        }

        post_url = f"{BASE_URL}/ords/{action}"
        post_headers = {
            "Referer": dialog_url,
            "Origin": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        try:
            async with session.post(post_url, data=post_payload, headers=post_headers) as resp:
                if resp.status != 200:
                    raise SimeAuthError(f"Login POST request rejected with HTTP {resp.status}")
                resp_json = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise SimeConnectionError(f"Network error submitting credentials: {err}") from err

        redirect_script = resp_json.get("redirectURL", "")

        # Check for rate limit / throttle notification
        if "notification_msg=" in redirect_script:
            msg_match = re.search(r"notification_msg=([^&\"]+)", redirect_script)
            error_message = "Authentication error"
            wait_sec = 60
            if msg_match:
                raw_msg = msg_match.group(1).split("%2F")[0]
                try:
                    decoded = base64.b64decode(raw_msg + "==").decode("utf-8", errors="ignore")
                    error_message = re.sub(r"<[^>]+>", " ", decoded).strip()
                    sec_match = re.search(r"([0-9]+)\s+seconds", error_message)
                    if sec_match:
                        wait_sec = int(sec_match.group(1))
                except Exception:
                    pass
            if "blocked" in error_message.lower() or "wait" in error_message.lower():
                raise SimeRateLimitError(error_message, wait_seconds=wait_sec)
            raise SimeAuthError(error_message)

        # Extract base64 redirect path
        match = re.search(r'atob\("([^"]+)"\)', redirect_script)
        if not match:
            raise SimeAuthError(f"Unexpected response from login: {redirect_script}")

        try:
            target_path = base64.b64decode(match.group(1)).decode("utf-8")
        except Exception as err:
            raise SimeAuthError(f"Failed to decode login redirect path: {err}") from err

        self.portal_url = urllib.parse.urljoin(BASE_URL, target_path)
        sess_match = re.search(r"session=([0-9]+)", self.portal_url)
        if sess_match:
            self.session_id = sess_match.group(1)
        self._authenticated = True

        _LOGGER.debug("Successfully authenticated to SIME with session ID %s", self.session_id)
        return self.portal_url
