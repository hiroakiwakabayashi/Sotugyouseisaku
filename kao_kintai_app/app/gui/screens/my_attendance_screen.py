#C kao_kintai_app\app\gui\screens\my_attendance_screen.py

# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
import csv

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo
from app.services.attendance_service import AttendanceService


# ===============================================================
# カレンダー付きエントリー（読み取り専用 + 確定/キャンセル）
# ===============================================================
class DatePickerEntry(ctk.CTkFrame):
    def __init__(self, master, textvariable: tk.StringVar | None = None,
                width=130, placeholder_text="YYYY-MM-DD"):
        super().__init__(master)
        self.var = textvariable or tk.StringVar()

        self.entry = ctk.CTkEntry(
            self, textvariable=self.var, width=width,
            placeholder_text=placeholder_text, state="readonly"
        )
        self.entry.pack(side="left", fill="x")
        self.entry.bind("<Button-1>", self._open)

        self.btn = ctk.CTkButton(self, text="📅", width=34, command=self._open)
        self.btn.pack(side="left", padx=4)

        self.popup: tk.Toplevel | None = None
        self.cal = None

    def _open(self, *_):
        from tkcalendar import Calendar

        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            self.popup.destroy()

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self.popup = tk.Toplevel(self)
        self.popup.overrideredirect(True)
        self.popup.geometry(f"+{x}+{y}")
        self.popup.attributes("-topmost", True)

        selected = None
        try:
            if self.var.get():
                selected = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            selected = None

        self.cal = Calendar(
            self.popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=(selected.year if selected else date.today().year),
            month=(selected.month if selected else date.today().month),
            day=(selected.day if selected else date.today().day),
            locale="ja_JP",
            font=("Meiryo UI", 15),
            showweeknumbers=False,
            showothermonthdays=False,
        )
        self.cal.pack(padx=8, pady=(8, 4))

        CAL_BTN_W, CAL_BTN_H = 110, 36
        btns = ctk.CTkFrame(self.popup)
        btns.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkButton(btns, text="確定", width=CAL_BTN_W, height=CAL_BTN_H, command=self._ok)\
            .pack(side="left", padx=(30, 8), pady=4)
        ctk.CTkButton(btns, text="キャンセル", width=CAL_BTN_W, height=CAL_BTN_H, command=self._cancel)\
            .pack(side="right", padx=(8, 30), pady=4)

        self.popup.focus_force()
        self.popup.bind("<FocusOut>", lambda e: self._cancel())

    def _ok(self):
        if self.cal:
            self.var.set(self.cal.get_date())
        self._cancel()

    def _cancel(self):
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            self.popup.destroy()
        self.popup = None
        self.cal = None


