# Personal Expense Tracker — Presentation & Demonstration Walkthrough

**Course:** CSC 226 — Web Database Applications (Fall 2026)  
**Instructor:** Professor Joseph Tooker  
**Author:** Samuel Hernandez  
**Project:** Personal Expense Tracker  
**Estimated Presentation Duration:** 3–4 Minutes  

---

## 1. Presentation Overview & Objectives

This walkthrough script is designed for live demonstration and grading evaluation of the Personal Expense Tracker. It systematically showcases the three core pillars of the CSC 226 grading rubric:

1. **Database Design (20%):** 3NF normalized schema, relational constraints, foreign keys, and indexes.
2. **User Interface Design (10%):** Accessible custom CSS design tokens, WCAG 2.2 AA compliance, interactive feedback, and data visualization.
3. **Full-Stack Integration, Security & Auth (20%):** Django MVT architecture, session auth, PBKDF2 hashing, row-level data isolation, and parameterized raw SQL queries.

---

## 2. Pre-Demo Setup Checklist

Before initiating the presentation, ensure the development environment and database are active:

```bash
# 1. Activate Python virtual environment
source .venv/bin/activate

# 2. Verify local MySQL server is running on 127.0.0.1:3306
mysql -u root -p -e "SELECT VERSION();"

# 3. Start local development server
python manage.py runserver
```

Open a web browser and navigate to:  
`http://127.0.0.1:8000/`

---

## 3. Step-by-Step Demonstration Script

### Segment 1: User Registration & Authentication (0:00 – 0:45)
*Rubric Focus: User Authentication, PBKDF2 Password Hashing, Session Management*

1. **Visit Login Page:**
   - Navigate directly to `http://127.0.0.1:8000/login/`.
   - Attempt to access a protected route directly by typing `http://127.0.0.1:8000/dashboard/` into the URL bar.
   - *Key Talking Point:* Notice that Django's `@login_required` middleware intercepts unauthenticated access, automatically redirecting to `/login/?next=/dashboard/` to prevent unauthorized entry.

2. **Register a New Account:**
   - Click **Register** (`http://127.0.0.1:8000/register/`).
   - Enter:
     - **Username:** `demo_user`
     - **Password:** `DemoPass123!`
     - **Confirm Password:** `DemoPass123!`
   - Click **Create Account**.
   - *Key Talking Point:* The system creates the user using an atomic database transaction. The password is never stored in plaintext—it is hashed using PBKDF2 with a SHA-256 digest and 870,000 iterations. The user is immediately authenticated with a secure HTTP-only session cookie and redirected to their personal dashboard.

3. **Inspect Initial Zero-State Dashboard:**
   - The dashboard opens showing:
     - **Total Spent This Month:** `$0.00` (0 transactions recorded)
     - **Monthly Budget Benchmark:** `$1,000.00`
     - **Budget Remaining:** `$1,000.00` (0.0% of budget consumed)
     - **Budget Progress Bar:** 0% width, aria-valuenow="0.0"
     - Clean empty-state prompt: *"No spending recorded for [Current Month]"*
   - *Key Talking Point:* In the zero-state, client-side Chart.js scripts are conditionally suppressed, eliminating unnecessary network bandwidth and rendering a clean, welcoming onboarding state.

---

### Segment 2: Adding Expenses & Dynamic Budget Pacing (0:45 – 1:45)
*Rubric Focus: Form Validation, Decimal Accuracy, Parameterized SQL Aggregation, WCAG Progress Bar, Chart.js Visualization*

1. **Navigate to Expense Entry Form:**
   - Click **+ Add Expense** in the header or dashboard card.
   - *Key Talking Point:* The form enforces strict client-side HTML5 validation (`required`, `step="0.01"`, `min="0.01"`, `max="999999.99"`) paired with server-side validation in `TransactionForm`. All input fields are explicitly linked to `<label>` tags with accessible error containers (`aria-describedby`).

2. **Log Three Diverse Transactions:**
   - **Transaction 1 (Food):**
     - Amount: `150.00`
     - Category: `Food` (Red `#FF5733`)
     - Date: Today
     - Note: `Weekly grocery shopping`
     - Click **Save Expense** (notice submit button loading spinner and double-submit prevention).
   - **Transaction 2 (Transport):**
     - Click **+ Add Expense**.
     - Amount: `100.00`
     - Category: `Transport` (Blue `#33A8FF`)
     - Date: Today
     - Note: `Monthly metro transit pass`
     - Click **Save Expense**.
   - **Transaction 3 (Housing - Big Expense):**
     - Click **+ Add Expense**.
     - Amount: `700.00`
     - Category: `Housing` (Purple `#9B59B6`)
     - Date: Today
     - Note: `Apartment rent contribution`
     - Click **Save Expense**.

