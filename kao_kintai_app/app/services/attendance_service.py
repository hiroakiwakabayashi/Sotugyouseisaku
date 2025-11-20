from __future__ import annotations
from typing import Optional, Set, Tuple
from datetime import date, datetime
from calendar import monthrange
from collections import defaultdict

from app.infra.db.attendance_repo import AttendanceRepo
from app.infra.db.employee_repo import EmployeeRepo


class AttendanceService:
    """
    打刻の状態遷移ガード：
      None/最後がCLOCK_OUT -> CLOCK_INのみ
      CLOCK_IN             -> BREAK_START or CLOCK_OUT
      BREAK_START          -> BREAK_END
      BREAK_END            -> BREAK_START or CLOCK_OUT
      CLOCK_OUT            -> CLOCK_IN
    """
    ALLOWED: dict[Optional[str], Set[str]] = {
        None: {"CLOCK_IN"},
        "CLOCK_IN": {"BREAK_START", "CLOCK_OUT"},
        "BREAK_START": {"BREAK_END"},
        "BREAK_END": {"BREAK_START", "CLOCK_OUT"},
        "CLOCK_OUT": {"CLOCK_IN"},
    }

    LABELS = {
        "CLOCK_IN": "出勤",
        "BREAK_START": "休憩開始",
        "BREAK_END": "休憩終了",
        "CLOCK_OUT": "退勤",
    }

    def __init__(self, repo: AttendanceRepo | None = None):
        self.repo = repo or AttendanceRepo()

    # ===== 打刻ガード関連 =====
    def last_state(self, employee_code: str) -> Optional[str]:
        last = self.repo.get_last(employee_code)
        return last["punch_type"] if last else None

    def allowed_next(self, last_type: Optional[str]) -> Set[str]:
        return self.ALLOWED.get(last_type, {"CLOCK_IN"})

    def can_punch(self, employee_code: str, new_type: str) -> Tuple[bool, str, Set[str]]:
        last = self.last_state(employee_code)
        allowed = self.allowed_next(last)
        if new_type in allowed:
            return True, "", allowed
        last_label = self.LABELS.get(last, "（未打刻）")
        want_label = self.LABELS.get(new_type, new_type)
        allowed_labels = " / ".join(self.LABELS[a] for a in allowed)
        msg = f"いまの状態（直前: {last_label}）では「{want_label}」は打刻できません。次に許可: {allowed_labels}"
        return False, msg, allowed

    def punch(self, employee_code: str, new_type: str) -> Tuple[bool, str, Set[str]]:
        ok, msg, _ = self.can_punch(employee_code, new_type)
        if not ok:
            return False, msg, self.allowed_next(self.last_state(employee_code))
        self.repo.add(employee_code=employee_code, punch_type=new_type)
        return True, f"{self.LABELS.get(new_type,new_type)} を記録しました。", self.allowed_next(new_type)

    # ===== 月次給与関連 =====
    def _ym_to_range(self, year: int, month: int) -> tuple[str, str]:
        """その月の開始/終了日(YYYY-MM-DD)を返す"""
        last_day = monthrange(year, month)[1]
        start = date(year, month, 1).strftime("%Y-%m-%d")
        end   = date(year, month, last_day).strftime("%Y-%m-%d")
        return start, end

    def calc_monthly_payroll(
        self,
        year: int,
        month: int,
        emp_repo: EmployeeRepo,
        employee_code: str | None = None
    ):
        """
        指定年月の月次給与を集計して返す。
        戻り値: list[{code, name, total_minutes, hourly_wage, amount}]
        - 実働 = (退勤 - 出勤) - 休憩合計
        - 金額 = 実働(時間) × 時給（未設定は0）
        """
        start, end = self._ym_to_range(year, month)

        if not hasattr(self.repo, "iter_logs"):
            raise AttributeError("AttendanceRepo.iter_logs() を先に実装してください。")

        logs = self.repo.iter_logs(start, end, employee_code=employee_code)

        # 時給マップ（未設定は0）
        wage_map = {e["code"]: (e.get("name", ""), float(e.get("wage") or 0.0)) for e in emp_repo.list_all()}

        # 社員ごとの積算
        total_work_min: dict[str, int] = defaultdict(int)
        current_in: dict[str, datetime] = {}      # code -> 出勤時刻
        break_start: dict[str, datetime] = {}     # code -> 休憩開始
        break_stack_min: dict[str, int] = defaultdict(int)  # 出勤〜退勤区間の休憩合計(分)

        def _to_dt(s: str) -> datetime:
            # 'YYYY-MM-DDTHH:MM:SS[.fff]' / 'YYYY-MM-DD HH:MM:SS' を許容
            s = s.replace(" ", "T")
            return datetime.fromisoformat(s)

        for r in logs:
            code = r["employee_code"]
            t = r["type"]
            ts = _to_dt(r["ts"])

            if t == "CLOCK_IN":
                current_in[code] = ts
                break_stack_min[code] = 0
                break_start.pop(code, None)

            elif t == "BREAK_START":
                if code in current_in and code not in break_start:
                    break_start[code] = ts

            elif t == "BREAK_END":
                if code in current_in and code in break_start:
                    bmin = int((ts - break_start[code]).total_seconds() // 60)
                    if bmin > 0:
                        break_stack_min[code] += bmin
                    break_start.pop(code, None)

            elif t == "CLOCK_OUT":
                if code in current_in:
                    work_min = int((ts - current_in[code]).total_seconds() // 60)
                    work_min -= break_stack_min[code]
                    if work_min > 0:
                        total_work_min[code] += work_min
                # クローズ／リセット
                current_in.pop(code, None)
                break_stack_min[code] = 0
                break_start.pop(code, None)

        # 出力整形
        out = []
        for code, minutes in total_work_min.items():
            name, wage = wage_map.get(code, ("", 0.0))
            hours = minutes / 60.0
            amount = round(hours * wage)
            out.append({
                "code": code,
                "name": name,
                "total_minutes": minutes,
                "hourly_wage": wage,
                "amount": amount,
            })

        out.sort(key=lambda x: x["amount"], reverse=True)
        return out
    
        # ==== 日別の実働/休憩 集計 ====
    def calc_daily_summary(
        self,
        start_date: str,
        end_date: str,
        emp_repo: "EmployeeRepo",
        employee_code: str | None = None,
    ):
        """
        指定期間の「日別・従業員別」の実働分 / 休憩分を集計して返す。
        戻り値: list[ {date, code, name, work_minutes, break_minutes} ] （日付昇順→コード昇順）
        ※MVP: 日またぎシフトは未対応（同日内でのIN→OUTを想定）
        """
        logs = self.repo.iter_logs(start_date, end_date, employee_code=employee_code)

        from collections import defaultdict
        # key: (code, 'YYYY-MM-DD')
        work_sum = defaultdict(int)
        break_sum = defaultdict(int)

        current_in: dict[str, datetime] = {}
        break_start: dict[str, datetime] = {}
        break_stack_min = defaultdict(int)

        def _to_dt(s: str) -> datetime:
            s = s.replace(" ", "T")
            return datetime.fromisoformat(s)

        for r in logs:
            code = r["employee_code"]
            t    = r["type"]              # ← iter_logs が 'punch_type AS type' で返す想定
            ts   = _to_dt(r["ts"])
            day_key = (code, ts.date().isoformat())

            if t == "CLOCK_IN":
                current_in[code] = ts
                break_stack_min[code] = 0
                break_start.pop(code, None)

            elif t == "BREAK_START":
                if code in current_in and code not in break_start:
                    break_start[code] = ts

            elif t == "BREAK_END":
                if code in current_in and code in break_start:
                    bmin = int((ts - break_start[code]).total_seconds() // 60)
                    if bmin > 0:
                        break_stack_min[code] += bmin
                    break_start.pop(code, None)

            elif t == "CLOCK_OUT":
                if code in current_in:
                    total = int((ts - current_in[code]).total_seconds() // 60)
                    bmin = break_stack_min[code]
                    work = max(0, total - bmin)
                    work_sum[day_key]  += work
                    break_sum[day_key] += bmin
                # クローズ
                current_in.pop(code, None)
                break_stack_min[code] = 0
                break_start.pop(code, None)

        # 従業員名マップ
        name_map = {e["code"]: e.get("name", "") for e in emp_repo.list_all()}

        out = []
        for (code, d), wmin in work_sum.items():
            out.append({
                "date": d,
                "code": code,
                "name": name_map.get(code, ""),
                "work_minutes": wmin,
                "break_minutes": break_sum.get((code, d), 0),
            })

        out.sort(key=lambda x: (x["date"], x["code"]))
        return out

