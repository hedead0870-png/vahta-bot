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

            CREATE TABLE IF NOT EXISTS sessions (
                chat_id    INTEGER NOT NULL,
                key        TEXT    NOT NULL,
                value      TEXT    NOT NULL,
                updated_at TEXT    DEFAULT (datetime('now')),
                PRIMARY KEY(chat_id, key)
            );

            CREATE TABLE IF NOT EXISTS employer_status (
                employer_id INTEGER PRIMARY KEY,
                status      TEXT    NOT NULL DEFAULT 'new',
                is_manual   INTEGER NOT NULL DEFAULT 0,
                verified_at TEXT
            );

            CREATE TABLE IF NOT EXISTS complaints (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                employer_id INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                reason      TEXT NOT NULL,
                text        TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(employer_id, user_id, reason)
            );

            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                vacancy_id  INTEGER NOT NULL,
                worker_id   INTEGER NOT NULL,
                employer_id INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'new',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(worker_id, vacancy_id)
            );
        """)
        # Миграции: добавить колонки если таблица уже существует без них
        cols = [r[1] for r in conn.execute("PRAGMA table_info(vacancies)").fetchall()]
        if 'status' not in cols:
            conn.execute("ALTER TABLE vacancies ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        if 'inn' not in cols:
            conn.execute("ALTER TABLE vacancies ADD COLUMN inn TEXT")

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
            INSERT INTO vacancies
                (employer_id, profession, city, company, inn, salary, schedule, contact)
            VALUES
                (:employer_id, :profession, :city, :company, :inn, :salary, :schedule, :contact)
        """, {
            "employer_id": employer_id,
            "inn": data.get("inn"),
            **{k: data.get(k) for k in ("profession", "city", "company", "salary", "schedule", "contact")}
        })
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

# ── Отклики (legacy) ─────────────────────────────────────────

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

# ── Заявки (applications) ─────────────────────────────────────

APPLICATION_STATUSES = ('new', 'viewed', 'accepted', 'rejected')
APPLICATION_STATUS_LABEL = {
    'new':      '🆕 Новый',
    'viewed':   '👁 Просмотрен',
    'accepted': '✅ Принят',
    'rejected': '❌ Отказан',
}