# ===============================================================
# マイ勤怠（日別：実働/休憩 集計 + CSV）
# ===============================================================
class MyAttendanceScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()
        self.svc = AttendanceService(self.att_repo)

        # UI変数
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        # 従業員はドロップダウンから選択（ログイン概念なしMVP）
        self.emp_var = tk.StringVar()

        # 合計表示
        self.sum_work_var = tk.StringVar(value="実働合計: 0.00 h")
        self.sum_break_var = tk.StringVar(value="休憩合計: 0.00 h")

        # レイアウト
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="👤 マイ勤怠（日別 実働 / 休憩 集計）", font=("Meiryo UI", 22, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 8)
        )

        # フィルタ行
        filt = ctk.CTkFrame(self)
        filt.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        for i in range(12):
            filt.grid_columnconfigure(i, weight=0)
        filt.grid_columnconfigure(11, weight=1)

        # 従業員
        ctk.CTkLabel(filt, text="従業員").grid(row=0, column=0, padx=(8, 4), pady=6, sticky="e")
        self.emp_menu = ctk.CTkOptionMenu(filt, values=self._employee_options(), variable=self.emp_var, width=260)
        self.emp_menu.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        # 期間
        ctk.CTkLabel(filt, text="開始日").grid(row=0, column=2, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.start_var, width=130).grid(
            row=0, column=3, padx=(0, 12), pady=6, sticky="w"
        )
        ctk.CTkLabel(filt, text="終了日").grid(row=0, column=4, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.end_var, width=130).grid(
            row=0, column=5, padx=(0, 12), pady=6, sticky="w"
        )

        BTN_W, BTN_H = 120, 36
        ctk.CTkButton(filt, text="検索", width=BTN_W, height=BTN_H, command=self.search)\
            .grid(row=0, column=6, padx=4, pady=6)
        ctk.CTkButton(filt, text="今日", width=BTN_W, height=BTN_H, command=self.quick_today)\
            .grid(row=0, column=7, padx=4, pady=6)
        ctk.CTkButton(filt, text="今月", width=BTN_W, height=BTN_H, command=self.quick_month)\
            .grid(row=0, column=8, padx=4, pady=6)
        ctk.CTkButton(filt, text="今年", width=BTN_W, height=BTN_H, command=self.quick_year)\
            .grid(row=0, column=9, padx=4, pady=6)
        ctk.CTkButton(filt, text="CSV出力", width=BTN_W, height=BTN_H, command=self.export_csv)\
            .grid(row=0, column=10, padx=4, pady=6)

        # 表
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=("date", "code", "name", "work_m", "work_h", "break_m", "break_h"),
            show="headings",
            height=18
        )
        self.tree.heading("date",    text="日付")
        self.tree.heading("code",    text="コード")
        self.tree.heading("name",    text="氏名")
        self.tree.heading("work_m",  text="実働(分)")
        self.tree.heading("work_h",  text="実働(時間)")
        self.tree.heading("break_m", text="休憩(分)")
        self.tree.heading("break_h", text="休憩(時間)")

        self.tree.column("date",    width=120, anchor="center")
        self.tree.column("code",    width=120, anchor="center")
        self.tree.column("name",    width=160, anchor="w")
        self.tree.column("work_m",  width=110, anchor="e")
        self.tree.column("work_h",  width=120, anchor="e")
        self.tree.column("break_m", width=110, anchor="e")
        self.tree.column("break_h", width=120, anchor="e")

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # 合計行
        sum_bar = ctk.CTkFrame(self)
        sum_bar.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        sum_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sum_bar, textvariable=self.sum_work_var, font=("Meiryo UI", 14)).pack(side="left", padx=6)
        ctk.CTkLabel(sum_bar, textvariable=self.sum_break_var, font=("Meiryo UI", 14)).pack(side="left", padx=16)

        # 初期表示：当月 & 先頭の従業員
        opts = self._employee_options()
        if opts:
            self.emp_var.set(opts[0])
        self.quick_month()

    # ====== 従業員オプション ======
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows]
    
    # ====== 検索バー連携用（従業員選択） ======
    def _select_employee_by_keyword(self, keyword: str) -> bool:
        """
        キーワード（氏名 or コードの一部）から
        プルダウンの従業員を 1 件選択する。
        見つかったら True / なければ False を返す。
        """
        kw = (keyword or "").strip().lower()
        if not kw:
            return False

        # 現在 OptionMenu に設定されている値一覧を取得
        options = list(self.emp_menu.cget("values")) or []
        if not options:
            # 念のため DB から再取得して反映
            options = self._employee_options()
            if options:
                self.emp_menu.configure(values=options)

        for opt in options:
            # opt: "E0001 山田 太郎" のような形式
            if kw in opt.lower():
                self.emp_var.set(opt)
                self.emp_menu.set(opt)
                return True

        return False

    # ====== ヘッダー検索連携：キーワードから従業員を選択して検索 ======
    def on_search_keyword(self, keyword: str) -> None:
        """
        ヘッダーの検索バーで Enter されたときに呼ばれる想定の入口。
        - キーワードから従業員を特定
        - 日付は「今月」で固定して検索
        """
        kw = (keyword or "").strip()
        if not kw:
            return

        if not self._select_employee_by_keyword(kw):
            messagebox.showinfo("検索", f"「{kw}」に該当する従業員が見つかりませんでした。")
            return

        # ★ 日付範囲：「今月」で表示（仕様に応じて quick_today 等にしてもOK）
        self.quick_month()

    def on_search_from_record(self, record: dict) -> None:
        """
        検索サジェストで 1件選択されたときに呼ばれる想定の入口。
        - record から従業員コード・氏名・打刻日時(ts)を受け取り、
        その日付 1 日分のマイ勤怠を表示する。
        """
        if not record:
            return

        code = record.get("employee_code", "")
        name = record.get("name", "")
        ts   = record.get("ts", "")

        if not code:
            return

        # --- 従業員プルダウンの選択 ---
        label = f"{code} {name}".strip()
        options = list(self.emp_menu.cget("values")) or []
        if label in options:
            self.emp_var.set(label)
            self.emp_menu.set(label)
        elif options:
            # 万一マッチしなければ先頭にフォールバック
            self.emp_var.set(options[0])
            self.emp_menu.set(options[0])

        # --- ts から日付部分だけ抜き出し ---
        date_str = ""
        if "T" in ts:
            date_str = ts.split("T", 1)[0]
        elif " " in ts:
            date_str = ts.split(" ", 1)[0]
        else:
            date_str = ts[:10]

        # フォーマットチェック（失敗したら何もしない）
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return

        # 開始日・終了日ともにその1日に固定して検索
        self.start_var.set(date_str)
        self.end_var.set(date_str)
        self.search()

    def _emp_code_selected(self) -> str | None:
        v = self.emp_var.get()
        if not v:
            return None
        return v.split(" ")[0] if " " in v else v

    # ====== 日付パース ======
    def _parse_date(self, s: str | None) -> str | None:
        if not s:
            return None
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        except ValueError:
            return None

    def _current_range(self) -> tuple[str, str]:
        s = self._parse_date(self.start_var.get())
        e = self._parse_date(self.end_var.get())
        if not s and not e:
            today = date.today().strftime("%Y-%m-%d")
            return today, today
        if s and not e:
            return s, s
        if e and not s:
            return e, e
        return s or e, e or s

    # ====== アクション ======
    def search(self):
        start, end = self._current_range()
        code = self._emp_code_selected()
        if not code:
            messagebox.showwarning("従業員", "従業員を選択してください。")
            return

        rows = self.svc.calc_daily_summary(start, end, emp_repo=self.emp_repo, employee_code=code)

        # クリア
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # 反映 + 合計
        tot_w, tot_b = 0, 0
        for r in rows:
            wmin = r["work_minutes"]; bmin = r["break_minutes"]
            tot_w += wmin; tot_b += bmin
            self.tree.insert(
                "", "end",
                values=(r["date"], r["code"], r["name"], wmin, f"{wmin/60:.2f}", bmin, f"{bmin/60:.2f}")
            )

        self.sum_work_var.set(f"実働合計: {tot_w/60:.2f} h")
        self.sum_break_var.set(f"休憩合計: {tot_b/60:.2f} h")

    def quick_today(self):
        today = date.today().strftime("%Y-%m-%d")
        self.start_var.set(today)
        self.end_var.set(today)
        self.search()

    def quick_month(self):
        today = date.today()
        start = date(today.year, today.month, 1).strftime("%Y-%m-%d")
        end   = today.strftime("%Y-%m-%d")
        self.start_var.set(start)
        self.end_var.set(end)
        self.search()

    def quick_year(self):
        today = date.today()
        start = date(today.year, 1, 1).strftime("%Y-%m-%d")
        end   = today.strftime("%Y-%m-%d")
        self.start_var.set(start)
        self.end_var.set(end)
        self.search()

    # ====== CSV ======
    def export_csv(self):
        if not self.tree.get_children():
            messagebox.showinfo("CSV", "出力するデータがありません。")
            return
        start, end = self._current_range()
        path = filedialog.asksaveasfilename(
            title="CSVに保存",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"my_daily_summary_{start.replace('-','')}_{end.replace('-','')}.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["日付", "コード", "氏名", "実働(分)", "実働(時間)", "休憩(分)", "休憩(時間)"])
                for iid in self.tree.get_children():
                    w.writerow(self.tree.item(iid)["values"])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")
