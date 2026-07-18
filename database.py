import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "vahta.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id     INTEGER PRIMARY KEY,
                name        TEXT,
                phone       TEXT,
                city        TEXT,
                profession  TEXT,
                experience  TEXT,
                salary      TEXT,
                shift       TEXT
            );

            CREATE TABLE IF NOT EXISTS vacancies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                employer_id INTEGER NOT NULL,
                profession  TEXT,
                city        TEXT,
                company     TEXT,
                salary      TEXT,
                schedule    TEXT,
                contact     TEXT
            );

            CREATE TABLE IF NOT EXISTS responses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id   INTEGER NOT NULL,
                employer_id INTEGER NOT NULL,
                vac_id      INTEGER NOT NULL,
                UNIQUE(worker_id, vac_id)
            );
        """)

# ── Профили работников ────────────────────────────────────────

def get_profile(chat_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None

def save_profile(chat_id, data):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (chat_id, name, phone, city, profession, experience, salary, shift)
            VALUES (:chat_id, :name, :phone, :city, :profession, :experience, :salary, :shift)
            ON CONFLICT(chat_id) DO UPDATE SET
                name=excluded.name, phone=excluded.phone, city=excluded.city,
                profession=excluded.profession, experience=excluded.experience,
                salary=excluded.salary, shift=excluded.shift
        """, {"chat_id": chat_id, **data})

def delete_profile(chat_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))

def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

def count_filled_profiles():
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE name IS NOT NULL AND shift IS NOT NULL"
        ).fetchone()[0]

# ── Вакансии ─────────────────────────────────────────────────

def add_vacancy(employer_id, data):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO vacancies (employer_id, profession, city, company, salary, schedule, contact)
            VALUES (:employer_id, :profession, :city, :company, :salary, :schedule, :contact)
        """, {"employer_id": employer_id, **data})
        return cur.lastrowid

def get_vacancies(employer_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM vacancies WHERE employer_id = ?", (employer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_vacancies_by_city(city):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM vacancies WHERE LOWER(city) = LOWER(?)", (city,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_vacancy_by_id(vac_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM vacancies WHERE id = ?", (vac_id,)).fetchone()
        return dict(row) if row else None

def count_vacancies():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]

# ── Отклики ───────────────────────────────────────────────────

def add_response(worker_id, employer_id, vac_id):
    """Возвращает True если отклик добавлен, False если уже существует."""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO responses (worker_id, employer_id, vac_id) VALUES (?, ?, ?)",
                (worker_id, employer_id, vac_id)
            )
        return True
    except sqlite3.IntegrityError:
        return False

def get_responses_for_employer(employer_id):
    """Возвращает список {vac_id, worker_id} для всех вакансий работодателя."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT vac_id, worker_id FROM responses WHERE employer_id = ?", (employer_id,)
        ).fetchall()
        return [dict(r) for r in rows]
