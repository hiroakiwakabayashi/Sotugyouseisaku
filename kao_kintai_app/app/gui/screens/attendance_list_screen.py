#app\gui\screens\attendance_list_screen.py
# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
import csv

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo
from app.services.attendance_service import AttendanceService  # 未使用だがそのまま


# ===============================================================
# カレンダー付きエントリー
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

        ctk.CTkButton(
            btns, text="確定", width=CAL_BTN_W, height=CAL_BTN_H, command=self._ok
        ).pack(side="left", padx=(30, 8), pady=4)
        ctk.CTkButton(
            btns, text="キャンセル", width=CAL_BTN_W, height=CAL_BTN_H, command=self._cancel
        ).pack(side="right", padx=(8, 30), pady=4)

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
# 勤怠一覧画面（氏名 / コード検索対応）
# ===============================================================
class AttendanceListScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()

        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.emp_var = tk.StringVar(value="全員")
        self.count_var = tk.StringVar(value="0 件")

        # 🔍 検索キーワード（氏名/コード）
        self.keyword: str = ""

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="📑 勤怠一覧 / 検索",
            font=("Meiryo UI", 22, "bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # =========================================================
        # フィルタエリア（2段構成、全体を均等配置）
        # =========================================================
        filt = ctk.CTkFrame(self)
        filt.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        filt.grid_columnconfigure(0, weight=1)

        BTN_H = 32  # ボタン高さ（全ボタン共通）

        # ---------- 1段目：開始日 / 終了日 / 従業員 / 検索 ----------
        row1 = ctk.CTkFrame(filt, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="ew")
        for c in range(4):
            row1.grid_columnconfigure(c, weight=1)

        # 開始日グループ
        start_box = ctk.CTkFrame(row1, fg_color="transparent")
        start_box.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(start_box, text="開始日").pack(side="left", padx=(0, 4))
        DatePickerEntry(start_box, textvariable=self.start_var, width=130).pack(
            side="left"
        )

        # 終了日グループ
        end_box = ctk.CTkFrame(row1, fg_color="transparent")
        end_box.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(end_box, text="終了日").pack(side="left", padx=(0, 4))
        DatePickerEntry(end_box, textvariable=self.end_var, width=130).pack(
            side="left"
        )

        # 従業員グループ
        emp_box = ctk.CTkFrame(row1, fg_color="transparent")
        emp_box.grid(row=0, column=2, sticky="w", padx=4, pady=4)
        ctk.CTkLabel(emp_box, text="従業員").pack(side="left", padx=(0, 4))
        ctk.CTkOptionMenu(
            emp_box,
            values=self._employee_options(),
            variable=self.emp_var,
            width=220,
        ).pack(side="left")

        # 検索ボタン（右端いっぱい）
        ctk.CTkButton(
            row1,
            text="検索",
            height=BTN_H,
            command=self.search,
        ).grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        # ---------- 2段目：クイックボタン列（均等5分割） ----------
        row2 = ctk.CTkFrame(filt, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        for c in range(5):
            row2.grid_columnconfigure(c, weight=1)

        quick_buttons = [
            ("今日", self.quick_today),
            ("今月", self.quick_month),
            ("今年", self.quick_year),
            ("給与(今月)", self.payroll_this_month),
            ("給与(表示月)", self.payroll_from_filters),
        ]
        for col, (label, cmd) in enumerate(quick_buttons):
            ctk.CTkButton(
                row2,
                text=label,
                height=BTN_H,
                command=cmd,
            ).grid(row=0, column=col, padx=4, pady=(2, 4), sticky="ew")

        # ---------------- 件数 + CSV ----------------
        meta = ctk.CTkFrame(self)
        meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            meta, textvariable=self.count_var, font=("Meiryo UI", 14)
        ).pack(side="left", padx=6)
        ctk.CTkButton(meta, text="CSVエクスポート", command=self.export_csv).pack(
            side="right", padx=4
        )

        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 0))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=("id", "code", "name", "ts", "type"),
            show="headings",
            height=18,
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("code", text="コード")
        self.tree.heading("name", text="氏名")
        self.tree.heading("ts", text="日時")
        self.tree.heading("type", text="区分")

        self.tree.column("id", width=70, anchor="center")
        self.tree.column("code", width=130, anchor="center")
        self.tree.column("name", width=180, anchor="center")
        self.tree.column("ts", width=220, anchor="center")
        self.tree.column("type", width=110, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd", background="#F9FAFB")

        self.quick_today()

    # ==== AppShell から呼ばれる検索入口 ====
    def on_search(self, keyword: str):
        self.keyword = (keyword or "").strip()
        self.search()

    # ==== フィルタ支援 ====
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return ["全員"] + [f"{r['code']} {r['name']}" for r in rows]

    def _emp_code_selected(self) -> str | None:
        v = self.emp_var.get()
        if not v or v == "全員":
            return None
        return v.split(" ")[0] if " " in v else v

    def _parse_date(self, s: str | None) -> str | None:
        if not s:
            return None
        try:
            datetime.strptime(s, "%Y-%m-%d")
            return s
        except ValueError:
            return None

    # ==== メイン検索処理 ====
    def search(self):
        start = self._parse_date(self.start_var.get())
        end = self._parse_date(self.end_var.get())
        if self.start_var.get() and not start:
            messagebox.showwarning("日付形式", "開始日は YYYY-MM-DD 形式で入力してください。")
            return
        if self.end_var.get() and not end:
            messagebox.showwarning("日付形式", "終了日は YYYY-MM-DD 形式で入力してください。")
            return

        code = self._emp_code_selected()
        rows = self.att_repo.list_records(
            start_date=start, end_date=end, employee_code=code
        )

        # 🔍 氏名 / コードの部分一致フィルタ
        if self.keyword:
            kw = self.keyword.lower()

            def match(r):
                name = str(r.get("name", "")).lower()
                code_val = str(r.get("employee_code", "")).lower()
                return (kw in name) or (kw in code_val)

            rows = [r for r in rows if match(r)]

        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for idx, r in enumerate(rows):
            raw_ts = r["ts"]
            ts_str = raw_ts
            try:
                ts_str = datetime.strptime(
                    raw_ts, "%Y-%m-%dT%H:%M:%S.%f"
                ).strftime("%Y/%m/%d %H:%M")
            except Exception:
                try:
                    ts_str = datetime.strptime(
                        raw_ts, "%Y-%m-%dT%H:%M:%S"
                    ).strftime("%Y/%m/%d %H:%M")
                except Exception:
                    ts_str = raw_ts.replace("T", " ")

            zebra = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    r["employee_code"],
                    r.get("name", ""),
                    ts_str,
                    self._label_of_type(r["punch_type"]),
                ),
                tags=(zebra,),
            )

        self.count_var.set(f"{len(rows)} 件")

    # ==== クイック日付 ====
    def quick_today(self):
        today = date.today().strftime("%Y-%m-%d")
        self.start_var.set(today)
        self.end_var.set(today)
        self.search()

    def quick_month(self):
        today = date.today()
        start = date(today.year, today.month, 1)
        self.start_var.set(start.strftime("%Y-%m-%d"))
        self.end_var.set(today.strftime("%Y-%m-%d"))
        self.search()

    def quick_year(self):
        today = date.today()
        start = date(today.year, 1, 1)
        self.start_var.set(start.strftime("%Y-%m-%d"))
        self.end_var.set(today.strftime("%Y-%m-%d"))
        self.search()

    # ==== CSV ====
    def export_csv(self):
        if not self.tree.get_children():
            messagebox.showinfo("CSV", "出力するデータがありません。")
            return
        path = filedialog.asksaveasfilename(
            title="CSVに保存",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"attendance_{date.today().strftime('%Y%m%d')}.csv",
        )
        if not path:
            return

        headers = ["ID", "コード", "氏名", "日時", "区分"]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for iid in self.tree.get_children():
                    writer.writerow(self.tree.item(iid)["values"])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")

    # ==== 区分ラベル ====
    def _label_of_type(self, punch_type: str) -> str:
        return {
            "CLOCK_IN": "出勤",
            "BREAK_START": "休憩開始",
            "BREAK_END": "休憩終了",
            "CLOCK_OUT": "退勤",
        }.get(punch_type, punch_type)

    # ==== 給与ダイアログ呼び出し ====
    def payroll_this_month(self):
        """今日の年月で月次給与を表示"""
        today = date.today()
        self._show_monthly_payroll(today.year, today.month)

    def payroll_from_filters(self):
        """
        フィルタで選んでいる開始日から年月を推定して表示。
        未指定なら今日の年月。
        """
        if self.start_var.get():
            try:
                dt = datetime.strptime(self.start_var.get(), "%Y-%m-%d")
                y, m = dt.year, dt.month
            except Exception:
                y, m = date.today().year, date.today().month
        else:
            y, m = date.today().year, date.today().month
        self._show_monthly_payroll(y, m)

    def _show_monthly_payroll(self, year: int, month: int):
        """
        月次給与を計算してポップアップ表示
        """
        svc = AttendanceService(self.att_repo)
        results = svc.calc_monthly_payroll(
            year, month, emp_repo=self.emp_repo, employee_code=None
        )

        # 画面
        win = ctk.CTkToplevel(self)
        win.title(f"月次給与 {year}-{month:02d}")
        win.geometry("780x520")
        win.grid_rowconfigure(2, weight=1)
        win.grid_columnconfigure(0, weight=1)

        # ============================
        # ★ 前面に出す（背面化対策）
        # ============================
        parent = self.winfo_toplevel()          # ルート（AppShell / root）
        try:
            win.transient(parent)               # 親に紐づけ（Alt+Tabでも親と一緒に出る）
        except Exception:
            pass

        win.lift()                              # スタッキング順を前へ
        win.focus_force()                       # フォーカスを取る

        # 一瞬だけ最前面化して確実に前に出す（その後解除して通常挙動へ）
        win.after(10, lambda: win.attributes("-topmost", True))
        win.after(50, lambda: win.attributes("-topmost", False))

        # モーダルにしたい場合（背面クリックで埋もれるのを防ぐ）
        win.grab_set()

        def _on_close():
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)

        # ヘッダ
        head = ctk.CTkFrame(win, height=46)
        head.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        head.grid_propagate(False)
        ctk.CTkLabel(
            head,
            text=f"🧾 月次給与 {year}-{month:02d}",
            font=("Meiryo UI", 18, "bold"),
        ).pack(side="left", padx=8)

        def _export():
            if not results:
                messagebox.showinfo("CSV", "出力するデータがありません。")
                return
            path = filedialog.asksaveasfilename(
                title="CSVに保存",
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                initialfile=f"payroll_{year}{month:02d}.csv",
            )
            if not path:
                return
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["コード", "氏名", "実働(分)", "実働(時間)", "時給", "支給額"])
                for r in results:
                    hours = r["total_minutes"] / 60.0
                    w.writerow(
                        [
                            r["code"],
                            r["name"],
                            r["total_minutes"],
                            f"{hours:.2f}",
                            r["hourly_wage"],
                            r["amount"],
                        ]
                    )
            messagebox.showinfo("CSV", f"保存しました：\n{path}")

        ctk.CTkButton(head, text="CSV出力", command=_export, width=100).pack(
            side="right", padx=8
        )

        # 表
        wrap = ctk.CTkFrame(win)
        wrap.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(
            wrap,
            columns=("code", "name", "mins", "hours", "wage", "amount"),
            show="headings",
            height=16,
        )
        tree.heading("code", text="コード")
        tree.heading("name", text="氏名")
        tree.heading("mins", text="実働(分)")
        tree.heading("hours", text="実働(時間)")
        tree.heading("wage", text="時給")
        tree.heading("amount", text="支給額")

        tree.column("code", width=120, anchor="center")
        tree.column("name", width=160, anchor="w")
        tree.column("mins", width=110, anchor="e")
        tree.column("hours", width=120, anchor="e")
        tree.column("wage", width=90, anchor="e")
        tree.column("amount", width=120, anchor="e")
        tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # データ投入
        total = 0
        for r in results:
            hours = r["total_minutes"] / 60.0
            total += r["amount"]
            tree.insert(
                "",
                "end",
                values=(
                    r["code"],
                    r["name"],
                    r["total_minutes"],
                    f"{hours:.2f}",
                    int(r["hourly_wage"]),
                    int(r["amount"]),
                ),
            )

        # 合計
        foot = ctk.CTkFrame(win, height=34)
        foot.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
        foot.grid_propagate(False)
        ctk.CTkLabel(
            foot,
            text=f"合計支給額：{total:,} 円",
            font=("Meiryo UI", 14, "bold"),
        ).pack(side="right", padx=10)
