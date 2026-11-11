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
- **`schema.sql`** contains the full DDL with seed categories (teammates can use this to bootstrap their DB)
- **`STATIC_ROOT`** is configured for collected static files

---

## 📦 Prerequisites

| Tool | Install command |
|------|-----------------|
| **Python 3.14+** | `brew install python@3.14` (macOS) or `sudo apt-get install python3` |
| **Docker & Docker Compose** *(optional but recommended)* | Follow Docker's official installer for your OS |
| **MySQL client libraries** (required for the `mysqlclient` Python package) | See §1 below |

---

## 1️⃣ System dependencies for the Python MySQL driver

The `mysqlclient` package needs native MySQL client libraries **before** `pip install -r requirements.txt`:

| OS | Command |
|----|---------|
| **macOS** | `brew install mysql-client pkg-config && export PKG_CONFIG_PATH="$(brew --prefix mysql-client)/lib/pkgconfig"` |
| **Ubuntu/Debian** | `sudo apt-get install libmysqlclient-dev pkg-config python3-dev build-essential` |
| **Windows** | Use the pre-built wheels from PyPI (no extra system packages required) |

> The project currently uses **PyMySQL** (`pymysql` in `requirements.txt`), so this step may not be needed unless you switch to the C-based `mysqlclient` driver.

---

## 2️⃣ Quick onboarding checklist (what every teammate should do)

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
   Then generate a secret key and paste it:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```
   Edit `.env` and set `SECRET_KEY=<the value you just generated>`. Update `DB_USER` and `DB_PASSWORD` to match your local MySQL credentials.

4. **Set up the database** — pick one approach:

   **Option A — Local MySQL (no Docker)**
   ```bash
   # Log in to your MySQL server and run the schema:
   mysql -u root -p < schema.sql
   # Then run Django migrations to create framework tables:
   python manage.py migrate
   # Seed the categories:
   python manage.py seed_categories
   ```

   **Option B — Docker** *(see §3 below for the compose file — not yet created)*
   ```bash
   docker compose up -d db
   python manage.py migrate
   python manage.py seed_categories
   ```

5. **Launch the development server**
   ```bash
   python manage.py runserver
   ```
   > `python-dotenv` automatically loads `.env` — no need to `source` it or `set -a`.

6. **Verify** — Open `http://localhost:8000`. Register a new account and confirm you can add transactions.

---

## 3️⃣ Docker Compose setup (NOT YET CREATED)

> **Status:** `docker-compose.yml` and `Dockerfile` do not exist yet. The configuration below is the target.

Create **`docker-compose.yml`** at the repo root:

```yaml
version: "3.9"

services:
  db:
    image: mysql:8.0
    container_name: expense_tracker_mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: root_pw   # change before any production use
      MYSQL_DATABASE: expense_tracker
      MYSQL_USER: et_user
      MYSQL_PASSWORD: et_pw
    volumes:
      - db_data:/var/lib/mysql
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro
    ports:
      - "3306:3306"   # will clash if you already run MySQL locally

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db

volumes:
  db_data:
```

Create **`Dockerfile`**:

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

**Notes:**
- The `env_file: .env` line makes Compose inject your variables into the `web` container.
- `schema.sql` is mounted into `/docker-entrypoint-initdb.d/` so MySQL auto-imports it on first run.
- The init script **only runs when the volume is empty**. To re-import, run `docker compose down -v && docker compose up -d db`.

> **⚠️ Warning:** `docker compose down -v` deletes **all** data in the `db_data` volume, not just the schema import.

**DB_HOST context:**
- Running Django on the host (`python manage.py runserver`): set `DB_HOST=127.0.0.1` in `.env`
- Running Django inside the Docker stack (`docker compose up web`): set `DB_HOST=db` in `.env`

---

## 4️⃣ Railway deployment (NOT YET CREATED)

> **Status:** `Procfile`, `gunicorn`, and `whitenoise` are not yet added. See the separate [railway_deployment_readiness_plan.md](file:///Users/samuelhernandez/.gemini/antigravity-cli/brain/7c41552e-9f4d-43e0-b765-c015b36e7fe3/railway_deployment_readiness_plan.md) for the full plan.

---

## 5️⃣ Hygiene & gotchas

- **`.env` must never be committed** — it's already in `.gitignore`.
- **Port clash** — the Docker compose file publishes MySQL on host port 3306. Stop any local MySQL or change the port mapping.
- **Re-importing schema** — after the first Docker run, the volume holds the data. Use `docker compose down -v` to wipe it for a fresh start (destroys all local data).
- **`schema.sql` vs migrations** — `schema.sql` is a reference DDL. Django migrations are the canonical source of truth. Running `python manage.py migrate` after importing `schema.sql` is safe; Django will detect existing tables via the `django_migrations` table.
- **SQLite fallback** — set `DB_ENGINE=sqlite` in `.env` to skip MySQL entirely (useful for quick local testing).
