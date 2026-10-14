# Local Diagnostic & Exploration Scripts

This directory contains standalone Python exploration, diagnostic, and reverse engineering scripts for `agenda.sime.md`.

## Usage
Scripts in this directory load credentials automatically from the root `.env` file (`SIME_USERNAME`, `SIME_PASSWORD`, `SIME_USERNAME_STUDENT`, `SIME_PASSWORD_STUDENT`).

> **Note:** Never commit secrets or hardcoded passwords into scripts. All secrets must remain in `.env` (which is gitignored).