def add_application(vacancy_id, worker_id, employer_id):
    """Создаёт заявку. Возвращает id новой заявки или None при дубликате."""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO applications (vacancy_id, worker_id, employer_id)
                   VALUES (?, ?, ?)""",
                (vacancy_id, worker_id, employer_id)
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def get_application_by_id(app_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        return dict(row) if row else None

def set_application_status(app_id, status):
    """Обновляет статус заявки. Возвращает worker_id для уведомления."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE applications SET status = ? WHERE id = ?", (status, app_id)
        )
        row = conn.execute(
            "SELECT worker_id FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        return row['worker_id'] if row else None

def get_applications_for_employer(employer_id):
    """Заявки на вакансии работодателя, сгруппированные с данными кандидата и вакансии."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.id, a.vacancy_id, a.worker_id, a.status, a.created_at,
                      v.profession, v.company, v.city  AS vac_city, v.status AS vac_status,
                      u.name, u.phone, u.city AS worker_city,
                      u.profession AS worker_profession, u.experience,
                      u.salary AS worker_salary, u.shift
               FROM applications a
               JOIN vacancies v ON v.id = a.vacancy_id
               LEFT JOIN users u ON u.chat_id = a.worker_id
               WHERE a.employer_id = ?
               ORDER BY a.created_at DESC""",
            (employer_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_applications_for_worker(worker_id):
    """Заявки работника с данными вакансии."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.id, a.vacancy_id, a.employer_id, a.status, a.created_at,
                      v.profession, v.company, v.city AS vac_city, v.salary
               FROM applications a
               JOIN vacancies v ON v.id = a.vacancy_id
               WHERE a.worker_id = ?
               ORDER BY a.created_at DESC""",
            (worker_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def mark_application_viewed(app_id):
    """Помечает заявку просмотренной (только если статус 'new')."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE applications SET status = 'viewed' WHERE id = ? AND status = 'new'",
            (app_id,)
        )

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

def get_employer_card(employer_id):
    """Возвращает агрегированную карточку работодателя."""
    with get_conn() as conn:
        # Берём последнюю вакансию для имени компании и ИНН
        vac_row = conn.execute(
            "SELECT company, inn FROM vacancies WHERE employer_id = ? ORDER BY id DESC LIMIT 1",
            (employer_id,)
        ).fetchone()
        vac_count = conn.execute(
            "SELECT COUNT(*) FROM vacancies WHERE employer_id = ?", (employer_id,)
        ).fetchone()[0]
        active_vac_count = conn.execute(
            "SELECT COUNT(*) FROM vacancies WHERE employer_id = ? AND status = 'active'", (employer_id,)
        ).fetchone()[0]
        rev_row = conn.execute(
            """SELECT AVG(rating) as avg_r, COUNT(*) as cnt,
                      COUNT(DISTINCT worker_id) as unique_workers
               FROM reviews WHERE employer_id = ?""",
            (employer_id,)
        ).fetchone()
        city_rows = conn.execute(
            "SELECT DISTINCT city FROM vacancies WHERE employer_id = ? AND city IS NOT NULL ORDER BY city",
            (employer_id,)
        ).fetchall()
        complaint_count = conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE employer_id = ? AND status = 'pending'", (employer_id,)
        ).fetchone()[0]
    return {
        "employer_id":       employer_id,
        "company":           vac_row["company"]  if vac_row else "—",
        "inn":               vac_row["inn"]       if vac_row else "—",
        "avg_rating":        round(rev_row["avg_r"], 1) if rev_row["avg_r"] else None,
        "review_count":      rev_row["cnt"],
        "vacancy_count":     vac_count,
        "active_vac_count":  active_vac_count,
        "unique_workers":    rev_row["unique_workers"],
        "cities":            [r["city"] for r in city_rows],
        "complaint_count":   complaint_count,
    }

def get_employer_reviews_paged(employer_id, page=0, per_page=5):
    """Возвращает (список отзывов на странице, общее кол-во отзывов)."""
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM reviews WHERE employer_id = ?", (employer_id,)
        ).fetchone()[0]
        rows = conn.execute(
            """SELECT r.*, u.name as worker_name
               FROM reviews r
               LEFT JOIN users u ON u.chat_id = r.worker_id
               WHERE r.employer_id = ?
               ORDER BY r.created_at DESC
               LIMIT ? OFFSET ?""",
            (employer_id, per_page, page * per_page)
        ).fetchall()
        return [dict(r) for r in rows], total

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

# ── Жалобы на работодателей ──────────────────────────────────

def add_complaint(employer_id, user_id, reason, text):
    """Добавляет жалобу. Один пользователь — одна жалоба на одного работодателя по одной причине.
    Возвращает id новой жалобы или None если дубликат.
    """
    try:
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO complaints (employer_id, user_id, reason, text)
                   VALUES (?, ?, ?, ?)""",
                (employer_id, user_id, reason, text)
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def count_pending_complaints():
    """Количество необработанных жалоб (для админки)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE status = 'pending'"
        ).fetchone()[0]

def get_pending_complaints(limit=30):
    """Список необработанных жалоб для админки."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT c.*,
                      (SELECT company FROM vacancies
                       WHERE employer_id = c.employer_id ORDER BY id DESC LIMIT 1) AS company
               FROM complaints c
               WHERE c.status = 'pending'
               ORDER BY c.created_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_complaint_by_id(complaint_id):
    """Одна жалоба по id."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT c.*,
                      (SELECT company FROM vacancies
                       WHERE employer_id = c.employer_id ORDER BY id DESC LIMIT 1) AS company
               FROM complaints c WHERE c.id = ?""",
            (complaint_id,)
        ).fetchone()
        return dict(row) if row else None

def resolve_complaint(complaint_id):
    """Помечает жалобу как рассмотренную."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE complaints SET status = 'resolved' WHERE id = ?", (complaint_id,)
        )

# ── Статусы работодателей ────────────────────────────────────

EMPLOYER_STATUSES = ('new', 'verified', 'complaints')

def _compute_auto_status(avg_rating, review_count):
    """Возвращает автоматический статус на основе рейтинга и числа отзывов."""
    if not review_count or avg_rating is None:
        return 'new'
    if avg_rating < 3.5:
        return 'complaints'
    if avg_rating >= 4.5 and review_count >= 5:
        return 'verified'
    return 'new'

def get_employer_status(employer_id):
    """Возвращает dict {status, is_manual, verified_at}.
    Если есть ручная установка — возвращает её; иначе вычисляет авто.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status, is_manual, verified_at FROM employer_status WHERE employer_id = ?",
            (employer_id,)
        ).fetchone()
        if row and row['is_manual']:
            return dict(row)
    # Авто-вычисление
    avg, cnt = get_employer_rating(employer_id)
    return {'status': _compute_auto_status(avg, cnt), 'is_manual': 0, 'verified_at': None}

def set_employer_status(employer_id, status, is_manual=True):
    """Устанавливает статус работодателя (ручной или автоматический)."""
    from datetime import datetime
    verified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'verified' else None
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO employer_status (employer_id, status, is_manual, verified_at)
               VALUES (?, ?, ?, ?)""",
            (employer_id, status, 1 if is_manual else 0, verified_at)
        )

def refresh_employer_status(employer_id):
    """Пересчитывает и сохраняет авто-статус (не перезаписывает ручной)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT is_manual FROM employer_status WHERE employer_id = ?", (employer_id,)
        ).fetchone()
        if row and row['is_manual']:
            return  # ручная установка — не трогаем
    avg, cnt = get_employer_rating(employer_id)
    status = _compute_auto_status(avg, cnt)
    from datetime import datetime
    verified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if status == 'verified' else None
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO employer_status (employer_id, status, is_manual, verified_at)
               VALUES (?, ?, 0, ?)""",
            (employer_id, status, verified_at)
        )

def get_all_employers_for_admin():
    """Список всех работодателей (имевших хоть одну вакансию) со статусом — для админки."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT v.employer_id,
                      (SELECT company FROM vacancies
                       WHERE employer_id = v.employer_id ORDER BY id DESC LIMIT 1) AS company,
                      COALESCE(es.status,    'new') AS status,
                      COALESCE(es.is_manual, 0)     AS is_manual
               FROM vacancies v
               LEFT JOIN employer_status es ON es.employer_id = v.employer_id
               ORDER BY v.employer_id"""
        ).fetchall()
        return [dict(r) for r in rows]

# ── Сессии (промежуточные состояния диалогов) ────────────────

def set_session(chat_id, key, value):
    """Сохраняет произвольное значение (JSON-сериализуемое) для chat_id+key."""
    import json
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO sessions (chat_id, key, value, updated_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (chat_id, key, json.dumps(value, ensure_ascii=False))
        )

def get_session(chat_id, key, default=None):
    """Возвращает сохранённое значение или default."""
    import json
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM sessions WHERE chat_id = ? AND key = ?", (chat_id, key)
        ).fetchone()
        return json.loads(row[0]) if row else default

def del_session(chat_id, key):
    """Удаляет запись сессии."""
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE chat_id = ? AND key = ?", (chat_id, key))

def has_session(chat_id, key):
    """Проверяет наличие записи сессии."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM sessions WHERE chat_id = ? AND key = ?", (chat_id, key)
        ).fetchone() is not None

def del_all_sessions(chat_id):
    """Удаляет все сессии пользователя (при сбросе состояния)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))

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
