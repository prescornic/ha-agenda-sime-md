"""Unit tests for the agenda_sime_md parsers."""

from bs4 import BeautifulSoup

from lib.agenda_sime_md.parser import (
    parse_absences_summary,
    parse_calendar_events,
    parse_homework,
    parse_login_dialog_url,
    parse_login_form_tokens,
    parse_portal_info,
    parse_recent_grades,
    parse_semester_grades_table,
    parse_student_dashboard,
    parse_student_profile,
)

SAMPLE_PROFILE_HTML = """
<html>
<body>
<input id="P1_ELEVE_ID" value="STUDENT_ID_00000000000000000000"/>
<input id="P1_ELEVE" value="Elev Exemplar"/>
<input id="P1_BIRTH_DATE" value="01.01.2012"/>
<input id="P1_ELEVE_UK" value="UK00000000"/>
<input id="P1_CLASS_NAME" value="5A"/>
<input id="P1_INSTITUTION_NAME" value="Liceul Teoretic Exemplu"/>
<input id="P1_DIRIGINTE" value="Profesor Diriginte"/>
<input id="P1_ADDRESS" value="Strada Exemplu 10"/>
<input id="P1_STUDY_YEAR" value="2026"/>
<input id="P1_SEMESTER_ID" value="1"/>
</body>
</html>
"""

SAMPLE_RECENT_EVAL = """
<ul id="last3-eval">
  <li><span class="eval-date">01.10.2026</span> <span class="eval-discipline">Limba și literatura română:</span> <span class="grade">8</span></li>
  <li><span class="eval-date">02.10.2026</span> <span class="eval-discipline">Limba engleză:</span> <span class="grade">9</span></li>
  <li><span class="eval-date">03.10.2026</span> <span class="eval-discipline">Biologie:</span> <span class="grade">10</span></li>
</ul>
"""

SAMPLE_SEMESTER_REPORT = """
<div id="report_sem1">
  <table class="t-Report-report" id="report_table_sem1">
    <thead>
      <tr>
        <th id="DISCIPLINA">Disciplina</th>
        <th id="LISTA_EVALUATION1">Lista notelor</th>
        <th id="MED_SEM1">Media semestrială</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td headers="DISCIPLINA">Biologie</td>
        <td headers="LISTA_EVALUATION1">9, 10</td>
        <td headers="MED_SEM1">9.5</td>
      </tr>
      <tr>
        <td headers="DISCIPLINA">Fizica</td>
        <td headers="LISTA_EVALUATION1">7, 9</td>
        <td headers="MED_SEM1"></td>
      </tr>
    </tbody>
  </table>
</div>
"""

SAMPLE_HOMEWORK = """
<ul id="homework_list">
  <b>15.10.2026</b>
  <li><span>Biologie:</span> <span>Exercițiul 1 și 2 pagina 10</span></li>
  <li><span>Educație muzicală:</span> <span>Repetare cantec</span></li>
</ul>
"""

SAMPLE_ABSENCES_HTML = """
<html>
<body>
<input id="P1_PRESENCE_PERCENT" value="100"/>
<input id="P1_MOTIVATED" value="2"/>
<input id="P1_UNMOTIVATED" value="1"/>
<input id="P1_MOTIVATED2" value="0"/>
<input id="P1_UNMOTIVATED2" value="0"/>
</body>
</html>
"""


def test_parse_student_profile():
    soup = BeautifulSoup(SAMPLE_PROFILE_HTML, "html.parser")
    student = parse_student_profile(soup)
    assert student.id == "STUDENT_ID_00000000000000000000"
    assert student.name == "Elev Exemplar"
    assert student.classroom == "5A"
    assert student.permanent_code == "UK00000000"
    assert student.class_master == "Profesor Diriginte"
    assert student.school_name == "Liceul Teoretic Exemplu"
    assert student.address == "Strada Exemplu 10"
    assert student.current_semester == 1


def test_parse_recent_grades():
    grades = parse_recent_grades(SAMPLE_RECENT_EVAL)
    assert len(grades) == 3
    assert grades[0].subject == "Limba și literatura română"
    assert grades[0].grade == 8.0
    assert grades[0].date_str == "01.10.2026"
    assert grades[2].subject == "Biologie"
    assert grades[2].grade == 10.0


def test_parse_semester_grades():
    subjects = parse_semester_grades_table(SAMPLE_SEMESTER_REPORT)
    assert len(subjects) == 2
    assert "Biologie" in subjects
    bio = subjects["Biologie"]
    assert bio.grades == [9.0, 10.0]
    assert bio.average == 9.5
    assert bio.semester_grade == 9.5

    fiz = subjects["Fizica"]
    assert fiz.grades == [7.0, 9.0]
    assert fiz.average == 8.0
    assert fiz.semester_grade is None


def test_parse_homework():
    tasks = parse_homework(SAMPLE_HOMEWORK)
    assert len(tasks) == 2
    assert tasks[0].due_date_str == "15.10.2026"
    assert tasks[0].subject == "Biologie"
    assert "Exercițiul" in tasks[0].description
    assert tasks[1].subject == "Educație muzicală"


def test_parse_absences():
    soup = BeautifulSoup(SAMPLE_ABSENCES_HTML, "html.parser")
    summary = parse_absences_summary(soup)
    assert summary.presence_percent == 100
    assert summary.sem1_motivated == 2
    assert summary.sem1_unmotivated == 1
    assert summary.total_motivated == 2
    assert summary.total_unmotivated == 1
    assert summary.total == 3


