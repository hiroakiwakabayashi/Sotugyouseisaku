from __future__ import annotations
from typing import Optional, Set, Tuple
from app.infra.db.attendance_repo import AttendanceRepo

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
        # エラーメッセージ
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
        # 新状態に基づく次の許可
        return True, f"{self.LABELS.get(new_type,new_type)} を記録しました。", self.allowed_next(new_type)
