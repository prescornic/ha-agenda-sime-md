# Agenda SIME MD — Home Assistant Integration

<p align="center">
  <img src="images/icon.png" width="120" alt="Agenda SIME MD Logo">
</p>

<p align="center">
  <strong>Integrare Home Assistant (HACS) pentru Catalogul Electronic Școlar din Republica Moldova (<a href="https://agenda.sime.md">agenda.sime.md</a>).</strong>
</p>

<p align="center">
  <a href="https://github.com/hacs/default"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS Custom"></a>
  <a href="https://github.com/prescornic/ha-agenda-sime-md/actions/workflows/validate.yml"><img src="https://github.com/prescornic/ha-agenda-sime-md/actions/workflows/validate.yml/badge.svg" alt="Validate"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
</p>

---

## 🌟 Funcționalități Principale (Key Features)

Această integrare aduce catalogul școlar SIME direct în tabloul de bord Home Assistant pentru părinți și elevi:

- 📊 **Note & Medii (Grades & Averages):**
  - Ultima notă primită (`sensor.<elev>_last_grade`), cu detalii despre materie, profesor, temă și dată în atribute.
  - Media generală a elevului (`sensor.<elev>_general_average`).
  - Medii pe fiecare disciplină școlară (`sensor.<elev>_<disciplina>_average`).
- 🚨 **Absențe & Alerte în Timp Real (Attendance & Live Alerts):**
  - Contor total absențe (`sensor.<elev>_absences`) cu clasificare motivate / nemotivate.
  - Senzor binar `binary_sensor.<elev>_absence_today`: se activează instant (`on`) dacă este înregistrată o absență în ziua curentă (ideal pentru notificări mobile rapide).
- 📅 **Orar Școlar (Timetable Calendar):**
  - Calendar nativ HA (`calendar.<elev>_timetable`) cu orarul lecțiilor pe zile, sala de clasă și profesorul.
- 📝 **Teme pentru Acasă (Homework To-Do):**
  - Listă nativă HA To-Do (`todo.<elev>_homework`) cu temele active, descrierea cerințelor și termenele limită.
- ⚡ **Sondare Inteligentă & Adaptivă (Adaptive Polling):**
  - **Ziua (07:00 – 19:00):** Actualizare frecventă (implicit 15 minute, configurabil) pentru a reflecta imediat notele și absențele primite la școală.
  - **Noaptea (19:00 – 07:00):** Actualizare relaxată (1 oră) pentru a reduce solicitarea serverelor.
- 👨‍👩‍👧‍👦 **Suport Conturi Părinte & Elev:**
  - Suportă conturi de **Părinte** (cu selectarea unuia sau mai multor elevi înrolați) și conturi de **Elev**.

---

## 📦 Instalare (Installation)

### Prin HACS (Recomandat)
1. Asigurați-vă că aveți instalat [HACS](https://hacs.xyz/).
2. În Home Assistant, navigați la **HACS** > **Integrări**.
3. Apăsați pe meniul cu trei puncte din colțul dreapta-sus > **Depozite personalizate (Custom repositories)**.
4. Adăugați URL-ul: `https://github.com/prescornic/ha-agenda-sime-md` cu categoria **Integration**.
5. Căutați **Agenda SIME MD**, apăsați **Descărcare (Download)** și reporniți Home Assistant.

---

## ⚙️ Configurare (Configuration)

1. În Home Assistant, mergeți la **Setări** > **Dispozitive și servicii** > **Adăugare integrare**.
2. Căutați **Agenda SIME MD**.
3. Introduceți **Numele de utilizator** și **Parola** de pe [agenda.sime.md](https://agenda.sime.md).
4. Dacă utilizați un cont de părinte cu mai mulți copii, selectați elevii pe care doriți să îi monitorizați.
5. Opțional, ajustați intervalul de actualizare pe timp de zi din meniul **Opțiuni**.

---

## 🔔 Exemple de Automatizări (Automations)

### Notificare instantanee pentru absență înregistrată astăzi
```yaml
alias: "Alertă: Absență înregistrată astăzi"
trigger:
  - platform: state
    entity_id: binary_sensor.elev_absence_today
    to: "on"
action:
  - service: notify.notify
    data:
      title: "⚠️ Alertă Școlară SIME"
      message: "A fost înregistrată o nouă absență pentru elev astăzi!"
```

### Notificare când se înregistrează o notă nouă
```yaml
alias: "Alertă: Notă nouă în catalog"
trigger:
  - platform: state
    entity_id: sensor.elev_last_grade
action:
  - service: notify.notify
    data:
      title: "🎓 Notă nouă: {{ trigger.to_state.state }}"
      message: >
        Disciplina: {{ trigger.to_state.attributes.subject }}
        Data: {{ trigger.to_state.attributes.date }}
        Profesor: {{ trigger.to_state.attributes.teacher }}
```

---

## 🏛️ Arhitectură & Dezvoltare (Architecture)

Codul este proiectat modular în două straturi:
- `lib/agenda_sime_md/`: Librărie asincronă independentă în Python (`aiohttp`), fără dependențe de Home Assistant, gata de extragere într-un pachet separat PyPI.
- `custom_components/agenda_sime_md/`: Componenta integrată pentru Home Assistant Core.

---

## 📄 Licență (License)

Acest proiect este licențiat sub licența MIT — consultați fișierul [LICENSE](LICENSE) pentru detalii.
