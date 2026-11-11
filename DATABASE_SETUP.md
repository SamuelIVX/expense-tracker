# Expense‑Tracker – Development & Database Setup

A quick‑start guide for anyone joining the project. It works whether you run the app locally **or** inside Docker.

---

## ✅ What's already set up

The following are **already configured** in the codebase — no action needed:

- **`python-dotenv`** is in `requirements.txt` and `load_dotenv()` is called at the top of `settings.py`
- **`SECRET_KEY`** is read from the environment; auto-generates in DEBUG mode, raises an error in production
- **Database config** reads `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` from environment variables
- **Multi-engine support** — set `DB_ENGINE=sqlite` for SQLite or `DB_ENGINE=mysql` (default) for MySQL
- **`.env.example`** exists with all required variable names and a secret-key generation comment
- **`.env`** is listed in `.gitignore`
- **`schema.sql`** contains reference DDL for MySQL Workbench; use Django migrations to initialize the app
- **`STATIC_ROOT`** is configured for collected static files
- **`docker-compose.yml`** and **`Dockerfile`** are included for containerized local setup

---

## 📦 Prerequisites

| Tool | Install command |
|------|-----------------|
| **Python 3.14+** | `brew install python@3.14` (macOS) or `sudo apt-get install python3` |
| **Docker & Docker Compose** *(optional but recommended)* | Follow Docker's official installer for your OS |

> The project uses **PyMySQL** as the MySQL driver, so no native MySQL client libraries are needed.

---

## 1️⃣ Quick onboarding checklist

### Option A — Docker (recommended, zero MySQL install)

1. **Clone the repo**
   ```bash
   git clone https://github.com/SamuelIVX/expense-tracker.git
   cd expense-tracker
   ```

2. **Create your local `.env` file**
   ```bash
   cp .env.example .env
   ```
   Then generate a secret key and paste it (works without Django installed):
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
   Run the command twice more to generate separate app-database and MySQL root passwords.
   Edit `.env` and set:
   - `SECRET_KEY=<the value you just generated>`
   - `DB_HOST=db` (the Docker service name)
   - `DB_USER=et_user`
   - `DB_PASSWORD=<a separately generated database password>`
   - `MYSQL_ROOT_PASSWORD=<a separately generated root password>`

   Compose requires both database passwords to be nonempty. It reads them from your ignored `.env`; no database passwords are supplied in the tracked Compose file.

3. **Start everything**
   ```bash
   docker compose up -d
   ```
   Docker will build the app image, create an empty MySQL database, and launch the Django dev server after an authenticated TCP database healthcheck succeeds. Initialize the tables in the next step before opening the app.

4. **Run migrations & seed categories**
   ```bash
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_categories
   ```

5. **Verify** — Open `http://localhost:8000`. Register a new account and confirm you can add transactions.

### Option B — Local MySQL (no Docker)

1. **Clone the repo**
   ```bash
   git clone https://github.com/SamuelIVX/expense-tracker.git
   cd expense-tracker
   ```

2. **Create a virtual environment & install Python deps**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create your local `.env` file**
   ```bash
   cp .env.example .env
   ```
   Then generate a secret key and paste it (works without Django installed):
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
   Edit `.env` and set:
   - `SECRET_KEY=<the value you just generated>`
   - `DB_HOST=127.0.0.1`
   - `DB_USER=root` (or your MySQL user)
   - `DB_PASSWORD=<your MySQL password>`

4. **Set up the database**
   ```bash
   mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS expense_tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   python manage.py migrate
   python manage.py seed_categories
   ```

5. **Launch the development server**
   ```bash
   python manage.py runserver
   ```
   > `python-dotenv` automatically loads `.env` — no need to `source` it.

6. **Verify** — Open `http://localhost:8000`. Register a new account and confirm you can add transactions.

---

## 2️⃣ Docker reference

### Starting & stopping

```bash
docker compose up -d          # start MySQL + Django in the background
docker compose logs -f web    # tail the Django logs
docker compose down           # stop containers (data preserved)
```

### Resetting the database

```bash
docker compose down -v        # ⚠️ deletes ALL data in the db_data volume
docker compose up -d          # re-creates the empty database
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_categories
```

### Running Django commands inside the container

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_categories
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py test
```

### DB_HOST context

| Where Django runs | `DB_HOST` value |
|-------------------|-----------------|
| Inside Docker (`docker compose up web`) | `db` (the service name) |
| On the host (`python manage.py runserver`) | `127.0.0.1` |

---

## 3️⃣ SQLite fallback (quick local testing)

If you don't want MySQL at all, set this in your `.env`:

```dotenv
DB_ENGINE=sqlite
```

Django will use `db.sqlite3` in the project root. No Docker or MySQL needed.

---

## 4️⃣ Railway deployment

> **Status:** Not yet configured. See the separate deployment readiness plan for details.

---

## 5️⃣ Hygiene & gotchas

- **`.env` must never be committed** — it's already in `.gitignore`.
- **Port clash** — the Docker compose file publishes MySQL on host port 3306. Stop any local MySQL or change the port mapping.
- **Persistent data** — stopping the stack preserves the database volume. Run migrations after pulling changes. Use `docker compose down -v` only when you intend to delete all local database data.
- **`schema.sql` vs migrations** — Django migrations are the canonical source of truth. Do not import the reference SQL before migrations: it requires Django's `auth_user` table and does not record migration history. Compose deliberately leaves schema creation to `migrate`.
- **Local use only** — both published ports bind to `127.0.0.1`. The Django dev server is for local testing, not deployment. Keep generated database passwords only in your ignored `.env`.
- **Existing volumes** — MySQL only creates the configured database and users on first initialization. Editing `.env` passwords does not update existing MySQL accounts; update those accounts to match before restarting. A disposable database can instead be reset using the commands above; back up any data you need first.
