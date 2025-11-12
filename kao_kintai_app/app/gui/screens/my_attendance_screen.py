# app/gui/screens/my_attendance_screen.py
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import date, datetime
import csv

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo


# ===============================================================
# カレンダー付きエントリー（確定/キャンセル付き・同サイズボタン）
# ===============================================================
class DatePickerEntry(ctk.CTkFrame):
    """
    クリックでポップアップのカレンダーを表示。
    「確定」を押したときだけ textvariable に反映。
    フォーカスが外れたら自動で閉じる（＝反映しない）。
    """
    def __init__(self, master, textvariable=None, width=130, placeholder_text="YYYY-MM-DD"):
        super().__init__(master)
        import tkinter as tk  # 局所 import（Tk と競合しないように）

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

        # 既存ポップアップがあれば閉じる
        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            self._popup.destroy()

        # エントリー直下に表示
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.geometry(f"+{x}+{y}")
        self._popup.attributes("-topmost", True)

        # 既存値を初期選択に
        selected = None
        try:
            if self.var.get():
                selected = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            selected = None

        # カレンダー本体（“ひと月だけ”の見やすい設定）
        self._cal = Calendar(
            self._popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=(selected.year if selected else date.today().year),
            month=(selected.month if selected else date.today().month),
            day=(selected.day if selected else date.today().day),
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

        # フォーカスを失ったら閉じる（＝確定しない）
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


# 既定の打刻種別（プロジェクトで使っているもの）
TYPES_ORDER = ["CLOCK_IN", "BREAK_START", "BREAK_END", "CLOCK_OUT"]

def _today_str():
    return date.today().strftime("%Y-%m-%d")

def _yyyymm_first_last():
    d = date.today()
    first = d.replace(day=1)
    # 次月の1日-1日 = 当月末日
    if d.month == 12:
        next_first = d.replace(year=d.year + 1, month=1, day=1)
    else:
        next_first = d.replace(month=d.month + 1, day=1)
    last = next_first.fromordinal(next_first.toordinal() - 1)
    return first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")


class MyAttendanceScreen(ctk.CTkFrame):
    """
    マイ勤怠（閲覧専用）
    - 従業員選択（プルダウン）
    - 期間絞り込み（今日 / 今月 / 任意）
    - 一覧表示（時刻・種別）
    - 件数サマリ（種別ごと）
    - CSV保存
    """
    def __init__(self, master):
        super().__init__(master)

        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== タイトル =====
        ctk.CTkLabel(self, text="👤 マイ勤怠（閲覧）", font=("Meiryo UI", 18, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # ===== 条件行 =====
        cond = ctk.CTkFrame(self)
        cond.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        for i in range(10):
            cond.grid_columnconfigure(i, weight=0)
        cond.grid_columnconfigure(9, weight=1)

        # 従業員選択
        ctk.CTkLabel(cond, text="従業員:").grid(row=0, column=0, padx=(8, 4), pady=8, sticky="w")
        self.emp_values = self._build_emp_values()
        import tkinter as tk  # for StringVar
        self.emp_var = tk.StringVar(value=self.emp_values[0] if self.emp_values else "(従業員未登録)")
        self.emp_sel = ctk.CTkOptionMenu(cond, values=self.emp_values or ["(従業員未登録)"],
                                         variable=self.emp_var, width=220)
        self.emp_sel.grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # 期間（← ここをカレンダー付きエントリーに変更）
        ctk.CTkLabel(cond, text="期間:").grid(row=0, column=2, padx=(16, 4), pady=8, sticky="w")
        s0, e0 = _yyyymm_first_last()
        self.start_var = tk.StringVar(value=s0)
        self.end_var   = tk.StringVar(value=e0)

        DatePickerEntry(cond, textvariable=self.start_var, width=130).grid(
            row=0, column=3, padx=4, pady=8, sticky="w"
        )
        DatePickerEntry(cond, textvariable=self.end_var, width=130).grid(
            row=0, column=4, padx=4, pady=8, sticky="w"
        )

        ctk.CTkButton(cond, text="今日",  width=64, command=self._quick_today).grid(row=0, column=5, padx=4)
        ctk.CTkButton(cond, text="今月",  width=64, command=self._quick_month).grid(row=0, column=6, padx=4)
        ctk.CTkButton(cond, text="検索",  width=92, command=self._search).grid(row=0, column=7, padx=(12, 4))
        ctk.CTkButton(cond, text="CSV保存", width=92, command=self._export_csv).grid(row=0, column=8, padx=4)

        # ===== 一覧＋サマリ =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # ヘッダ
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        for i, h in enumerate(["日時", "種別", "メモ"]):
            ctk.CTkLabel(head, text=h, anchor="w").grid(row=0, column=i, padx=8, pady=6, sticky="w")
            head.grid_columnconfigure(i, weight=1 if i < 3 else 0)

        # スクロール領域
        self.scroll = ctk.CTkScrollableFrame(body, height=420)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self._row_widgets = []

        # サマリ
        self.summary = ctk.CTkLabel(body, text="—", anchor="w")
        self.summary.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 4))

        # 初期検索
        self._search()

    # ===== 内部ユーティリティ =====
    def _build_emp_values(self):
        # "E0001:山田 太郎" の並びでプルダウン用配列を作る
        values = []
        for r in self.emp_repo.list_all():
            values.append(f'{r["code"]}:{r["name"]}')
        if not values:
            return []
        return values

    def _get_selected_code(self) -> str | None:
        if not self.emp_values:
            return None
        v = self.emp_var.get()
        if ":" not in v:
            return None
        return v.split(":", 1)[0].strip()

    def _quick_today(self):
        t = _today_str()
        self.start_var.set(t); self.end_var.set(t)
        self._search()

    def _quick_month(self):
        s, e = _yyyymm_first_last()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    def _clear_rows(self):
        for w in self._row_widgets:
            try:
                w.destroy()
            except:
                pass
        self._row_widgets.clear()

    def _add_row(self, dt_text: str, typ: str, memo: str = ""):
        r = len(self._row_widgets)
        lbl_dt = ctk.CTkLabel(self.scroll, text=dt_text, anchor="w")
        lbl_ty = ctk.CTkLabel(self.scroll, text=typ, anchor="w")
        lbl_me = ctk.CTkLabel(self.scroll, text=memo, anchor="w")
        lbl_dt.grid(row=r, column=0, padx=8, pady=3, sticky="w")
        lbl_ty.grid(row=r, column=1, padx=8, pady=3, sticky="w")
        lbl_me.grid(row=r, column=2, padx=8, pady=3, sticky="w")
        self._row_widgets.extend([lbl_dt, lbl_ty, lbl_me])

    def _validate_dates(self) -> tuple[bool, str]:
        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        try:
            ds = datetime.strptime(s, "%Y-%m-%d")
            de = datetime.strptime(e, "%Y-%m-%d")
        except ValueError:
            return False, "日付は YYYY-MM-DD 形式で入力してください。"
        if ds > de:
            return False, "開始日が終了日より後になっています。"
        return True, ""

    # ===== 検索 =====
    def _search(self):
        self._clear_rows()
        code = self._get_selected_code()
        if not code:
            self.summary.configure(text="従業員が未選択です。従業員を登録して選択してください。")
            return
        ok, msg = self._validate_dates()
        if not ok:
            messagebox.showwarning("日付エラー", msg)
            return

        rows = self.att_repo.list_records(
            start_date=self.start_var.get(),
            end_date=self.end_var.get(),
            employee_code=code
        )
        # rows は {id, employee_code, type, ts, note? ...} を想定
        cnt = {k: 0 for k in TYPES_ORDER}
        for r in rows:
            ts = r.get("ts") or r.get("timestamp") or ""
            typ = r.get("type") or r.get("att_type") or ""
            memo = r.get("note") or ""
            # 表示
            self._add_row(ts, typ, memo)
            # 集計
            if typ in cnt:
                cnt[typ] += 1

        # サマリ表示
        total = len(rows)
        parts = [f"{k}:{cnt[k]}件" for k in TYPES_ORDER if k in cnt]
        self.summary.configure(
            text=f"表示件数: {total}  |  " + "  /  ".join(parts) if rows else "該当データはありません。"
        )

    # ===== CSV保存 =====
    def _export_csv(self):
        code = self._get_selected_code()
        if not code:
            messagebox.showwarning("CSV", "従業員を選択してください。")
            return
        ok, msg = self._validate_dates()
        if not ok:
            messagebox.showwarning("CSV", msg)
            return

        rows = self.att_repo.list_records(
            start_date=self.start_var.get(),
            end_date=self.end_var.get(),
            employee_code=code
        )
        if not rows:
            messagebox.showinfo("CSV", "出力対象のデータがありません。")
            return

        # 保存ダイアログ
        fpath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV ファイル", "*.csv")],
            initialfile=f"my_attendance_{code}_{self.start_var.get()}_{self.end_var.get()}.csv"
        )
        if not fpath:
            return

        # 書き出し（既知列＋不明列も落とさない方針）
        known = ["id", "employee_code", "type", "ts", "note"]
        extra = []
        for r in rows:
            for k in r.keys():
                if k not in known and k not in extra:
                    extra.append(k)
        headers = [*known, *extra]

        try:
            with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for r in rows:
                    w.writerow([r.get(h, "") for h in headers])
            messagebox.showinfo("CSV", "CSVを書き出しました。")
        except Exception as e:
            messagebox.showerror("CSV", f"書き出しに失敗しました。\n{e}")
