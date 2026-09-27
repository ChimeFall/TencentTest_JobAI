import json
import os
from datetime import datetime
from contextlib import contextmanager
import sqlite3

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

try:
    import pymysql
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from app.config import DATABASE_URL, MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_PORT

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "offer_catcher.db")

# 根据 DATABASE_URL 决定用哪个数据库驱动
_use_postgres = False
_use_mysql = False
_pg_conn_string = ""

if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    _use_postgres = True
    _pg_conn_string = DATABASE_URL

if MYSQL_HOST and MYSQL_USER and MYSQL_PASSWORD and MYSQL_DATABASE:
    _use_mysql = True


def _get_pg_conn():
    return psycopg2.connect(_pg_conn_string)


def _get_mysql_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=int(MYSQL_PORT),
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def init_db():
    """Initialize database tables."""
    if _use_mysql:
        _init_mysql()
    elif _use_postgres:
        _init_pg()
    else:
        _init_sqlite()


def _init_pg():
    conn = _get_pg_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            resume_id TEXT PRIMARY KEY,
            raw_text TEXT,
            parsed_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            session_id TEXT PRIMARY KEY,
            resume_id TEXT,
            profile_json JSONB,
            current_stage TEXT DEFAULT 'S1',
            session_token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            platform TEXT,
            title TEXT,
            company TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            salary_score REAL DEFAULT 0,
            city TEXT,
            city_tier INTEGER DEFAULT 2,
            industry TEXT,
            company_size TEXT,
            level TEXT,
            skills_required JSONB,
            jd_text TEXT,
            radar_json JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id SERIAL PRIMARY KEY,
            session_id TEXT,
            stage TEXT,
            role TEXT,
            content TEXT,
            payload JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_profiles_token ON user_profiles(session_token);
    """)
    conn.commit()
    conn.close()


def _init_mysql():
    """MySQL tables are created via CloudBase MCP — this is a no-op.
    Kept here for code path consistency."""
    pass


def _init_sqlite():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    statements = [
        """CREATE TABLE IF NOT EXISTS resumes (
            resume_id TEXT PRIMARY KEY,
            raw_text TEXT,
            parsed_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS user_profiles (
            session_id TEXT PRIMARY KEY,
            resume_id TEXT,
            profile_json TEXT,
            current_stage TEXT DEFAULT 'S1',
            session_token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            platform TEXT,
            title TEXT,
            company TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            salary_score REAL DEFAULT 0,
            city TEXT,
            city_tier INTEGER DEFAULT 2,
            industry TEXT,
            company_size TEXT,
            level TEXT,
            skills_required TEXT,
            jd_text TEXT,
            radar_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            stage TEXT,
            role TEXT,
            content TEXT,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_token ON user_profiles(session_token)",
    ]
    for stmt in statements:
        try:
            cursor.execute(stmt)
        except sqlite3.OperationalError as e:
            print(f"SQLite init warning (ignored): {e}")
    # 老库缺列就自动补上，省得每次改字段都要手动刷库
    _sqlite_migrate(conn, cursor)
    conn.commit()
    conn.close()


def _sqlite_migrate(conn, cursor):
    """Add missing columns that may have been added after table creation."""
    migrations = {
        "user_profiles": ["session_token TEXT", "token_expires_at TEXT", "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"],
    }
    for table, cols in migrations.items():
        try:
            cursor.execute(f"SELECT * FROM {table} LIMIT 0")
            existing_cols = [desc[0] for desc in cursor.description]
        except sqlite3.OperationalError:
            continue
        for col_def in cols:
            col_name = col_def.split()[0]
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                    print(f"SQLite migration: added {col_name} to {table}")
                except sqlite3.OperationalError as e:
                    print(f"SQLite migration warning: {e}")


@contextmanager
def get_db():
    if _use_mysql:
        conn = _get_mysql_conn()
        try:
            yield conn
        finally:
            conn.close()
    elif _use_postgres:
        conn = _get_pg_conn()
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def _serialize(val):
    return json.dumps(val, ensure_ascii=False)


def _deserialize(val):
    if val is None:
        return None
    if isinstance(val, dict) or isinstance(val, list):
        return val
    if isinstance(val, bytes):
        val = val.decode('utf-8')
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


# --- Resume operations ---

def save_resume(resume_id: str, raw_text: str, parsed: dict):
    with get_db() as db:
        if _use_mysql:
            db.cursor().execute(
                """INSERT INTO resumes (resume_id, raw_text, parsed_json)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   raw_text=VALUES(raw_text), parsed_json=VALUES(parsed_json)""",
                (resume_id, raw_text, _serialize(parsed))
            )
        elif _use_postgres:
            db.cursor().execute(
                """INSERT INTO resumes (resume_id, raw_text, parsed_json)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (resume_id) DO UPDATE SET
                   raw_text=EXCLUDED.raw_text, parsed_json=EXCLUDED.parsed_json""",
                (resume_id, raw_text, _serialize(parsed))
            )
        else:
            db.execute(
                "INSERT OR REPLACE INTO resumes (resume_id, raw_text, parsed_json) VALUES (?, ?, ?)",
                (resume_id, raw_text, _serialize(parsed))
            )
        db.commit()


def get_resume(resume_id: str) -> dict | None:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM resumes WHERE resume_id = %s", (resume_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "resume_id": row["resume_id"],
                    "raw_text": row["raw_text"],
                    "parsed": _deserialize(row["parsed_json"]),
                    "created_at": str(row.get("created_at", "")),
                }
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM resumes WHERE resume_id = %s", (resume_id,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                d = dict(zip(cols, row))
                return {
                    "resume_id": d["resume_id"],
                    "raw_text": d["raw_text"],
                    "parsed": _deserialize(d["parsed_json"]),
                    "created_at": str(d.get("created_at", "")),
                }
        else:
            row = db.execute("SELECT * FROM resumes WHERE resume_id = ?", (resume_id,)).fetchone()
            if row:
                return {
                    "resume_id": row["resume_id"],
                    "raw_text": row["raw_text"],
                    "parsed": _deserialize(row["parsed_json"]),
                    "created_at": row["created_at"],
                }
        return None


