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
                contact     TEXT,
                status      TEXT NOT NULL DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS responses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id   INTEGER NOT NULL,
                employer_id INTEGER NOT NULL,
                vac_id      INTEGER NOT NULL,
                UNIQUE(worker_id, vac_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id   INTEGER NOT NULL,
                employer_id INTEGER NOT NULL,
                vac_id      INTEGER NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                text        TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(worker_id, vac_id)
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                profession  TEXT NOT NULL,
                city        TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, profession, city)
            );
        """)
        # Миграция: добавить status если таблица уже существует без него
        cols = [r[1] for r in conn.execute("PRAGMA table_info(vacancies)").fetchall()]
        if 'status' not in cols:
            conn.execute("ALTER TABLE vacancies ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")

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
    """Возвращает только активные вакансии в указанном городе."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM vacancies WHERE LOWER(city) = LOWER(?) AND status = 'active'",
            (city,)
        ).fetchall()
        return [dict(r) for r in rows]

def search_vacancies(profession=None, city=None):
    """Поиск активных вакансий по профессии (LIKE) и городу (точное, регистронезависимое).
    Если city=None — ищет по всем городам.
    """
    conditions = ["status = 'active'"]
    params = []
    if profession:
        conditions.append("LOWER(profession) LIKE LOWER(?)")
        params.append(f"%{profession.strip()}%")
    if city:
        conditions.append("LOWER(city) = LOWER(?)")
        params.append(city.strip())
    sql = "SELECT * FROM vacancies WHERE " + " AND ".join(conditions)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

def get_vacancy_by_id(vac_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM vacancies WHERE id = ?", (vac_id,)).fetchone()
        return dict(row) if row else None

def set_vacancy_status(vac_id, status):
    """status: 'active' или 'closed'"""
    with get_conn() as conn:
        conn.execute("UPDATE vacancies SET status = ? WHERE id = ?", (status, vac_id))

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

# ── Отзывы ────────────────────────────────────────────────────

def add_review(worker_id, employer_id, vac_id, rating, text):
    """Возвращает True если отзыв добавлен, False если уже оставлял."""
    try:
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO reviews (worker_id, employer_id, vac_id, rating, text)
                   VALUES (?, ?, ?, ?, ?)""",
                (worker_id, employer_id, vac_id, rating, text)
            )
        return True
    except sqlite3.IntegrityError:
        return False

def get_reviews_for_employer(employer_id):
    """Возвращает все отзывы о работодателе."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reviews WHERE employer_id = ? ORDER BY created_at DESC",
            (employer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_employer_rating(employer_id):
    """Возвращает (средний_рейтинг, количество_отзывов) или (None, 0)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(rating) as avg_r, COUNT(*) as cnt FROM reviews WHERE employer_id = ?",
            (employer_id,)
        ).fetchone()
        return (round(row['avg_r'], 1) if row['avg_r'] else None, row['cnt'])

def has_reviewed(worker_id, vac_id):
    """Проверяет, оставлял ли работник отзыв по этой вакансии."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM reviews WHERE worker_id = ? AND vac_id = ?",
            (worker_id, vac_id)
        ).fetchone()
        return row is not None

# ── Подписки ─────────────────────────────────────────────────

def add_subscription(user_id, profession, city):
    """Добавляет подписку. city=None — любой город.
    Возвращает id новой подписки или None если уже существует."""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO subscriptions (user_id, profession, city) VALUES (?, ?, ?)",
                (user_id, profession.strip(), city.strip() if city else None)
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def get_subscriptions(user_id):
    """Возвращает все подписки пользователя."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def delete_subscription(sub_id, user_id):
    """Удаляет подписку по id (только свою)."""
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id)
        )

def delete_all_subscriptions(user_id):
    """Удаляет все подписки пользователя."""
    with get_conn() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))

def find_matching_subscribers(profession, city):
    """Возвращает user_id всех подписчиков, которым подходит вакансия.
    Совпадение профессии — LIKE (подстрока).
    Совпадение города — точное регистронезависимое, либо подписка без города (Любой город).
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT user_id FROM subscriptions
               WHERE LOWER(?) LIKE '%' || LOWER(profession) || '%'
                  OR LOWER(profession) LIKE '%' || LOWER(?) || '%'""",
            (profession, profession)
        ).fetchall()
        # Дополнительная фильтрация по городу в Python, чтобы учесть city=NULL (любой)
        candidate_ids = [r['user_id'] for r in rows]
        if not candidate_ids:
            return []
        placeholders = ','.join('?' * len(candidate_ids))
        filtered = conn.execute(
            f"""SELECT DISTINCT user_id FROM subscriptions
                WHERE user_id IN ({placeholders})
                  AND (city IS NULL OR LOWER(city) = LOWER(?))
                  AND (LOWER(?) LIKE '%' || LOWER(profession) || '%'
                       OR LOWER(profession) LIKE '%' || LOWER(?) || '%')""",
            (*candidate_ids, city if city else '', profession, profession)
        ).fetchall()
        return [r['user_id'] for r in filtered]
