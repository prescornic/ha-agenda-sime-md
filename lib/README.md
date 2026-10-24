# agenda-sime-md

Python asynchronous client library for [agenda.sime.md](https://agenda.sime.md) — Sistemul Informațional de Management în Educație (SIME) din Republica Moldova.

## Features

- Asynchronous HTTP client built with `aiohttp` and `BeautifulSoup4`.
- Support for both **Parent** and **Student** account types.
- Automatic session management and APEX token extraction.
- Fetches student profiles, marks/grades, semester averages, absences, and homework tasks.
- Zero Home Assistant dependencies — completely pure Python library.

## Installation

```bash
pip install agenda-sime-md
```

## Quick Start

```python
import asyncio
from agenda_sime_md import SimeClient, SimeAccountRole


async def main():
    async with SimeClient("username", "password", SimeAccountRole.PARENT) as client:
        await client.login()
        students = await client.get_students()
        for student in students:
            print(f"Student: {student.name} ({student.classroom})")
            data = await client.get_student_data(student.id)
            print(f"GPA: {data.general_average}")
            for grade in data.recent_grades:
                print(f"  {grade.date_str}: {grade.subject} -> {grade.grade}")


asyncio.run(main())
```

## License

MIT License