def test_parse_calendar_events():
    events_raw = [
        {
            "start": "2026-10-15T09:00:00",
            "end": "2026-10-15T09:45:00",
            "allDay": False,
            "title": (
                '<div class="lesson-card">'
                '<div class="lesson-left">'
                '<div class="lesson-order">2</div>'
                '<div class="lesson-time"><span>09:00</span><span>09:45</span></div>'
                "</div>"
                '<div class="lesson-right">'
                '<div class="lesson-line1">'
                '<span class="lesson-text-wrap">Matematică</span>'
                '<span class="lesson-room">101</span>'
                "</div>"
                '<div class="lesson-line2"><span class="lesson-teacher">Profesor Exemplu</span></div>'
                '<div class="lesson-line3"><span class="lesson-homework">Exercițiile 1-5 pag 20</span></div>'
                "</div></div>"
            ),
            "url": (
                "javascript:apex.theme42.dialog("
                "'\\u002Fords\\u002Fr\\u002Fagenda\\u002Fmain\\u002Fcalendar-info?"
                "p19_orar_id=ORAR0000000001\\u0026p19_lesson_date=15.10.2026"
                "\\u0026session=0000000000000\\u0026cs=ANON_CHECKSUM',"
                "{title:'Detalii'},'','#orar_calendar_calendar')"
            ),
        }
    ]

    lessons = parse_calendar_events(events_raw)
    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.id == "ORAR0000000001_15.10.2026"
    assert lesson.subject == "Matematică"
    assert lesson.classroom == "101"
    assert lesson.teacher == "Profesor Exemplu"
    assert lesson.topic == "Exercițiile 1-5 pag 20"
    assert lesson.start_time.hour == 9
    assert lesson.start_time.minute == 0
    assert lesson.end_time.hour == 9
    assert lesson.end_time.minute == 45
    assert lesson.start_time.tzinfo is not None


def test_parse_login_dialog_url():
    html = """
    <div>
        <a href="javascript:apex.theme42.dialog('login_desktop?p101_user_type=P&session=123',{})">Parent Login</a>
        <a href="javascript:apex.theme42.dialog('login_desktop?p101_user_type=E&session=123',{})">Student Login</a>
    </div>
    """
    url_p = parse_login_dialog_url(html, "P")
    assert url_p == "https://agenda.sime.md/login_desktop?p101_user_type=P&session=123"

    url_e = parse_login_dialog_url(html, "E")
    assert url_e == "https://agenda.sime.md/login_desktop?p101_user_type=E&session=123"

    assert parse_login_dialog_url(html, "UNKNOWN") is None
    assert parse_login_dialog_url("", "P") is None


def test_parse_login_form_tokens():
    html = """
    <form action="wwv_flow.accept">
        <input id="pFlowId" value="100"/>
        <input id="pFlowStepId" value="101"/>
        <input id="pInstance" value="12345"/>
        <input id="pPageSubmissionId" value="67890"/>
        <input id="pReloadOnSubmit" value="S"/>
        <input id="pSalt" value="99999"/>
        <input id="pPageItemsProtected" value="ENCRYPTED_PROTECTED"/>
        <input data-for="P101_USERNAME" value="CK_USER"/>
    </form>
    """
    tokens = parse_login_form_tokens(html)
    assert tokens["action"] == "wwv_flow.accept"
    assert tokens["p_flow_id"] == "100"
    assert tokens["p_flow_step_id"] == "101"
    assert tokens["p_instance"] == "12345"
    assert tokens["salt"] == "99999"
    assert tokens["protected"] == "ENCRYPTED_PROTECTED"
    assert tokens["checksums"]["P101_USERNAME"] == "CK_USER"


def test_parse_portal_info():
    html = f"""
    <html>
    <body>
        {SAMPLE_PROFILE_HTML}
        <ul id="t_TreeNav">
            <li data-current="true"><a href="f?p=100:1:0::::user_eleve_id=ST1">Elev 1</a></li>
            <li><a href="f?p=100:1:0::::user_eleve_id=ST2">Elev 2</a></li>
        </ul>
    </body>
    </html>
    """
    portal_info = parse_portal_info(html)
    assert portal_info.p1_id == "STUDENT_ID_00000000000000000000"
    assert portal_info.has_tree_nav is True
    assert len(portal_info.student_links) == 2
    assert portal_info.student_links[0][0] == "ST1"
    assert portal_info.student_links[0][3] is True  # is_current
    assert portal_info.student_links[1][0] == "ST2"
    assert portal_info.student_links[1][3] is False


def test_parse_student_dashboard():
    html = f"""
    <html>
    <body>
        {SAMPLE_PROFILE_HTML}
        <input id="P1_LAST_3_EVAL_LIST" value='{SAMPLE_RECENT_EVAL}'/>
        <input id="P1_HOMEWORK" value='{SAMPLE_HOMEWORK}'/>
        {SAMPLE_ABSENCES_HTML}
        <input data-for="P1_ELEVE_ID" value="CK_ELEVE_VAL"/>
        <input id="pSalt" value="SALT123"/>
        <input id="pPageItemsProtected" value="PROT123"/>
        <script>
            apex.widget.report.init("sem1","AJAX_SEM1",{{"pageItems":"#P1_ELEVE_ID","lazyLoading":true,"internalRegionId":"REG_SEM1"}});
        </script>
    </body>
    </html>
    """
    dash = parse_student_dashboard(html)
    assert dash.student.id == "STUDENT_ID_00000000000000000000"
    assert dash.eleve_ck == "CK_ELEVE_VAL"
    assert dash.salt == "SALT123"
    assert dash.protected == "PROT123"
    assert "sem1" in dash.sem_ajax_configs
    assert dash.sem_ajax_configs["sem1"] == ("AJAX_SEM1", "REG_SEM1")
    assert dash.absence_summary.total == 3
