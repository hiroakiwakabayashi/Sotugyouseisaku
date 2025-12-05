# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import date, timedelta
import re

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.shift_repo import ShiftRepo

# =========================
# 時刻ユーティリティ（要件対応）
# =========================

_COMPACT = re.compile(r"^\d{3,4}$")      # 600 / 0900 / 1730
_HHMM = re.compile(r"^\d{2}:\d{2}$")     # 06:00 / 17:30

def _from_db_to_compact(hhmm: str) -> str:
    """'HH:MM' → 'HMM/HHMM'（先頭0を落としてコロン無し）"""
    if not _HHMM.match(hhmm):
        return hhmm  # 想定外はそのまま返す
    hh, mm = hhmm.split(":")
    h = str(int(hh))  # 先頭ゼロ除去（'00'→'0'）
    return f"{h}{mm}"

def _compact_to_hhmm(s: str) -> str | None:
    """
    '600' / '0900' / '1730' → 'HH:MM' に正規化。
    不正なら None を返す。
    """
    if not s:
        return None
    s = s.strip()
    if not _COMPACT.match(s):
        return None
    # 後ろ2桁が分、前が時
    mm = int(s[-2:])
    hh = int(s[:-2])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return f"{hh:02d}:{mm:02d}"

def _lt_hhmm(a: str, b: str) -> bool:
    """a < b を 'HH:MM' で判定（双方とも 'HH:MM' 前提）"""
    ah, am = map(int, a.split(":"))
    bh, bm = map(int, b.split(":"))
    return (ah, am) < (bh, bm)