# --- User Profile operations ---

def save_profile(session_id: str, resume_id: str, profile: dict, stage: str = "S1",
                 session_token: str = None, token_expires_at: datetime = None):
    with get_db() as db:
        if _use_mysql:
            db.cursor().execute(
                """INSERT INTO user_profiles (session_id, resume_id, profile_json, current_stage,
                   session_token, token_expires_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   resume_id=VALUES(resume_id), profile_json=VALUES(profile_json),
                   current_stage=VALUES(current_stage),
                   session_token=VALUES(session_token),
                   token_expires_at=VALUES(token_expires_at),
                   updated_at=VALUES(updated_at)""",
                (session_id, resume_id, _serialize(profile), stage,
                 session_token, token_expires_at, datetime.now())
            )
        elif _use_postgres:
            db.cursor().execute(
                """INSERT INTO user_profiles (session_id, resume_id, profile_json, current_stage,
                   session_token, token_expires_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (session_id) DO UPDATE SET
                   resume_id=EXCLUDED.resume_id, profile_json=EXCLUDED.profile_json,
                   current_stage=EXCLUDED.current_stage,
                   session_token=EXCLUDED.session_token,
                   token_expires_at=EXCLUDED.token_expires_at,
                   updated_at=EXCLUDED.updated_at""",
                (session_id, resume_id, _serialize(profile), stage,
                 session_token, token_expires_at, datetime.now())
            )
        else:
            db.execute(
                """INSERT OR REPLACE INTO user_profiles
                   (session_id, resume_id, profile_json, current_stage, session_token, token_expires_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, resume_id, _serialize(profile), stage,
                 session_token, token_expires_at, datetime.now())
            )
        db.commit()


def get_profile(session_id: str) -> dict | None:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM user_profiles WHERE session_id = %s", (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "resume_id": row["resume_id"],
                    "profile": _deserialize(row["profile_json"]),
                    "current_stage": row["current_stage"],
                    "session_token": row.get("session_token"),
                    "token_expires_at": row.get("token_expires_at"),
                }
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM user_profiles WHERE session_id = %s", (session_id,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                d = dict(zip(cols, row))
                return {
                    "session_id": d["session_id"],
                    "resume_id": d["resume_id"],
                    "profile": _deserialize(d["profile_json"]),
                    "current_stage": d["current_stage"],
                    "session_token": d.get("session_token"),
                    "token_expires_at": d.get("token_expires_at"),
                }
        else:
            row = db.execute("SELECT * FROM user_profiles WHERE session_id = ?", (session_id,)).fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "resume_id": row["resume_id"],
                    "profile": _deserialize(row["profile_json"]),
                    "current_stage": row["current_stage"],
                    "session_token": row["session_token"],
                    "token_expires_at": row["token_expires_at"],
                }
        return None


def get_profile_by_token(token: str) -> dict | None:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM user_profiles WHERE session_token = %s AND token_expires_at > %s",
                (token, datetime.now())
            )
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "resume_id": row["resume_id"],
                    "profile": _deserialize(row["profile_json"]),
                    "current_stage": row["current_stage"],
                    "session_token": row["session_token"],
                    "token_expires_at": row["token_expires_at"],
                }
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM user_profiles WHERE session_token = %s AND token_expires_at > %s",
                (token, datetime.now())
            )
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                d = dict(zip(cols, row))
                return {
                    "session_id": d["session_id"],
                    "resume_id": d["resume_id"],
                    "profile": _deserialize(d["profile_json"]),
                    "current_stage": d["current_stage"],
                    "session_token": d["session_token"],
                    "token_expires_at": d["token_expires_at"],
                }
        else:
            row = db.execute(
                "SELECT * FROM user_profiles WHERE session_token = ? AND token_expires_at > ?",
                (token, datetime.now().isoformat())
            ).fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "resume_id": row["resume_id"],
                    "profile": _deserialize(row["profile_json"]),
                    "current_stage": row["current_stage"],
                    "session_token": row["session_token"],
                    "token_expires_at": row["token_expires_at"],
                }
        return None


# --- Job operations ---

def get_all_jobs() -> list[dict]:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            results = []
            for row in rows:
                row["skills_required"] = _deserialize(row["skills_required"])
                row["radar_json"] = _deserialize(row["radar_json"]) or {}
                results.append(row)
            return results
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            results = []
            for row in rows:
                d = dict(zip(cols, row))
                d["skills_required"] = _deserialize(d["skills_required"])
                d["radar_json"] = _deserialize(d["radar_json"]) or {}
                results.append(d)
            return results
        else:
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["skills_required"] = _deserialize(d["skills_required"])
                d["radar_json"] = _deserialize(d["radar_json"]) or {}
                results.append(d)
            return results


def get_job(job_id: str) -> dict | None:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
            row = cursor.fetchone()
            if row:
                row["skills_required"] = _deserialize(row["skills_required"])
                row["radar_json"] = _deserialize(row["radar_json"]) or {}
                return row
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                d = dict(zip(cols, row))
                d["skills_required"] = _deserialize(d["skills_required"])
                d["radar_json"] = _deserialize(d["radar_json"]) or {}
                return d
        else:
            row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row:
                d = dict(row)
                d["skills_required"] = _deserialize(d["skills_required"])
                d["radar_json"] = _deserialize(d["radar_json"]) or {}
                return d
        return None


def save_job(job: dict):
    with get_db() as db:
        if _use_mysql:
            db.cursor().execute(
                """INSERT INTO jobs
                   (job_id, platform, title, company, salary_min, salary_max, salary_score,
                    city, city_tier, industry, company_size, level, skills_required, jd_text, radar_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                   title=VALUES(title), company=VALUES(company),
                   salary_min=VALUES(salary_min), salary_max=VALUES(salary_max),
                   salary_score=VALUES(salary_score), city=VALUES(city),
                   industry=VALUES(industry), skills_required=VALUES(skills_required),
                   jd_text=VALUES(jd_text), radar_json=VALUES(radar_json)""",
                (job["job_id"], job["platform"], job["title"], job["company"],
                 job["salary_min"], job["salary_max"], job.get("salary_score", 0),
                 job["city"], job.get("city_tier", 2), job["industry"],
                 job.get("company_size", ""), job.get("level", "初级"),
                 _serialize(job["skills_required"]),
                 job["jd_text"],
                 _serialize(job.get("radar_json", {})))
            )
        elif _use_postgres:
            db.cursor().execute(
                """INSERT INTO jobs
                   (job_id, platform, title, company, salary_min, salary_max, salary_score,
                    city, city_tier, industry, company_size, level, skills_required, jd_text, radar_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (job_id) DO UPDATE SET
                   title=EXCLUDED.title, company=EXCLUDED.company,
                   salary_min=EXCLUDED.salary_min, salary_max=EXCLUDED.salary_max,
                   salary_score=EXCLUDED.salary_score, city=EXCLUDED.city,
                   industry=EXCLUDED.industry, skills_required=EXCLUDED.skills_required,
                   jd_text=EXCLUDED.jd_text, radar_json=EXCLUDED.radar_json""",
                (job["job_id"], job["platform"], job["title"], job["company"],
                 job["salary_min"], job["salary_max"], job.get("salary_score", 0),
                 job["city"], job.get("city_tier", 2), job["industry"],
                 job.get("company_size", ""), job.get("level", "初级"),
                 _serialize(job["skills_required"]),
                 job["jd_text"],
                 _serialize(job.get("radar_json", {})))
            )
        else:
            db.execute(
                """INSERT OR REPLACE INTO jobs
                   (job_id, platform, title, company, salary_min, salary_max, salary_score,
                    city, city_tier, industry, company_size, level, skills_required, jd_text, radar_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (job["job_id"], job["platform"], job["title"], job["company"],
                 job["salary_min"], job["salary_max"], job.get("salary_score", 0),
                 job["city"], job.get("city_tier", 2), job["industry"],
                 job.get("company_size", ""), job.get("level", "初级"),
                 _serialize(job["skills_required"]),
                 job["jd_text"],
                 _serialize(job.get("radar_json", {})))
            )
        db.commit()


# --- Chat History ---

def save_chat(session_id: str, stage: str, role: str, content: str, payload: dict = None):
    with get_db() as db:
        if _use_mysql:
            db.cursor().execute(
                "INSERT INTO chat_history (session_id, stage, role, content, payload) VALUES (%s, %s, %s, %s, %s)",
                (session_id, stage, role, content, _serialize(payload) if payload else None)
            )
        elif _use_postgres:
            db.cursor().execute(
                "INSERT INTO chat_history (session_id, stage, role, content, payload) VALUES (%s, %s, %s, %s, %s)",
                (session_id, stage, role, content, _serialize(payload) if payload else None)
            )
        else:
            db.execute(
                "INSERT INTO chat_history (session_id, stage, role, content, payload) VALUES (?, ?, ?, ?, ?)",
                (session_id, stage, role, content, _serialize(payload) if payload else None)
            )
        db.commit()


def get_chat_history(session_id: str) -> list[dict]:
    with get_db() as db:
        if _use_mysql:
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM chat_history WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                if row["payload"]:
                    row["payload"] = _deserialize(row["payload"])
                results.append(row)
            return results
        elif _use_postgres:
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM chat_history WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]
            results = []
            for row in rows:
                d = dict(zip(cols, row))
                if d["payload"]:
                    d["payload"] = _deserialize(d["payload"])
                results.append(d)
            return results
        else:
            rows = db.execute(
                "SELECT * FROM chat_history WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,)
            ).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                if d["payload"]:
                    d["payload"] = _deserialize(d["payload"])
                results.append(d)
            return results
