"""Unit tests for the agenda_sime_md parsers."""

from bs4 import BeautifulSoup
from lib.agenda_sime_md.models import SimeAbsenceSummary, SimeSubjectGrades
from lib.agenda_sime_md.parser import (
    parse_absences_summary,
    parse_homework,
    parse_recent_grades,
    parse_semester_grades_table,
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