class ShiftSubmitScreen(ctk.CTkFrame):
    """
    従業員が週次でシフトを「希望提出」する画面。
    - 入力形式は HHMM（コロン無し）。例: 600, 900, 1730
    - 第1希望 IN/OUT（必須扱いではないが、両方埋まっていないと登録しない）
    - 第2希望 IN/OUT（任意。両方埋まっているときだけ登録）
    - DB保存時は 'HH:MM' に正規化して保存
    """

    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.shift_repo = ShiftRepo()

        # 週の基準（表示開始日＝週の月曜日）
        today = date.today()
        self.week_start = today - timedelta(days=(today.weekday() % 7))  # 月曜=0

        # 従業員選択
        self.emp_var = tk.StringVar()
        emp_opts = self._employee_options()
        if emp_opts:
            self.emp_var.set(emp_opts[0])

        # レイアウト
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="🗓 シフト提出（週次 / 第1・第2希望、時刻はHHMM入力）",
            font=("Meiryo UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        # ツールバー（従業員・週移動）
        bar = ctk.CTkFrame(self)
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(bar, text="従業員").grid(
            row=0, column=0, padx=(8, 4), pady=6, sticky="e"
        )
        self.emp_menu = ctk.CTkOptionMenu(
            bar, variable=self.emp_var, values=emp_opts, width=250
        )
        self.emp_menu.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        prev_btn = ctk.CTkButton(
            bar, text="◀ 前の週", command=lambda: self._move_week(-7), width=110, height=34
        )
        next_btn = ctk.CTkButton(
            bar, text="次の週 ▶", command=lambda: self._move_week(+7), width=110, height=34
        )
        self.week_label = ctk.CTkLabel(bar, text="", font=("Meiryo UI", 14, "bold"))

        prev_btn.grid(row=0, column=2, padx=6, pady=6)
        next_btn.grid(row=0, column=3, padx=6, pady=6)
        self.week_label.grid(row=0, column=4, padx=6, pady=6, sticky="w")

        # ===== 行コンテナ（ヘッダ＋7日分） =====
        self.rows = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.rows.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))

        # 0:日付, 1:第1IN, 2:第1OUT, 3:第2IN, 4:第2OUT, 5:メモ
        self.rows.grid_columnconfigure(0, weight=0, minsize=150)
        for col in (1, 2, 3, 4):
            self.rows.grid_columnconfigure(col, weight=0, minsize=110)
        self.rows.grid_columnconfigure(5, weight=1)

        # 操作用ボタン
        foot = ctk.CTkFrame(self)
        foot.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        foot.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            foot,
            text="この週を保存",
            command=self._save_week,
            height=40,
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
        ).pack(side="right", padx=6)

        # 週表示・行構築
        self._build_week_rows()

    # ---------------- 支援 ----------------
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows]

    def _selected_code(self) -> str | None:
        v = self.emp_var.get()
        if not v:
            return None
        return v.split(" ")[0] if " " in v else v

    def _move_week(self, days: int):
        self.week_start += timedelta(days=days)
        self._build_week_rows()

    def _week_label_text(self):
        s = self.week_start
        e = self.week_start + timedelta(days=6)
        return f"{s.strftime('%Y/%m/%d')} 〜 {e.strftime('%Y/%m/%d')}"

    # ---------------- 行構築 ----------------
    def _build_week_rows(self):
        # クリア
        for w in self.rows.winfo_children():
            w.destroy()

        # 週ラベル更新
        self.week_label.configure(text=self._week_label_text())

        # ==== ヘッダ行（row=0）====
        header_titles = ["日付", "第1希望 IN", "第1希望 OUT", "第2希望 IN", "第2希望 OUT", "メモ"]
        for col, text in enumerate(header_titles):
            ctk.CTkLabel(
                self.rows,
                text=text,
                font=("Meiryo UI", 13, "bold"),
                text_color="#4B5563",
            ).grid(row=0, column=col, padx=6, pady=(6, 4), sticky="w")

        # 行エディット用保持: {date_str: {...widgets}}
        self._editors: dict[str, dict[str, ctk.CTkEntry]] = {}

        # 7日分作成（row=1〜7）
        for i in range(7):
            d = self.week_start + timedelta(days=i)
            self._add_day_row(d, row_index=i + 1)

        # 既存データを反映
        self._fill_from_db()

    def _add_day_row(self, day: date, row_index: int):
        dstr = day.strftime("%Y-%m-%d")
        editors = {}
        self._editors[dstr] = editors

        # 日付ラベル
        ctk.CTkLabel(
            self.rows,
            text=day.strftime("%Y-%m-%d (%a)"),
            font=("Meiryo UI", 13, "bold"),
            text_color="#111827",
        ).grid(row=row_index, column=0, padx=6, pady=4, sticky="w")

        # エントリ生成ヘルパ（placeholder は HHMM）
        def _mk_entry(col: int, placeholder: str = "HHMM", width: int = 96):
            e = ctk.CTkEntry(self.rows, placeholder_text=placeholder, width=width)
            e.grid(row=row_index, column=col, padx=6, pady=4, sticky="w")
            return e

        editors["in1"] = _mk_entry(1)
        editors["out1"] = _mk_entry(2)
        editors["in2"] = _mk_entry(3)
        editors["out2"] = _mk_entry(4)
        editors["note"] = ctk.CTkEntry(self.rows, placeholder_text="メモ（任意）", width=260)
        editors["note"].grid(row=row_index, column=5, padx=6, pady=4, sticky="ew")

    def _fill_from_db(self):
        code = self._selected_code()
        if not code:
            return
        s = self.week_start
        e = s + timedelta(days=6)
        rows = self.shift_repo.list_by_range(
            s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), employee_code=code
        )

        # 同日のレコードを時間順にして第1/第2へ割り振る
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            by_day.setdefault(r["work_date"], []).append(r)

        def _key(r):
            return (r["start_time"], r["end_time"])

        for d, lst in by_day.items():
            lst.sort(key=_key)
            ed = self._editors.get(d)
            if not ed:
                continue
            if len(lst) >= 1:
                ed["in1"].delete(0, tk.END)
                ed["in1"].insert(0, _from_db_to_compact(lst[0]["start_time"]))
                ed["out1"].delete(0, tk.END)
                ed["out1"].insert(0, _from_db_to_compact(lst[0]["end_time"]))
                if lst[0].get("note"):
                    ed["note"].delete(0, tk.END)
                    ed["note"].insert(0, lst[0]["note"])
            if len(lst) >= 2:
                ed["in2"].delete(0, tk.END)
                ed["in2"].insert(0, _from_db_to_compact(lst[1]["start_time"]))
                ed["out2"].delete(0, tk.END)
                ed["out2"].insert(0, _from_db_to_compact(lst[1]["end_time"]))

    # ---------------- 保存 ----------------
    def _save_week(self):
        code = self._selected_code()
        if not code:
            messagebox.showwarning("従業員", "従業員を選択してください。")
            return

        items = []  # (id, code, work_date, start_time, end_time, note)
        errors = []

        for dkey, ed in self._editors.items():
            in1_raw = ed["in1"].get().strip()
            out1_raw = ed["out1"].get().strip()
            in2_raw = ed["in2"].get().strip()
            out2_raw = ed["out2"].get().strip()
            note = ed["note"].get().strip()

            # 第1希望（両方埋まっているときだけ登録対象）
            if in1_raw or out1_raw:
                in1 = _compact_to_hhmm(in1_raw)
                out1 = _compact_to_hhmm(out1_raw)
                if not (in1 and out1 and _lt_hhmm(in1, out1)):
                    errors.append(f"{dkey} 第1希望は HHMM / IN<OUT で入力してください。例: 600, 930, 1730")
                else:
                    items.append((None, code, dkey, in1, out1, note))

            # 第2希望（任意／両方埋まっているときだけ登録対象）
            if in2_raw or out2_raw:
                in2 = _compact_to_hhmm(in2_raw)
                out2 = _compact_to_hhmm(out2_raw)
                if not (in2 and out2 and _lt_hhmm(in2, out2)):
                    errors.append(f"{dkey} 第2希望は HHMM / IN<OUT で入力してください。例: 600, 930, 1730")
                else:
                    items.append((None, code, dkey, in2, out2, note))

        if errors:
            messagebox.showwarning(
                "入力チェック",
                "\n".join(errors[:8]) + ("\n…他" if len(errors) > 8 else ""),
            )
            return

        if not items:
            if messagebox.askyesno("確認", "入力が空です。この週の既存シフトをすべて削除しますか？"):
                self._delete_all_in_week(code)
                messagebox.showinfo("シフト", "この週のシフトを削除しました。")
                self._build_week_rows()
            return

        # 週の既存シフトを削除してから一括保存（上書き）
        self._delete_all_in_week(code)
        self.shift_repo.upsert_many(items)
        messagebox.showinfo("シフト", "この週のシフトを保存しました。")
        self._build_week_rows()

    def _delete_all_in_week(self, code: str):
        s = self.week_start
        e = s + timedelta(days=6)
        exists = self.shift_repo.list_by_range(
            s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), employee_code=code
        )
        for r in exists:
            self.shift_repo.delete(r["id"])
