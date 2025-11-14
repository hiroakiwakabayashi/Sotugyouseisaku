# app/infra/db/employee_repo.py
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
        self._ensure_wage_column()  # 既存DBにも wage 列を足す

    # ===== 基本接続 =====
    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ===== スキーマ初期化 =====
    def _init_schema(self):
        # 初回作成時は wage 列込みで作る
        with self._connect() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS employees(
              code       TEXT PRIMARY KEY,
              name       TEXT NOT NULL,
              role       TEXT NOT NULL DEFAULT 'USER',
              active     INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              wage       REAL   -- 時給（円）。既存DBには後続でALTER
            );
            """)
            con.commit()

    def _ensure_wage_column(self):
        """既存DBに wage 列が無い場合は追加（後方互換）。"""
        with self._connect() as con:
            cur = con.execute("PRAGMA table_info(employees)")
            cols = [r[1] for r in cur.fetchall()]  # r[1] = 列名
            if "wage" not in cols:
                con.execute("ALTER TABLE employees ADD COLUMN wage REAL")
                con.commit()

    # ===== CRUD =====
    def list_all(self):
        with self._connect() as con:
            cur = con.execute(
                "SELECT code,name,role,active,created_at,wage FROM employees ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [
            {
                "code": r[0],
                "name": r[1],
                "role": r[2],
                "active": bool(r[3]),
                "created_at": r[4],
                "wage": r[5] if r[5] is not None else 0.0,  # 画面で使いやすいように数値化
            }
            for r in rows
        ]

    def get(self, code: str):
        with self._connect() as con:
            cur = con.execute(
                "SELECT code,name,role,active,created_at,wage FROM employees WHERE code=?",
                (code,),
            )
            r = cur.fetchone()
        return None if not r else {
            "code": r[0],
            "name": r[1],
            "role": r[2],
            "active": bool(r[3]),
            "created_at": r[4],
            "wage": r[5] if r[5] is not None else 0.0,
        }

    def create(self, name: str, role: str = "USER", wage: float | None = None):
        code = self._generate_unique_code()
        now = datetime.now().isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO employees(code,name,role,active,created_at,wage) VALUES (?,?,?,?,?,?)",
                (code, name, role, 1, now, wage),
            )
            con.commit()
        return code

    def update(self, code: str, name: str, role: str, active: bool, wage: float | None = None):
        with self._connect() as con:
            if wage is None:
                con.execute(
                    "UPDATE employees SET name=?, role=?, active=? WHERE code=?",
                    (name, role, 1 if active else 0, code),
                )
            else:
                con.execute(
                    "UPDATE employees SET name=?, role=?, active=?, wage=? WHERE code=?",
                    (name, role, 1 if active else 0, wage, code),
                )
            con.commit()

    def set_active(self, code: str, active: bool):
        with self._connect() as con:
            con.execute("UPDATE employees SET active=? WHERE code=?", (1 if active else 0, code))
            con.commit()

    # ===== 時給専用API =====
    def update_wage(self, code: str, wage: float):
        """従業員コード指定で時給のみ更新。存在しない code なら例外。"""
        with self._connect() as con:
            cur = con.execute("SELECT 1 FROM employees WHERE code=?", (code,))
            if cur.fetchone() is None:
                raise ValueError(f"employee code not found: {code}")
            con.execute("UPDATE employees SET wage=? WHERE code=?", (wage, code))
            con.commit()

    # ===== helpers =====
    def _generate_unique_code(self, length: int = 8) -> str:
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=length))
            if not self.get(code):
                return code
