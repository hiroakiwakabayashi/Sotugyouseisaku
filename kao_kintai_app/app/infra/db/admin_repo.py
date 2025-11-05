# app/infra/db/admin_repo.py
import sqlite3
from pathlib import Path
from typing import Optional, Dict
import bcrypt

class AdminRepo:
    def __init__(self):
        self.db_path = Path(__file__).resolve().parents[3] / "data" / "db" / "kintai.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_table()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def ensure_table(self):
        with self._conn() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS admins (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              display_name TEXT NOT NULL,
              pw_hash BLOB NOT NULL,
              role TEXT NOT NULL DEFAULT 'admin',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            """)
            con.commit()

    # 初期管理者シード（admin01 / admin01）
    def seed_default(self):
        if self.exists_any():
            return
        self.create(username="admin01", display_name="管理者", password_plain="admin01", role="admin", is_active=True)

    def exists_any(self) -> bool:
        with self._conn() as con:
            cur = con.execute("SELECT 1 FROM admins LIMIT 1;")
            return cur.fetchone() is not None

    def create(self, *, username: str, display_name: str, password_plain: str, role: str = "admin", is_active: bool = True) -> int:
        pw_hash = bcrypt.hashpw(password_plain.encode("utf-8"), bcrypt.gensalt())
        with self._conn() as con:
            cur = con.execute("""
                INSERT INTO admins (username, display_name, pw_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?);
            """, (username, display_name, pw_hash, role, 1 if is_active else 0))
            con.commit()
            return cur.lastrowid

    def find_by_username(self, username: str) -> Optional[Dict]:
        with self._conn() as con:
            cur = con.execute("""
                SELECT id, username, display_name, pw_hash, role, is_active
                FROM admins WHERE username = ?;
            """, (username,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "username": row[1],
                "display_name": row[2],
                "pw_hash": row[3],
                "role": row[4],
                "is_active": bool(row[5]),
            }

    def verify_login(self, username: str, password_plain: str) -> Optional[Dict]:
        user = self.find_by_username(username)
        if not user or not user["is_active"]:
            return None
        try:
            if bcrypt.checkpw(password_plain.encode("utf-8"), user["pw_hash"]):
                return user
        except Exception:
            return None
        return None

    def list_all(self):
        with self._conn() as con:
            cur = con.execute("""
                SELECT id, username, display_name, role, is_active, created_at
                FROM admins ORDER BY id DESC;
            """)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
