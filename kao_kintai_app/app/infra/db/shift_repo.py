# app/infra/db/shift_repo.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

class ShiftRepo:
    def __init__(self):
        self.db_path = Path(__file__).resolve().parents[3] / "data" / "db" / "kintai.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_table()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def ensure_table(self):
        with self._conn() as con:
            con.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              employee_code TEXT NOT NULL,
              work_date TEXT NOT NULL,        -- YYYY-MM-DD
              start_time TEXT NOT NULL,       -- HH:MM
              end_time TEXT NOT NULL,         -- HH:MM
              note TEXT,
              created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            );
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(work_date);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_shifts_emp_date ON shifts(employee_code, work_date);")
            con.commit()

    def upsert(self, *, id: Optional[int], employee_code: str, work_date: str, start_time: str, end_time: str, note: str="") -> int:
        with self._conn() as con:
            if id:
                con.execute("""
                    UPDATE shifts
                       SET employee_code=?, work_date=?, start_time=?, end_time=?, note=?,
                           updated_at=(datetime('now','localtime'))
                     WHERE id=?;
                """, (employee_code, work_date, start_time, end_time, note, id))
                con.commit()
                return id
            cur = con.execute("""
                INSERT INTO shifts(employee_code, work_date, start_time, end_time, note)
                VALUES (?, ?, ?, ?, ?);
            """, (employee_code, work_date, start_time, end_time, note))
            con.commit()
            return cur.lastrowid

    def delete(self, id: int) -> None:
        with self._conn() as con:
            con.execute("DELETE FROM shifts WHERE id=?;", (id,))
            con.commit()

    def list_by_range(self, start_date: str, end_date: str, employee_code: Optional[str]=None) -> List[Dict]:
        sql = """
        SELECT id, employee_code, work_date, start_time, end_time, note
          FROM shifts
         WHERE work_date BETWEEN ? AND ?
        """
        params = [start_date, end_date]
        if employee_code:
            sql += " AND employee_code=?"
            params.append(employee_code)
        sql += " ORDER BY work_date ASC, start_time ASC"
        with self._conn() as con:
            cur = con.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