3. **Examine Live Dashboard Analytics:**
   - Navigate to `/dashboard/`.
   - **Metrics Aggregation:**
     - **Total Spent:** `$950.00` (3 transactions recorded)
     - **Budget Remaining:** `$50.00` (95.0% consumed)
     - *Key Talking Point:* This calculation is executed via raw parameterized SQL (`tracker/queries.py` -> `get_monthly_spending_summary` and `get_monthly_category_breakdown`) using `connection.cursor()` with parameter binding (`%s`).
   - **Budget Progress Indicator:**
     - Progress bar is at 95.0% width.
     - Progress bar color dynamically transitioned from normal primary blue to warning/danger red (`et-progress__bar--danger`) because consumption exceeded 90%.
     - Full accessibility metadata: `role="progressbar"`, `aria-valuenow="95.0"`, `aria-valuemin="0"`, `aria-valuemax="100"`.
   - **Interactive Spending Breakdown Chart:**
     - The dashboard displays both a structured data table and an interactive Chart.js horizontal bar chart.
     - Hover over each bar to see formatted currency tooltips (`Spent: $700.00`, `Spent: $150.00`, `Spent: $100.00`), with detailed percentage shares displayed in the adjacent table.
     - *Key Talking Point:* Chart.js is loaded via CDN with Subresource Integrity (`integrity="sha256-..."`). Data is embedded safely via Django's `json_script` tag, completely eliminating XSS vulnerabilities. The chart is tied to the table via `aria-describedby="categoryBreakdownTable"` for complete screen reader accessibility.

---

### Segment 3: Transaction History, Multi-Param Filtering & Safe Deletion (1:45 – 2:30)
*Rubric Focus: Relational Querying, Pagination, Ownership Security (IDOR Defense)*

1. **Open Transaction History:**
   - Click **History** in the navigation bar (`http://127.0.0.1:8000/history/`).
   - The table lists all 3 transactions ordered newest-first with category color badges, formatted currency values, and action controls.

2. **Demonstrate Filtering & Search:**
   - **Filter by Category:** Select **Food** from the category dropdown -> click **Apply Filter**.
     - *Result:* Only the $150.00 grocery expense is displayed.
   - **Clear and Search by Keyword:** Click **Reset** (or select "All Categories"), enter `metro` into the search box -> click **Apply Filter**.
     - *Result:* Only the Transport transaction with note matching "metro" is returned.
     - *Key Talking Point:* The SQL query utilizes Django's `connection.ops.prep_for_like_query()` to sanitize wildcards (`%` and `_`) and applies `ESCAPE '\'` safely across SQLite and MySQL backends.
   - **Reset View:** Click **Reset** to return to the full unsegmented history.

3. **Demonstrate Safe Deletion:**
   - On the `Transport` row ($100.00), click the **Delete** button.
   - A modal confirmation prompt prevents accidental deletion.
   - Confirm deletion.
   - *Key Talking Point:* Deletion is strictly POST-only (`delete_transaction_view` rejects GET with HTTP 405) and enforces ownership: `Transaction.objects.get(id=pk, user=request.user)`. If an attacker attempts to delete another user's transaction by ID, the system returns HTTP 404, preventing Insecure Direct Object References (IDOR).
   - Return to the **Dashboard**: Total spend automatically adjusts down to `$850.00` (85.0%), and the progress bar reflects the updated budget state immediately.

---

### Segment 4: Code & Database Architecture Walkthrough (2:30 – 3:30)
*Rubric Focus: Relational Schema, Raw SQL Execution, Code Craftsmanship*

1. **Database Schema (`schema.sql`):**
   - Open `schema.sql`:
     - Highlight 3NF design: separate `tracker_category` lookup table and `tracker_transaction` table.
     - Highlight constraints:
       - `fk_tx_user FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE`
       - `fk_tx_category FOREIGN KEY (category_id) REFERENCES tracker_category(id) ON DELETE RESTRICT` (preventing orphan records)
       - `chk_amount_pos CHECK (amount > 0.00 AND amount <= 999999.99)`
       - `INDEX idx_tx_user_date (user_id, tx_date)` for query performance.

2. **Raw SQL Query Engine (`tracker/queries.py`):**
   - Open `tracker/queries.py`:
     - Point out `get_monthly_spending_summary` and `get_monthly_category_breakdown`.
     - *Key Talking Point:* Rather than relying solely on the Django ORM, the core analytics are authored in pure parameterized SQL with `connection.cursor()`. This fulfills the database programming requirement while strictly neutralizing SQL injection risks.

3. **Automated Test Suite Verification:**
   - Run the automated test suite in the terminal:
     ```bash
     python -m pytest --ds=expense_tracker.settings
     ```
   - *Result:* All **61 automated tests pass** in under 9 seconds, covering model validation, view routing, auth isolation, raw SQL execution, accessibility attributes, and XSS script escaping.

---

## 4. Grading Rubric Quick Reference

| Rubric Component | Weight | Where It Is Implemented in Code |
|---|---|---|
| **Database Design** | **20%** | `schema.sql`, `tracker/models.py`, `tracker/management/commands/seed_categories.py` |
| **User Interface Design** | **10%** | `static/css/style.css`, `static/js/ui.js`, `templates/base.html`, `templates/tracker/dashboard.html` |
| **Integration, Security & Auth** | **20%** | `expense_tracker/settings.py`, `tracker/views.py`, `tracker/queries.py`, `tracker/forms.py` |
| **Total Project Grade** | **50%** | Fully tested with 61 unit and integration tests across SQLite and MySQL 8.0 |
