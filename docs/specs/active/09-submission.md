# Spec: Submission

## Applicable Skills
- `better-writing`: Professional, concise technical documentation; clear presentation scripting; accurate rubric attribution.

## Objective
Package the final coursework deliverable for CSC 226: prepare the production-ready root `README.md`,
author the `WALKTHROUGH.md` demo script for the group presentation, verify the full test and setup
sequence from a clean clone, and document the rubric mapping against Professor Tooker's grading breakdown
(20% Database Design, 10% UI Design, 20% Integration & Security).

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `README.md` (project root submission README)
  - `WALKTHROUGH.md` (step-by-step presentation and demo script)
- Off-limits: source code and templates (frozen at spec 07/08).

## Non-Goals
- No new features or refactors.
- No cloud deployment (local execution against MySQL Workbench meets course guidelines).

## Requirements

### Root `README.md`
1. THE SYSTEM SHALL provide a clean root `README.md` containing:
   - **Project Overview:** Purpose of the personal expense tracker and problem it solves.
   - **Team Members & Roles:** Group members and contribution breakdown.
   - **Tech Stack:** Python 3 + Django 5, MySQL (Workbench), vanilla HTML5/CSS/JavaScript.
   - **Setup Guide:** Clear step-by-step setup commands from fresh clone:
     ```bash
     git clone <repo-url>
     cd expense-tracker
     python3 -m venv .venv
     source .venv/bin/activate  # (or .\.venv\Scripts\activate on Windows)
     pip install -r requirements.txt
     cp .env.example .env
     # Populate MySQL credentials in .env
     mysql -u root -p < schema.sql
     python manage.py migrate
     python manage.py runserver
     ```
   - **Course Rubric Mapping:** Explicitly mapping project components to Professor Tooker's 50% project grade:
     - **Database Design (20%):** 3NF normalization, foreign keys, constraints, and `schema.sql`.
     - **UI Design (10%):** Custom CSS design tokens, WCAG AA contrast, loading states, progress bars, transitions.
     - **Integration & Security (20%):** Django MVT architecture, PBKDF2 auth, CSRF tokens, parameterized queries via `connection.cursor()`.
   - **Feature Checklist:** Accurate list of implemented features with `[x]` marks.

### `WALKTHROUGH.md`
2. THE SYSTEM SHALL provide a step-by-step 3-minute presentation script (`WALKTHROUGH.md`) covering:
   - Registration of a new test user (`demo_user`)
   - Logging in and viewing the initial zero-state dashboard
   - Recording 3 transactions across different categories (`Food`, `Transport`, `Housing`)
   - Observing the budget progress bar transition from blue to amber/red
   - Viewing and filtering transaction history by category and month
   - Demonstrating safe transaction deletion
   - Inspecting the `schema.sql` and raw SQL queries in `views.py`

## Acceptance Criteria
- [ ] Fresh clone in a temporary directory runs cleanly following the README steps.
- [ ] `schema.sql` runs in MySQL Workbench without errors.
- [ ] All rubric requirements are explicitly documented with links to source files.
- [ ] `WALKTHROUGH.md` covers all grading points in under 5 minutes.
