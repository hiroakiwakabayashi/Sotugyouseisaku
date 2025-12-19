# app/gui/screens/shift_view_screen.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import date, datetime, timedelta
import csv

from app.infra.db.shift_repo import ShiftRepo
from app.infra.db.employee_repo import EmployeeRepo


# =========================
# 共通: カレンダー付き入力
# =========================
class DatePickerEntry(ctk.CTkFrame):
    """
    クリックでポップアップのカレンダーを表示。
    「確定」を押した時だけ textvariable に反映。
    フォーカス外れ・キャンセル時は反映しない。
    """
    def __init__(self, master, textvariable=None, width=130, placeholder_text="YYYY-MM-DD"):
        super().__init__(master)
        import tkinter as tk

        self.var = textvariable or tk.StringVar()
        self.entry = ctk.CTkEntry(
            self, width=width, textvariable=self.var,
            placeholder_text=placeholder_text, state="readonly"
        )
        self.entry.pack(side="left", fill="x")
        self.entry.bind("<Button-1>", self._open_popup)

        self.btn = ctk.CTkButton(self, text="📅", width=34, command=self._open_popup)
        self.btn.pack(side="left", padx=4)

        self._popup = None
        self._cal = None

    def _open_popup(self, *_):
        import tkinter as tk
        from tkcalendar import Calendar

        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            self._popup.destroy()

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.geometry(f"+{x}+{y}")
        self._popup.attributes("-topmost", True)

        # 既存値で初期化
        sel = None
        try:
            if self.var.get():
                sel = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            sel = None

        # “ひと月だけ”の見やすい設定
        self._cal = Calendar(
            self._popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=(sel.year if sel else date.today().year),
            month=(sel.month if sel else date.today().month),
            day=(sel.day if sel else date.today().day),
            locale="ja_JP",
            font=("Meiryo UI", 15),
            showweeknumbers=False,
            showothermonthdays=False,
            background="#FFFFFF",
            foreground="#111111",
            headersbackground="#E5E7EB",
            headersforeground="#111111",
            weekendbackground="#F8FAFC",
            weekendforeground="#111111",
            selectbackground="#2563EB",
            selectforeground="#FFFFFF",
            bordercolor="#CBD5E1",
            normalbackground="#FFFFFF",
            normalforeground="#111111",
        )
        self._cal.pack(padx=8, pady=(8, 4))

        # 同サイズボタン
        BTN_W, BTN_H = 110, 36
        btns = ctk.CTkFrame(self._popup)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(btns, text="確定", width=BTN_W, height=BTN_H, command=self._ok)\
            .pack(side="left", padx=(30, 8), pady=4)
        ctk.CTkButton(btns, text="キャンセル", width=BTN_W, height=BTN_H, command=self._cancel)\
            .pack(side="right", padx=(8, 30), pady=4)

        self._popup.focus_force()
        self._popup.bind("<FocusOut>", lambda e: self._cancel())

    def _ok(self):
        if self._cal:
            self.var.set(self._cal.get_date())
        self._cancel()

    def _cancel(self):
        import tkinter as tk
        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            self._popup.destroy()
        self._popup = None
        self._cal = None


def _today_str():
    return date.today().strftime("%Y-%m-%d")

def _week_range():
    d = date.today()
    start = d - timedelta(days=d.weekday())  # 月曜はじめ
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def _month_range():
    d = date.today().replace(day=1)
    if d.month == 12:
        next_first = d.replace(year=d.year+1, month=1, day=1)
    else:
        next_first = d.replace(month=d.month+1, day=1)
    last = next_first - timedelta(days=1)
    return d.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")

def _hhmm_to_minutes(hhmm: str) -> int:
    try:
        h, m = map(int, hhmm.split(":"))
        return h*60 + m
    except Exception:
        return 0


