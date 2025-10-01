import sqlite3, string, random
from pathlib import Path
from datetime import datetime

class EmployeeRepo:
    def __init__(self):
        # プロジェクトルート/ data/db/kintai.sqlite3
        self.project_root = Path(__file__).resolve().parents[3]
        self.db_path = self.project_root / "data" / "db" / "kintai.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS employees(
              code TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'USER',
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            """)
            con.commit()

    # -------- CRUD --------
    def list_all(self):
        with self._connect() as con:
            cur = con.execute("SELECT code,name,role,active,created_at FROM employees ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [{"code":r[0], "name":r[1], "role":r[2], "active":bool(r[3]), "created_at":r[4]} for r in rows]

    def get(self, code:str):
        with self._connect() as con:
            cur = con.execute("SELECT code,name,role,active,created_at FROM employees WHERE code=?", (code,))
            r = cur.fetchone()
        return None if not r else {"code":r[0], "name":r[1], "role":r[2], "active":bool(r[3]), "created_at":r[4]}

    def create(self, name:str, role:str="USER"):
        code = self._generate_unique_code()
        now = datetime.now().isoformat()
        with self._connect() as con:
            con.execute("INSERT INTO employees(code,name,role,active,created_at) VALUES (?,?,?,?,?)",
                        (code, name, role, 1, now))
            con.commit()
        return code

    def update(self, code:str, name:str, role:str, active:bool):
        with self._connect() as con:
            con.execute("UPDATE employees SET name=?, role=?, active=? WHERE code=?",
                        (name, role, 1 if active else 0, code))
            con.commit()

    def set_active(self, code:str, active:bool):
        with self._connect() as con:
            con.execute("UPDATE employees SET active=? WHERE code=?", (1 if active else 0, code))
            con.commit()

    # -------- helpers --------
    def _generate_unique_code(self, length:int=8) -> str:
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=length))
            if not self.get(code):
                return code
