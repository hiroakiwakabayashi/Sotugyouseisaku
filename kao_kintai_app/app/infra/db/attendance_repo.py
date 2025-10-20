import sqlite3
from pathlib import Path
from datetime import datetime

class AttendanceRepo:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[3]
        self.db_path = self.project_root / "data" / "db" / "kintai.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS attendance(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              employee_code TEXT NOT NULL,
              punch_type TEXT NOT NULL,
              ts TEXT NOT NULL
            );
            """)
            con.commit()

    def add(self, employee_code: str, punch_type: str):
        now = datetime.now().isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO attendance(employee_code,punch_type,ts) VALUES (?,?,?)",
                (employee_code, punch_type, now)
            )
            con.commit()

    def get_last(self, employee_code: str):
        """その従業員の直近の打刻1件を返す（なければ None）"""
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT id, ts, employee_code, punch_type FROM attendance WHERE employee_code=? ORDER BY id DESC LIMIT 1",
                (employee_code,)
            )
            r = cur.fetchone()
        return dict(r) if r else None

    def list_records(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        employee_code: str | None = None,
        limit: int = 2000,
    ):
        where = ["1=1"]
        params: dict[str, object] = {}
        if start_date:
            where.append("a.ts >= :start_ts"); params["start_ts"] = f"{start_date}T00:00:00"
        if end_date:
            where.append("a.ts <= :end_ts"); params["end_ts"] = f"{end_date}T23:59:59"
        if employee_code and employee_code.strip():
            where.append("a.employee_code = :code"); params["code"] = employee_code.strip()

        sql = f"""
        SELECT a.id, a.ts, a.employee_code, IFNULL(e.name, '') AS name, a.punch_type
        FROM attendance a
        LEFT JOIN employees e ON e.code = a.employee_code
        WHERE {" AND ".join(where)}
        ORDER BY a.id DESC
        LIMIT :limit
        """
        params["limit"] = int(limit)
        with self._connect() as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
        return rows
