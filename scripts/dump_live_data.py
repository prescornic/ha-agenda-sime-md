"""Dump live data from agenda.sime.md to inspect structure for dataclasses."""

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-MD,ro;q=0.9,en-US;q=0.8",
}


async def get_authenticated_page(session: aiohttp.ClientSession | None = None):
    if session is None:
        session = aiohttp.ClientSession(headers=HEADERS)

    # Public
    async with session.get(f"{BASE_URL}/ords/r/agenda/main/public") as r:
        soup = BeautifulSoup(await r.text(), "html.parser")

    # Dialog
    dialog_url = None
    for a in soup.find_all("a", href=True):
        if "login_desktop" in a["href"] and "p101_user_type=1" in a["href"]:
            href = a["href"]
            start = href.find("'")
            end = href.find("'", start + 1)
            target = href[start + 1 : end].encode("utf-8").decode("unicode_escape")
            dialog_url = urllib.parse.urljoin(BASE_URL, target)
            break

    # Fetch dialog
    async with session.get(dialog_url) as r2:
        dsoup = BeautifulSoup(await r2.text(), "html.parser")
        action = dsoup.find("form")["action"]
        p_flow_id = dsoup.find("input", id="pFlowId")["value"]
        p_flow_step_id = dsoup.find("input", id="pFlowStepId")["value"]
        p_instance = dsoup.find("input", id="pInstance")["value"]
        p_page_submission_id = dsoup.find("input", id="pPageSubmissionId")["value"]
        p_reload_on_submit = dsoup.find("input", id="pReloadOnSubmit")["value"]
        p_salt = dsoup.find("input", id="pSalt")["value"]
        p_protected = dsoup.find("input", id="pPageItemsProtected")["value"]
        checksums = {inp["data-for"]: inp.get("value", "") for inp in dsoup.find_all("input", attrs={"data-for": True})}

    items_to_submit = [
        {"n": "P101_USER_TYPE", "v": "1", "ck": checksums.get("P101_USER_TYPE")},
        {"n": "P101_USER_TYPE_NAME", "v": "Autentificare părinte", "ck": checksums.get("P101_USER_TYPE_NAME")},
        {"n": "P101_USERNAME", "v": USERNAME},
        {"n": "P101_PASSWORD", "v": PASSWORD},
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

    post_url = f"{BASE_URL}/ords/{action}"
    post_headers = {
        "Referer": dialog_url,
        "Origin": BASE_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    async with session.post(post_url, data=post_payload, headers=post_headers) as resp:
        resp_json = await resp.json(content_type=None)
        match = re.search(r'atob\("([^"]+)"\)', resp_json["redirectURL"])
        target_path = base64.b64decode(match.group(1)).decode("utf-8")
        main_url = urllib.parse.urljoin(BASE_URL, target_path)

    # Now fetch main-page
    async with session.get(main_url) as r3:
        main_html = await r3.text()
        
    return main_html, main_url, session


async def main():
    html, url, _ = await get_authenticated_page()
    soup = BeautifulSoup(html, "html.parser")
    
    print("=== EXPLORING SECTIONS IN AUTHENTICATED PAGE ===")
    
    # 1. Student Info
    print("\n[1] STUDENT INFO")
    student_folder = soup.find(class_="student-folder")
    if student_folder:
        name = student_folder.find(class_="student-name")
        info = student_folder.find(class_="student-info")
        print("Student Name:", name.get_text(strip=True) if name else None)
        print("Student Info:", info.get_text(" | ", strip=True) if info else None)
        
    # 2. Subjects & Teachers
    print("\n[2] SUBJECTS & TEACHERS")
    subject_table = soup.find("table", id=lambda x: x and "R546889" in x)
    if subject_table:
        for row in subject_table.find_all("tr")[1:10]:
            cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            print("  ", cols)
            
    # 3. Absences Report
    print("\n[3] ABSENCES")
    for abs_box in soup.find_all(class_=lambda c: c and "absence" in c):
        print(f"  Class: {abs_box.get('class')}")
        print("  Text:", abs_box.get_text(" ", strip=True)[:200])

    # 4. Search for Timetable / Agenda / Orar
    print("\n[4] AGENDA / TIMETABLE / TABS")
    tabs = soup.find_all(class_=lambda c: c and any(t in c for t in ["t-Tabs", "t-Region", "tab", "nav"]))
    for tab in tabs[:10]:
        t_id = tab.get("id")
        t_class = " ".join(tab.get("class", []))
        print(f"  Region/Tab id='{t_id}' class='{t_class}' text='{tab.get_text(' ', strip=True)[:100]}'")
        
    # 5. Search for AJAX / Dynamic Regions
    print("\n[5] APEX AJAX REQUEST REGIONS")
    # In APEX, regions that load via AJAX have data-region-id or apex.widget or p_widget_name
    for script in soup.find_all("script"):
        if script.string and any(w in script.string for w in ["apex.widget", "apex.server", "apex.region"]):
            for line in script.string.split(";"):
                if any(w in line for w in ["apex.server.widget", "apex.server.plugin", "p_flow_step_id"]):
                    print("  AJAX call snippet:", line.strip()[:150])


if __name__ == "__main__":
    asyncio.run(main())
