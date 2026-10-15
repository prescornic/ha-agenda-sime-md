"""Diagnostic script to explore agenda.sime.md authentication flows."""

import asyncio
import base64
import json
import os
import re
import urllib.parse

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://agenda.sime.md"
USERNAME = os.getenv("SIME_USERNAME")
PASSWORD = os.getenv("SIME_PASSWORD")
USERNAME_STUDENT = os.getenv("SIME_USERNAME_STUDENT")
PASSWORD_STUDENT = os.getenv("SIME_PASSWORD_STUDENT")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-MD,ro;q=0.9,en-US;q=0.8",
}


async def login(session: aiohttp.ClientSession, username: str, password: str, user_type: str = "1"):
    """Perform Oracle APEX login for parent (user_type=1) or student (user_type=2)."""
    role_name = "Parent" if user_type == "1" else "Student"
    user_type_name = "Autentificare părinte" if user_type == "1" else "Autentificare elev"
    print("\n=======================================================")
    print(f"AUTHENTICATING AS {role_name.upper()}: {username}")
    print("=======================================================")

    # Step 1: Fetch public portal page
    async with session.get(f"{BASE_URL}/ords/r/agenda/main/public") as r:
        public_html = await r.text()
        soup = BeautifulSoup(public_html, "html.parser")

    # Step 2: Extract modal dialog URL
    dialog_url = None
    pattern = f"p101_user_type={user_type}"
    for a in soup.find_all("a", href=True):
        if "login_desktop" in a["href"] and pattern in a["href"]:
            href = a["href"]
            start = href.find("'")
            end = href.find("'", start + 1)
            target = href[start + 1 : end].encode("utf-8").decode("unicode_escape")
            dialog_url = urllib.parse.urljoin(BASE_URL, target)
            break

    if not dialog_url:
        raise RuntimeError(f"Could not find login dialog link for {role_name}")

    print(f"Found {role_name} Dialog URL: {dialog_url}")

    # Step 3: Fetch modal dialog page
    async with session.get(dialog_url) as r2:
        dialog_html = await r2.text()
        dsoup = BeautifulSoup(dialog_html, "html.parser")

        form = dsoup.find("form")
        if not form:
            raise RuntimeError("Dialog did not contain wwvFlowForm")

        action = form.get("action")
        p_flow_id = dsoup.find("input", id="pFlowId")["value"]
        p_flow_step_id = dsoup.find("input", id="pFlowStepId")["value"]
        p_instance = dsoup.find("input", id="pInstance")["value"]
        p_page_submission_id = dsoup.find("input", id="pPageSubmissionId")["value"]
        p_reload_on_submit = dsoup.find("input", id="pReloadOnSubmit")["value"]
        p_salt = dsoup.find("input", id="pSalt")["value"]
        p_protected = dsoup.find("input", id="pPageItemsProtected")["value"]

        # Collect checksums from data-for attributes
        checksums = {}
        for inp in dsoup.find_all("input", attrs={"data-for": True}):
            checksums[inp["data-for"]] = inp.get("value", "")

    # Step 4: Construct APEX 23.2 p_json payload
    items_to_submit = [
        {"n": "P101_USER_TYPE", "v": user_type, "ck": checksums.get("P101_USER_TYPE")},
        {"n": "P101_USER_TYPE_NAME", "v": user_type_name, "ck": checksums.get("P101_USER_TYPE_NAME")},
        {"n": "P101_USERNAME", "v": username},
        {"n": "P101_PASSWORD", "v": password},
    ]

    r_obj = {
        "salt": p_salt,
        "pageItems": {
            "itemsToSubmit": items_to_submit,
            "protected": p_protected,
            "rowVersion": "",
            "formRegionChecksums": [],
        },
    }

    post_payload = {
        "p_flow_id": p_flow_id,
        "p_flow_step_id": p_flow_step_id,
        "p_instance": p_instance,
        "p_page_submission_id": p_page_submission_id,
        "p_request": "LOGIN",
        "p_reload_on_submit": p_reload_on_submit,
        "p_json": json.dumps(r_obj),
    }

    post_headers = {
        "Referer": dialog_url,
        "Origin": BASE_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    post_url = f"{BASE_URL}/ords/{action}"
    print(f"Submitting APEX login to: {post_url}")

    async with session.post(post_url, data=post_payload, headers=post_headers) as resp:
        print(f"Login POST status: {resp.status}")
        resp_json = await resp.json(content_type=None)
        print("Login response:", resp_json)

        redirect_script = resp_json.get("redirectURL", "")
        # Look for atob("...") in redirect script
        match = re.search(r'atob\("([^"]+)"\)', redirect_script)
        if not match:
            # Check for error or throttle
            if "notification_msg=" in redirect_script:
                msg_match = re.search(r'notification_msg=([^&"]+)', redirect_script)
                if msg_match:
                    raw_msg = msg_match.group(1).split("%2F")[0]
                    try:
                        decoded_msg = base64.b64decode(raw_msg + "==").decode("utf-8", errors="ignore")
                        print(f"ALERT / ERROR MESSAGE: {decoded_msg}")
                    except (ValueError, TypeError) as e:
                        print("Failed to decode message:", e)
            raise RuntimeError(f"Login did not return standard redirect URL: {redirect_script}")

        target_path = base64.b64decode(match.group(1)).decode("utf-8")
        target_url = urllib.parse.urljoin(BASE_URL, target_path)
        print(f"SUCCESS: Logged in! Redirect target: {target_url}")
        return target_url


async def inspect_portal(session: aiohttp.ClientSession, url: str):
    """Fetch and inspect logged-in portal page."""
    print("\n=======================================================")
    print(f"INSPECTING PORTAL PAGE: {url}")
    print("=======================================================")
    async with session.get(url) as resp:
        print(f"Status: {resp.status}")
        print(f"Final URL: {resp.url}")
        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string if soup.title else "No title"
        print(f"Page Title: {title}")

        print("\n--- Main Headings ---")
        for h in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = h.get_text(strip=True)
            if text:
                print(f"  [{h.name}] {text}")

        print("\n--- Navigation & Links ---")
        found_links = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if href.startswith(("javascript:", "#")):
                continue
            key = (text, href)
            if key not in found_links:
                found_links.add(key)
                print(f"  Link: text='{text}' href='{href}'")

        print("\n--- Tables / Data Grids ---")
        for table in soup.find_all("table"):
            table_id = table.get("id", "no-id")
            table_class = " ".join(table.get("class", []))
            headers = [th.get_text(strip=True) for th in table.find_all("th") if th.get_text(strip=True)]
            print(f"  Table id='{table_id}' class='{table_class}' headers={headers[:8]}")

        print("\n--- Interactive Grid / Reports / Cards ---")
        for elem in soup.find_all(class_=lambda c: c and any(x in c for x in ["a-Card", "t-Cards", "report", "ig-grid", "student", "elev"])):
            print(f"  Card/Report: tag={elem.name} class='{' '.join(elem.get('class', []))}' text='{elem.get_text(strip=True)[:100]}'")

        return html, soup


async def main():
    # 1. Test Parent Login
    if USERNAME and PASSWORD:
        async with aiohttp.ClientSession(headers=HEADERS) as session_parent:
            try:
                portal_url = await login(session_parent, USERNAME, PASSWORD, user_type="1")
                await inspect_portal(session_parent, portal_url)
            except (aiohttp.ClientError, RuntimeError) as e:
                print(f"Parent login test failed: {e}")

    # 2. Test Student Login
    if USERNAME_STUDENT and PASSWORD_STUDENT:
        async with aiohttp.ClientSession(headers=HEADERS) as session_student:
            try:
                portal_url = await login(session_student, USERNAME_STUDENT, PASSWORD_STUDENT, user_type="2")
                await inspect_portal(session_student, portal_url)
            except (aiohttp.ClientError, RuntimeError) as e:
                print(f"Student login test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
