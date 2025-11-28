# app/infra/db/shift_repo.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Iterable, Tuple
from datetime import date, datetime
from calendar import monthrange
import re


class ShiftRepo:
    def __init__(self):
        self.db_path = Path(__file__).resolve().parents[3] / "data" / "db" / "kintai.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_table()

    # ---------------- low-level ----------------
    def _conn(self):
        # 必要なら row_factory 指定でもOK（呼び出し側で dict 化しているので今はそのまま）
        return sqlite3.connect(self.db_path)

    # ---------------- schema ----------------
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
              -- ※ 以前は submitted_at が無かった
            );
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(work_date);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_shifts_emp_date ON shifts(employee_code, work_date);")

            # 既存DBに submitted_at が無ければ追加
            cols = [r[1] for r in con.execute("PRAGMA table_info(shifts);").fetchall()]
            if "submitted_at" not in cols:
                con.execute("ALTER TABLE shifts ADD COLUMN submitted_at TEXT;")  # NULL許容
            con.commit()

    # ---------------- validators ----------------
    _HHMM = re.compile(r"^\d{2}:\d{2}$")

    @staticmethod
    def _valid_date(d: str) -> bool:
        try:
            y, m, dd = map(int, d.split("-"))
            date(y, m, dd)
            return True
        except Exception:
            return False

    @classmethod
    def _valid_hhmm(cls, s: str) -> bool:
        if not cls._HHMM.match(s):
            return False
        hh, mm = map(int, s.split(":"))
        return 0 <= hh <= 23 and 0 <= mm <= 59

    def _validate_shift(self, employee_code: str, work_date: str,
                        start_time: str, end_time: str):
        if not employee_code:
            raise ValueError("employee_code は必須です。")
        if not self._valid_date(work_date):
            raise ValueError("work_date は YYYY-MM-DD 形式で指定してください。")
        if not self._valid_hhmm(start_time) or not self._valid_hhmm(end_time):
            raise ValueError("start_time / end_time は HH:MM 形式で指定してください。")
        # 24:00 を許容したい場合は別処理（ここは 00:00〜23:59）
        if end_time <= start_time:
            # 日跨ぎを許すなら UI 側で翌日扱いに分割して登録推奨。
            raise ValueError("end_time は start_time より後である必要があります。")

    # ---------------- CRUD ----------------
    def upsert(self, *, id: Optional[int], employee_code: str,
               work_date: str, start_time: str, end_time: str,
               note: str = "") -> int:
        """1件を新規 or 更新。"""
        self._validate_shift(employee_code, work_date, start_time, end_time)
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

    def upsert_many(self, items: Iterable[Tuple[Optional[int], str, str, str, str, str]]) -> List[int]:
        """
        複数件まとめて upsert。
        items: Iterable[(id, employee_code, work_date, start_time, end_time, note)]
        戻り値: 登録/更新後の id リスト
        """
        ids: List[int] = []
        with self._conn() as con:
            for id_, code, wdate, st, et, note in items:
                self._validate_shift(code, wdate, st, et)
                if id_:
                    con.execute("""
                        UPDATE shifts
                           SET employee_code=?, work_date=?, start_time=?, end_time=?, note=?,
                               updated_at=(datetime('now','localtime'))
                         WHERE id=?;
                    """, (code, wdate, st, et, note, id_))
                    ids.append(id_)
                else:
                    cur = con.execute("""
                        INSERT INTO shifts(employee_code, work_date, start_time, end_time, note)
                        VALUES (?, ?, ?, ?, ?);
                    """, (code, wdate, st, et, note))
                    ids.append(cur.lastrowid)
            con.commit()
        return ids

    def delete(self, id: int) -> None:
        with self._conn() as con:
            con.execute("DELETE FROM shifts WHERE id=?;", (id,))
            con.commit()

    def get(self, id: int) -> Optional[Dict]:
        with self._conn() as con:
            cur = con.execute("""
                SELECT id, employee_code, work_date, start_time, end_time, note, submitted_at
                  FROM shifts WHERE id=?;
            """, (id,))
            row = cur.fetchone()
        if not row:
            return None
        cols = ["id", "employee_code", "work_date", "start_time", "end_time", "note", "submitted_at"]
        return dict(zip(cols, row))

    # ---------------- 提出フラグ操作 ----------------
    def mark_submitted(self, shift_id: int) -> None:
        """提出日時を現在時刻でセット"""
        with self._conn() as con:
            con.execute(
                "UPDATE shifts SET submitted_at=?, updated_at=(datetime('now','localtime')) WHERE id=?;",
                (datetime.now().isoformat(timespec="seconds"), shift_id)
            )
            con.commit()

    def clear_submitted(self, shift_id: int) -> None:
        """提出フラグを解除"""
        with self._conn() as con:
            con.execute(
                "UPDATE shifts SET submitted_at=NULL, updated_at=(datetime('now','localtime')) WHERE id=?;",
                (shift_id,)
            )
            con.commit()

    # ---------------- queries ----------------
    def list_by_range(self, start_date: str, end_date: str,
                      employee_code: Optional[str] = None) -> List[Dict]:
        """
        指定期間（YYYY-MM-DD 〜 YYYY-MM-DD）でのシフト一覧。
        """
        if not (self._valid_date(start_date) and self._valid_date(end_date)):
            raise ValueError("start_date / end_date は YYYY-MM-DD 形式で指定してください。")
        sql = """
        SELECT id, employee_code, work_date, start_time, end_time, note, submitted_at
          FROM shifts
         WHERE work_date BETWEEN ? AND ?
        """
        params: list = [start_date, end_date]
        if employee_code:
            sql += " AND employee_code=?"
            params.append(employee_code)
        sql += " ORDER BY work_date ASC, start_time ASC"
        with self._conn() as con:
            cur = con.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_by_month(self, year: int, month: int,
                      employee_code: Optional[str] = None) -> List[Dict]:
        """
        指定年月の1ヶ月分をまとめて取得。
        """
        last = monthrange(year, month)[1]
        start = date(year, month, 1).strftime("%Y-%m-%d")
        end = date(year, month, last).strftime("%Y-%m-%d")
        return self.list_by_range(start, end, employee_code)

    def list_by_employee_on(self, work_date: str, employee_code: str) -> List[Dict]:
        """
        特定日・特定従業員のシフトを取得（同日複数コマを許容）。
        """
        if not self._valid_date(work_date):
            raise ValueError("work_date は YYYY-MM-DD 形式で指定してください。")
        with self._conn() as con:
            cur = con.execute("""
                SELECT id, employee_code, work_date, start_time, end_time, note, submitted_at
                  FROM shifts
                 WHERE work_date=? AND employee_code=?
                 ORDER BY start_time ASC;
            """, (work_date, employee_code))
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    # ---------------- names joined helpers ----------------
    def list_all_with_names(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        employee_code: str | None = None,
    ) -> List[Dict]:
        """
        shifts に employees を LEFT JOIN して、氏名付きで一覧を返す。
        返却カラム: id, employee_code, name, work_date, start_time, end_time, note, submitted_at
        フィルタ:
          - start_date / end_date は 'YYYY-MM-DD' 形式（どちらか片方のみでも可）
          - employee_code を指定するとその人だけ
        並び: work_date ASC, start_time ASC
        """
        where = ["1=1"]
        params: list = []

        if start_date:
            if not self._valid_date(start_date):
                raise ValueError("start_date は YYYY-MM-DD 形式で指定してください。")
            where.append("s.work_date >= ?")
            params.append(start_date)

        if end_date:
            if not self._valid_date(end_date):
                raise ValueError("end_date は YYYY-MM-DD 形式で指定してください。")
            where.append("s.work_date <= ?")
            params.append(end_date)

        if employee_code:
            where.append("s.employee_code = ?")
            params.append(employee_code)

        sql = f"""
        SELECT
            s.id,
            s.employee_code,
            IFNULL(e.name, '') AS name,
            s.work_date,
            s.start_time,
            s.end_time,
            IFNULL(s.note, '') AS note,
            s.submitted_at
        FROM shifts s
        LEFT JOIN employees e ON e.code = s.employee_code
        WHERE {" AND ".join(where)}
        ORDER BY s.work_date ASC, s.start_time ASC
        """
        with self._conn() as con:
            cur = con.execute(sql, params)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def list_all_with_names_by_month(
        self, year: int, month: int, employee_code: str | None = None
    ) -> List[Dict]:
        """
        指定年月の氏名付き一覧（list_all_with_names の月版）。
        """
        last = monthrange(year, month)[1]
        start = date(year, month, 1).strftime("%Y-%m-%d")
        end = date(year, month, last).strftime("%Y-%m-%d")
        return self.list_all_with_names(start, end, employee_code)
        # ==== 週ユーティリティ ====
    @staticmethod
    def week_range_from(anchor_yyyy_mm_dd: str) -> tuple[str, str]:
        """anchor日を含む月曜〜日曜のYYYY-MM-DD範囲を返す"""
        y, m, d = map(int, anchor_yyyy_mm_dd.split("-"))
        dt = date(y, m, d)
        monday = dt - datetime.timedelta(days=dt.weekday())  # 0=Mon
        sunday = monday + datetime.timedelta(days=6)
        return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

    def list_by_week(self, anchor_yyyy_mm_dd: str, employee_code: Optional[str] = None) -> List[Dict]:
        start, end = self.week_range_from(anchor_yyyy_mm_dd)
        return self.list_by_range(start, end, employee_code)

    # ==== 提出フラグ（範囲一括） ====
    def mark_submitted_range(self, start_date: str, end_date: str, employee_code: Optional[str] = None) -> int:
        """指定範囲（週など）をまとめて提出済みにする。戻り値は更新件数。"""
        if not (self._valid_date(start_date) and self._valid_date(end_date)):
            raise ValueError("start_date / end_date は YYYY-MM-DD 形式で指定してください。")
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as con:
            sql = "UPDATE shifts SET submitted_at=?, updated_at=(datetime('now','localtime')) WHERE work_date BETWEEN ? AND ?"
            params = [now, start_date, end_date]
            if employee_code:
                sql += " AND employee_code=?"
                params.append(employee_code)
            cur = con.execute(sql, params)
            con.commit()
            return cur.rowcount
