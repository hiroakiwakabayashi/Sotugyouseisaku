# app/gui/screens/shift_editor_screen.py
import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta
from typing import Optional

from app.infra.db.shift_repo import ShiftRepo
from app.infra.db.employee_repo import EmployeeRepo

__all__ = ["ShiftEditorScreen"]


def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def _week_range_str():
    d = date.today()
    start = d - timedelta(days=d.weekday())  # 月曜はじめ
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


class ShiftEditorScreen(ctk.CTkFrame):
    """シフト作成 / 編集（su向け）
       - 期間検索（今日 / 今週 / 任意）
       - 従業員絞り込み（空=全員）
       - 行追加、選択行の保存（追加/更新）、削除
    """
    def __init__(self, master):
        super().__init__(master)
        self.shift_repo = ShiftRepo()
        self.emp_repo = EmployeeRepo()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="🗓 シフト作成・編集", font=("Meiryo UI", 18, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # ===== 条件エリア =====
        cond = ctk.CTkFrame(self)
        cond.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        for i in range(12):
            cond.grid_columnconfigure(i, weight=0)
        cond.grid_columnconfigure(11, weight=1)

        # 従業員プルダウン（空=全員）
        ctk.CTkLabel(cond, text="従業員:").grid(row=0, column=0, padx=(8,4), pady=8, sticky="w")
        self.emp_values = ["(全員)"] + [f'{r["code"]}:{r["name"]}' for r in self.emp_repo.list_all()]
        self.emp_var = ctk.StringVar(value=self.emp_values[0])
        ctk.CTkOptionMenu(cond, values=self.emp_values, variable=self.emp_var, width=220)\
            .grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # 期間
        ctk.CTkLabel(cond, text="期間:").grid(row=0, column=2, padx=(16,4), pady=8, sticky="w")
        s0, e0 = _week_range_str()
        self.start_var = ctk.StringVar(value=s0)
        self.end_var   = ctk.StringVar(value=e0)
        ctk.CTkEntry(cond, width=120, textvariable=self.start_var, placeholder_text="YYYY-MM-DD")\
            .grid(row=0, column=3, padx=4, pady=8, sticky="w")
        ctk.CTkEntry(cond, width=120, textvariable=self.end_var,   placeholder_text="YYYY-MM-DD")\
            .grid(row=0, column=4, padx=4, pady=8, sticky="w")

        ctk.CTkButton(cond, text="今日",  width=70, command=self._quick_today).grid(row=0, column=5, padx=4)
        ctk.CTkButton(cond, text="今週",  width=70, command=self._quick_week).grid(row=0, column=6, padx=4)
        ctk.CTkButton(cond, text="検索",  width=90, command=self._search).grid(row=0, column=7, padx=(12,4))
        ctk.CTkButton(cond, text="追加行", width=90, command=self._new_row).grid(row=0, column=8, padx=4)

        # ===== 一覧（スクロール） =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        titles = ["", "ID", "従業員コード", "日付", "開始", "終了", "メモ"]
        for i, t in enumerate(titles):
            ctk.CTkLabel(head, text=t, anchor="w").grid(row=0, column=i, padx=8, pady=6, sticky="w")
            head.grid_columnconfigure(i, weight=1 if i in (2,3,6) else 0)

        self.scroll = ctk.CTkScrollableFrame(body, height=420, fg_color="#ECEFF1")
        self.scroll.grid(row=1, column=0, sticky="nsew")

        # 操作ボタン
        ops = ctk.CTkFrame(self)
        ops.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(ops, text="選択行を保存（追加/更新）", command=self._save_selected)\
            .pack(side="left", padx=6, pady=6)
        ctk.CTkButton(ops, text="選択行を削除", fg_color="#E74C3C", hover_color="#C0392B", command=self._delete_selected)\
            .pack(side="left", padx=6, pady=6)

        # 行ウィジェット保持
        self._rows = []     # [{id, widgets, map}, ...]
        self._row_count = 0

        self._search()

    # ===== クイック期間 =====
    def _quick_today(self):
        t = _today_str()
        self.start_var.set(t); self.end_var.set(t)
        self._search()

    def _quick_week(self):
        s, e = _week_range_str()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    # ===== 行管理 =====
    def _clear_rows(self):
        for r in self._rows:
            for w in r["widgets"]:
                try: w.destroy()
                except: pass
        self._rows.clear()
        self._row_count = 0

    def _add_row(self, *, id: Optional[int], employee_code: str, work_date: str,
                 start_time: str, end_time: str, note: str):
        rindex = self._row_count

        # カード化（見やすさ）
        card = ctk.CTkFrame(self.scroll, corner_radius=10, border_width=2,
                            border_color="#B8C1CC", fg_color="#FFFFFF")
        card.grid(row=rindex, column=0, sticky="ew", padx=10, pady=6)
        for i in (0,2,3,6):
            card.grid_columnconfigure(i, weight=1)

        # チェック
        sel = ctk.CTkCheckBox(card, text="")
        sel.grid(row=0, column=0, padx=8, pady=8, sticky="w")

        # ID（表示のみ）
        id_lbl = ctk.CTkLabel(card, text=str(id) if id else "-")
        id_lbl.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        code_e = ctk.CTkEntry(card, width=140)
        code_e.insert(0, employee_code)
        code_e.grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        date_e = ctk.CTkEntry(card, width=120, placeholder_text="YYYY-MM-DD")
        date_e.insert(0, work_date)
        date_e.grid(row=0, column=3, padx=8, pady=8, sticky="ew")

        st_e = ctk.CTkEntry(card, width=80, placeholder_text="HH:MM")
        st_e.insert(0, start_time)
        st_e.grid(row=0, column=4, padx=8, pady=8, sticky="w")

        en_e = ctk.CTkEntry(card, width=80, placeholder_text="HH:MM")
        en_e.insert(0, end_time)
        en_e.grid(row=0, column=5, padx=8, pady=8, sticky="w")

        note_e = ctk.CTkEntry(card, width=260)
        note_e.insert(0, note)
        note_e.grid(row=0, column=6, padx=8, pady=8, sticky="ew")

        self._rows.append({
            "id": id,
            "widgets": [card, sel, id_lbl, code_e, date_e, st_e, en_e, note_e],
            "map": {"sel": sel, "code": code_e, "date": date_e, "st": st_e, "en": en_e, "note": note_e}
        })
        self._row_count += 1

    # ===== 入出力 =====
    def _selected_maps(self):
        out = []
        for r in self._rows:
            if r["map"]["sel"].get():
                out.append({
                    "id": r["id"],
                    "employee_code": r["map"]["code"].get().strip(),
                    "work_date":     r["map"]["date"].get().strip(),
                    "start_time":    r["map"]["st"].get().strip(),
                    "end_time":      r["map"]["en"].get().strip(),
                    "note":          r["map"]["note"].get().strip(),
                })
        return out

    def _validate(self, m: dict) -> tuple[bool, str]:
        if not m["employee_code"]:
            return False, "従業員コードが未入力です。"
        d = m["work_date"]
        if len(d) != 10 or d[4] != "-" or d[7] != "-":
            return False, "日付は YYYY-MM-DD 形式で入力してください。"
        for k in ("start_time", "end_time"):
            t = m[k]
            if len(t) != 5 or t[2] != ":":
                return False, f"{('開始','終了')[k=='end_time']}は HH:MM 形式で入力してください。"
        if m["start_time"] >= m["end_time"]:
            return False, "開始≧終了 になっています。"
        return True, ""

    # ===== 動作 =====
    def _new_row(self):
        # 絞り込みの従業員・日付を初期値に
        v = self.emp_var.get()
        code = None if v == "(全員)" else v.split(":", 1)[0].strip()
        code = code or ""
        day = self.start_var.get() if self.start_var.get() == self.end_var.get() else _today_str()
        self._add_row(id=None, employee_code=code, work_date=day,
                      start_time="09:00", end_time="18:00", note="")

    def _search(self):
        self._clear_rows()
        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        v = self.emp_var.get()
        code = None if v == "(全員)" else v.split(":", 1)[0].strip()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)
        for r in rows:
            self._add_row(id=r["id"], employee_code=r["employee_code"], work_date=r["work_date"],
                          start_time=r["start_time"], end_time=r["end_time"], note=r.get("note",""))

    def _save_selected(self):
        items = self._selected_maps()
        if not items:
            messagebox.showwarning("保存", "保存対象の行にチェックを入れてください。")
            return
        for m in items:
            ok, msg = self._validate(m)
            if not ok:
                messagebox.showwarning("入力エラー", msg)
                return
        for m in items:
            rid = self.shift_repo.upsert(
                id=m["id"], employee_code=m["employee_code"], work_date=m["work_date"],
                start_time=m["start_time"], end_time=m["end_time"], note=m["note"]
            )
        messagebox.showinfo("保存", f"{len(items)} 件を保存しました。")
        self._search()

    def _delete_selected(self):
        items = self._selected_maps()
        if not items:
            messagebox.showwarning("削除", "削除対象の行にチェックを入れてください。")
            return
        if messagebox.askyesno("確認", f"{len(items)} 件を削除します。よろしいですか？") is False:
            return
        for m in items:
            if m["id"]:
                self.shift_repo.delete(m["id"])
        messagebox.showinfo("削除", f"{len(items)} 件を削除しました。")
        self._search()
