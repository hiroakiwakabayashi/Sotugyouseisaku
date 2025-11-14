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
        # RowFactoryは都度設定（dict化しやすい）
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._connect() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS attendance(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              employee_code TEXT NOT NULL,
              punch_type TEXT NOT NULL,          -- CLOCK_IN / BREAK_START / BREAK_END / CLOCK_OUT
              ts TEXT NOT NULL                   -- ISO8601 'YYYY-MM-DDTHH:MM:SS[.fff]'
            );
            """)
            # 検索高速化
            con.execute("CREATE INDEX IF NOT EXISTS idx_attendance_emp_ts ON attendance(employee_code, ts);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_attendance_ts ON attendance(ts);")
            con.commit()

    # ========= CRUD =========
    def add(self, employee_code: str, punch_type: str):
        now = datetime.now().isoformat()
        with self._connect() as con:
            con.execute(
                "INSERT INTO attendance(employee_code,punch_type,ts) VALUES (?,?,?)",
                (employee_code, punch_type, now)
            )
            con.commit()

    def get_last(self, employee_code: str):
        """その従業員の直近の打刻1件を返す（なければ None）。"""
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
        """
        画面の一覧表示用。
        start_date/end_date は 'YYYY-MM-DD' を想定。
        """
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

    # ========= 集計用：月次給与で使用 =========
    def iter_logs(self, start_date: str, end_date: str, employee_code: str | None = None):
        """
        指定期間の勤怠ログを employee_code, type, ts で時系列に返す。
        - start_date/end_date: 'YYYY-MM-DD'（endは当日を含む）
        - type: 'CLOCK_IN' / 'CLOCK_OUT' / 'BREAK_START' / 'BREAK_END'
        - ts: ISO文字列（'YYYY-MM-DDTHH:MM:SS' など）
        """
        q = """
          SELECT employee_code,
                 punch_type AS type,   -- ← 重要：列別名で 'type' に揃える
                 ts
          FROM attendance
          WHERE ts BETWEEN ? AND ?
        """
        # 日境界を含むように00:00:00〜23:59:59で絞る
        s = f"{start_date}T00:00:00"
        e = f"{end_date}T23:59:59"

        params = [s, e]
        if employee_code:
            q += " AND employee_code = ?"
            params.append(employee_code)
        q += " ORDER BY employee_code, ts"

        with self._connect() as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(q, params)
            rows = cur.fetchall()

        return [{"employee_code": r["employee_code"], "type": r["type"], "ts": r["ts"]} for r in rows]