class ShiftViewScreen(ctk.CTkFrame):
    """シフト閲覧（読み取り専用）
        - 従業員選択（空=全員）
        - 期間絞り込み（今日 / 今週 / 今月 / 任意）
        - 一覧表示（日付・開始・終了・合計時間・メモ）
        - 件数/合計時間サマリ
        - CSV出力
    """
    def __init__(self, master):
        super().__init__(master)
        import tkinter as tk  # StringVar 用

        self.shift_repo = ShiftRepo()
        self.emp_repo = EmployeeRepo()

        # ★ 件数 / 合計時間 表示用
        self.count_var = tk.StringVar(value="0 件")
        self.total_hours_var = tk.StringVar(value="合計時間: 0.00 h")

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="🗓 シフト閲覧", font=("Meiryo UI", 22, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # ===== 条件行 =====
        filt = ctk.CTkFrame(self)
        filt.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        filt.grid_columnconfigure(0, weight=1)

        BTN_H = 32  # ボタン高さ（勤怠一覧と揃える）

        # ---------- 1段目：従業員 / 開始日 / 終了日 ----------
        row1 = ctk.CTkFrame(filt, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew")
        for c in range(3):
            row1.grid_columnconfigure(c, weight=1)

        # 従業員グループ
        emp_box = ctk.CTkFrame(row1, fg_color="transparent")
        emp_box.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(emp_box, text="従業員").pack(side="left", padx=(0, 4))
        self.emp_values = ["(全員)"] + [
            f'{r["code"]}:{r["name"]}' for r in self.emp_repo.list_all()
        ]
        self.emp_var = tk.StringVar(value=self.emp_values[0])
        self.emp_sel = ctk.CTkOptionMenu(
            emp_box,
            values=self.emp_values,
            variable=self.emp_var,
            width=220,
        )
        self.emp_sel.pack(side="left")

        # 開始日グループ
        start_box = ctk.CTkFrame(row1, fg_color="transparent")
        start_box.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(start_box, text="開始日").pack(side="left", padx=(0, 4))
        s0, e0 = _week_range()
        self.start_var = tk.StringVar(value=s0)
        DatePickerEntry(start_box, textvariable=self.start_var, width=130).pack(
            side="left"
        )

        # 終了日グループ
        end_box = ctk.CTkFrame(row1, fg_color="transparent")
        end_box.grid(row=0, column=2, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(end_box, text="終了日").pack(side="left", padx=(0, 4))
        self.end_var = tk.StringVar(value=e0)
        DatePickerEntry(end_box, textvariable=self.end_var, width=130).pack(
            side="left"
        )

        # ---------- 2段目：クイックボタン列（均等3分割） ----------
        row2 = ctk.CTkFrame(filt, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        for c in range(3):
            row2.grid_columnconfigure(c, weight=1)

        quick_buttons = [
            ("今日", self._quick_today),
            ("今週", self._quick_week),
            ("今月", self._quick_month),
        ]
        for col, (label, cmd) in enumerate(quick_buttons):
            ctk.CTkButton(
                row2,
                text=label,
                height=BTN_H,
                command=cmd,
                font=("Meiryo UI", 15, "bold"),
            ).grid(row=0, column=col, padx=4, pady=(2, 4), sticky="ew")

        # ===== 一覧（Treeview） =====
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        # ===== 一覧（Treeview） =====
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        from tkinter import ttk

        self.tree = ttk.Treeview(
            table_wrap,
            columns=("code", "name", "date", "start", "end", "hours", "note"),
            show="headings",
            height=18,
        )

        self.tree.heading("code",  text="従業員コード")
        self.tree.heading("name",  text="氏名")
        self.tree.heading("date",  text="日付")
        self.tree.heading("start", text="開始")
        self.tree.heading("end",   text="終了")
        self.tree.heading("hours", text="合計(h)")
        self.tree.heading("note",  text="メモ")

        self.tree.column("code",  width=130, anchor="center")
        self.tree.column("name",  width=150, anchor="center")
        self.tree.column("date",  width=110, anchor="center")
        self.tree.column("start", width=80,  anchor="center")
        self.tree.column("end",   width=80,  anchor="center")
        self.tree.column("hours", width=90,  anchor="center")
        self.tree.column("note",  width=200, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        # ゼブラ柄（勤怠一覧と統一）
        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd",  background="#F9FAFB")

        # 初回検索
        self._search()

        # ===== 件数 / 合計時間 + CSV（勤怠一覧風） =====
        meta = ctk.CTkFrame(self)
        meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        meta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            meta,
            textvariable=self.count_var,
            font=("Meiryo UI", 14),
        ).pack(side="left", padx=6)
        ctk.CTkLabel(
            meta,
            textvariable=self.total_hours_var,
            font=("Meiryo UI", 14),
        ).pack(side="left", padx=16)
        ctk.CTkButton(
            meta,
            text="CSV出力",
            command=self._export_csv,
            width=120,
        ).pack(side="right", padx=4)

    # ==== helpers ====
    def _emp_code(self):
        v = self.emp_var.get()
        return None if v == "(全員)" else v.split(":", 1)[0].strip()

    def _quick_today(self):
        t = _today_str()
        self.start_var.set(t); self.end_var.set(t)
        self._search()

    def _quick_week(self):
        s, e = _week_range()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    def _quick_month(self):
        s, e = _month_range()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    def _search(self):
        # データ取得
        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        try:
            datetime.strptime(s, "%Y-%m-%d")
            datetime.strptime(e, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("日付エラー", "日付形式が不正です。")
            return

        code = self._emp_code()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)

        # 名前キャッシュ
        name_map = {r["code"]: r["name"] for r in self.emp_repo.list_all()}

        # Treeview クリア
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # 挿入
        total_hours = 0.0
        for i, r in enumerate(rows):
            st = _hhmm_to_minutes(r["start_time"])
            en = _hhmm_to_minutes(r["end_time"])
            h = max(0, en - st) / 60.0
            total_hours += h

            tag = "even" if i % 2 == 0 else "odd"

            self.tree.insert(
                "",
                "end",
                values=(
                    r["employee_code"],
                    name_map.get(r["employee_code"], ""),
                    r["work_date"],
                    r["start_time"],
                    r["end_time"],
                    f"{h:.2f}",
                    r.get("note", "")
                ),
                tags=(tag,),
            )

            # 下部表示更新
            self.count_var.set(f"{len(rows)} 件")
            self.total_hours_var.set(f"合計時間: {total_hours:.2f} h")

    def _export_csv(self):
        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        code = self._emp_code()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)
        if not rows:
            messagebox.showinfo("CSV", "出力対象データがありません。")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSVファイル","*.csv")],
            initialfile=f"shifts_{code or 'all'}_{s}_{e}.csv"
        )
        if not path:
            return

        headers = ["id","employee_code","work_date","start_time","end_time","note"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers + ["hours"])
                for r in rows:
                    st = _hhmm_to_minutes(r["start_time"])
                    en = _hhmm_to_minutes(r["end_time"])
                    h  = max(0, en - st) / 60.0
                    w.writerow([r.get(k,"") for k in headers] + [f"{h:.2f}"])
            messagebox.showinfo("CSV", "CSVを書き出しました。")
        except Exception as ex:
            messagebox.showerror("CSV", f"書き出しに失敗しました。\n{ex}")
