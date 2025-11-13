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

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="🗓 シフト閲覧", font=("Meiryo UI", 18, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # ===== 条件行 =====
        cond = ctk.CTkFrame(self)
        cond.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        for i in range(12):
            cond.grid_columnconfigure(i, weight=0)
        cond.grid_columnconfigure(11, weight=1)

        # 従業員選択
        ctk.CTkLabel(cond, text="従業員:").grid(row=0, column=0, padx=(8,4), pady=8, sticky="w")
        self.emp_values = ["(全員)"] + [f'{r["code"]}:{r["name"]}' for r in self.emp_repo.list_all()]
        self.emp_var = tk.StringVar(value=self.emp_values[0])
        self.emp_sel = ctk.CTkOptionMenu(cond, values=self.emp_values, variable=self.emp_var, width=200)
        self.emp_sel.grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # 期間（← カレンダー付きエントリーを使用）
        ctk.CTkLabel(cond, text="期間:").grid(row=0, column=2, padx=(16,4), pady=8, sticky="w")
        s0, e0 = _week_range()
        self.start_var = tk.StringVar(value=s0)
        self.end_var   = tk.StringVar(value=e0)
        DatePickerEntry(cond, textvariable=self.start_var, width=130).grid(row=0, column=3, padx=4, pady=8, sticky="w")
        DatePickerEntry(cond, textvariable=self.end_var,   width=130).grid(row=0, column=4, padx=4, pady=8, sticky="w")

        # 操作用ボタン（サイズ統一）
        BTN_W = 64
        ctk.CTkButton(cond, text="今日",  width=BTN_W, command=self._quick_today).grid(row=0, column=5, padx=4)
        ctk.CTkButton(cond, text="今週",  width=BTN_W, command=self._quick_week).grid(row=0, column=6, padx=4)
        ctk.CTkButton(cond, text="今月",  width=BTN_W, command=self._quick_month).grid(row=0, column=7, padx=4)
        ctk.CTkButton(cond, text="検索",  width=90, command=self._search).grid(row=0, column=8, padx=(12,4))
        ctk.CTkButton(cond, text="CSV出力", width=90, command=self._export_csv).grid(row=0, column=9, padx=4)

        # ===== 一覧 =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        titles = ["従業員コード", "氏名", "日付", "開始", "終了", "合計(h)", "メモ"]
        for i, t in enumerate(titles):
            ctk.CTkLabel(header, text=t, anchor="w").grid(row=0, column=i, padx=8, pady=6, sticky="w")
            header.grid_columnconfigure(i, weight=1 if i in (0,1,2,6) else 0)

        self.scroll = ctk.CTkScrollableFrame(body, height=420)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self._row_widgets = []

        self.summary = ctk.CTkLabel(body, text="—", anchor="w")
        self.summary.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 4))

        # 初回検索
        self._search()

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

    def _clear_rows(self):
        for w in self._row_widgets:
            try:
                w.destroy()
            except:
                pass
        self._row_widgets.clear()

    def _add_row(self, code, name, work_date, start, end, hours, note):
        r = len(self._row_widgets)//7
        cells = [
            ctk.CTkLabel(self.scroll, text=code, anchor="w"),
            ctk.CTkLabel(self.scroll, text=name, anchor="w"),
            ctk.CTkLabel(self.scroll, text=work_date, anchor="w"),
            ctk.CTkLabel(self.scroll, text=start, anchor="w"),
            ctk.CTkLabel(self.scroll, text=end, anchor="w"),
            ctk.CTkLabel(self.scroll, text=f"{hours:.2f}", anchor="e"),
            ctk.CTkLabel(self.scroll, text=note, anchor="w"),
        ]
        for i, c in enumerate(cells):
            c.grid(row=r, column=i, padx=8, pady=3, sticky="ew" if i in (0,1,2,6) else "w")
            self._row_widgets.append(c)

    # ==== actions ====
    def _search(self):
        self._clear_rows()

        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        try:
            ds = datetime.strptime(s, "%Y-%m-%d")
            de = datetime.strptime(e, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("日付エラー", "日付は YYYY-MM-DD 形式で入力してください。")
            return
        if ds > de:
            messagebox.showwarning("日付エラー", "開始日が終了日より後になっています。")
            return

        code = self._emp_code()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)

        # 名前キャッシュ
        name_map = {r["code"]: r["name"] for r in self.emp_repo.list_all()}

        total_hours = 0.0
        for r in rows:
            st_m = _hhmm_to_minutes(r["start_time"])
            en_m = _hhmm_to_minutes(r["end_time"])
            mins = max(0, en_m - st_m)
            h = mins / 60.0
            total_hours += h

            code = r["employee_code"]
            name = name_map.get(code, "")
            self._add_row(
                code=code,
                name=name,
                work_date=r["work_date"],
                start=r["start_time"],
                end=r["end_time"],
                hours=h,
                note=r.get("note", "")
            )

        self.summary.configure(text=f"件数: {len(rows)}  / 合計時間: {total_hours:.2f} h")

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
