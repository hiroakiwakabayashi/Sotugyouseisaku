import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
import csv

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo

from tkcalendar import Calendar


class DatePickerEntry(ctk.CTkFrame):
    """クリックでカレンダーを出すCTk対応の日付入力"""
    def __init__(self, master, textvariable: tk.StringVar | None = None, width=130, placeholder_text="YYYY-MM-DD"):
        super().__init__(master)
        self.var = textvariable or tk.StringVar()
        self.entry = ctk.CTkEntry(self, textvariable=self.var, width=width,
                                  placeholder_text=placeholder_text, state="readonly")
        self.entry.pack(side="left", fill="x")
        self.entry.bind("<Button-1>", self._open_popup)

        self.btn = ctk.CTkButton(self, text="📅", width=34, command=self._open_popup)
        self.btn.pack(side="left", padx=4)

        self.popup = None

    def _open_popup(self, event=None):
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            self.popup.destroy()

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self.popup = tk.Toplevel(self)
        self.popup.wm_overrideredirect(True)
        self.popup.wm_geometry(f"+{x}+{y}")
        self.popup.attributes("-topmost", True)

        selected_date = None
        try:
            if self.var.get():
                selected_date = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            pass

        cal = Calendar(
            self.popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=(selected_date.year if selected_date else date.today().year),
            month=(selected_date.month if selected_date else date.today().month),
            day=(selected_date.day if selected_date else date.today().day),
            locale="ja_JP",
        )
        cal.pack(padx=4, pady=4)

        def on_ok():
            self.var.set(cal.get_date())
            self.popup.destroy()

        def on_cancel():
            self.popup.destroy()

        btns = ctk.CTkFrame(self.popup)
        btns.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkButton(btns, text="OK", command=on_ok, width=60).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="キャンセル", command=on_cancel, width=80).pack(side="right", padx=4)

        self.popup.focus_force()
        self.popup.bind("<FocusOut>", lambda e: self.popup.destroy())


class AttendanceListScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()

        # 変数
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.emp_var = tk.StringVar(value="全員")
        self.count_var = tk.StringVar(value="0 件")

        # レイアウト
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="📑 勤怠一覧 / 検索", font=("Meiryo UI", 22, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 8)
        )

        # フィルタ行
        filt = ctk.CTkFrame(self)
        filt.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        for i in range(10):
            filt.grid_columnconfigure(i, weight=0)
        filt.grid_columnconfigure(9, weight=1)

        ctk.CTkLabel(filt, text="開始日").grid(row=0, column=0, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.start_var, width=130).grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        ctk.CTkLabel(filt, text="終了日").grid(row=0, column=2, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.end_var, width=130).grid(row=0, column=3, padx=(0, 12), pady=6, sticky="w")

        ctk.CTkLabel(filt, text="従業員").grid(row=0, column=4, padx=(8, 4), pady=6, sticky="e")
        ctk.CTkOptionMenu(filt, values=self._employee_options(), variable=self.emp_var, width=220).grid(
            row=0, column=5, padx=(0, 12), pady=6, sticky="w"
        )

        ctk.CTkButton(filt, text="検索", command=self.search).grid(row=0, column=6, padx=4, pady=6)
        ctk.CTkButton(filt, text="今日", command=self.quick_today).grid(row=0, column=7, padx=4, pady=6)
        ctk.CTkButton(filt, text="今月", command=self.quick_month).grid(row=0, column=8, padx=4, pady=6)
        ctk.CTkButton(filt, text="全期間", command=self.quick_all).grid(row=0, column=9, padx=4, pady=6, sticky="w")

        # 件数＆エクスポート
        meta = ctk.CTkFrame(self)
        meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(meta, textvariable=self.count_var, font=("Meiryo UI", 14)).pack(side="left", padx=6)
        ctk.CTkButton(meta, text="CSVエクスポート", command=self.export_csv).pack(side="right", padx=4)

        # テーブル枠
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 0))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        # ===== Treeview を大きく見やすくするスタイル =====
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            font=("Meiryo UI", 14),   # 行の文字
            rowheight=36,             # 行の高さ
        )
        style.configure(
            "Treeview.Heading",
            font=("Meiryo UI", 15, "bold"),  # 見出しの文字
            padding=6,
        )
        style.map(
            "Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", "#111827")],
        )

        # テーブル
        self.tree = ttk.Treeview(
            table_wrap,
            columns=("id", "ts", "code", "name", "type"),
            show="headings",
            height=18
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("ts", text="日時")
        self.tree.heading("code", text="コード")
        self.tree.heading("name", text="氏名")
        self.tree.heading("type", text="区分")

        # 広めのカラム幅
        self.tree.column("id",   width=110, anchor="e")
        self.tree.column("ts",   width=220, anchor="w")
        self.tree.column("code", width=160, anchor="w")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("type", width=130, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # 初期表示：今日
        self.quick_today()

    # ---------- フィルタ支援 ----------
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        opts = ["全員"] + [f"{r['code']} {r['name']}" for r in rows]
        return opts

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

    # ---------- アクション ----------
    def search(self):
        start = self._parse_date(self.start_var.get())
        end   = self._parse_date(self.end_var.get())
        if self.start_var.get() and not start:
            messagebox.showwarning("日付形式", "開始日は YYYY-MM-DD 形式で入力してください。")
            return
        if self.end_var.get() and not end:
            messagebox.showwarning("日付形式", "終了日は YYYY-MM-DD 形式で入力してください。")
            return

        code = self._emp_code_selected()
        rows = self.att_repo.list_records(start_date=start, end_date=end, employee_code=code)

        # テーブル反映
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            try:
                # 秒以下をカットして「分まで」に整形
                ts_str = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = r["ts"].replace("T", " ")

            self.tree.insert("", "end", values=(
                r["id"],
                ts_str,
                r["employee_code"],
                r.get("name", ""),
                self._label_of_type(r["punch_type"]),
            ))
        self.count_var.set(f"{len(rows)} 件")

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

    def quick_all(self):
        self.start_var.set("")
        self.end_var.set("")
        self.emp_var.set("全員")
        self.search()

    def export_csv(self):
        if not self.tree.get_children():
            messagebox.showinfo("CSV", "出力するデータがありません。")
            return
        path = filedialog.asksaveasfilename(
            title="CSVに保存",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"attendance_{date.today().strftime('%Y%m%d')}.csv"
        )
        if not path:
            return

        headers = ["ID", "日時", "コード", "氏名", "区分"]
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for iid in self.tree.get_children():
                    writer.writerow(self.tree.item(iid)["values"])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")

    # ---------- 表示ラベル ----------
    def _label_of_type(self, punch_type: str) -> str:
        return {
            "CLOCK_IN": "出勤",
            "BREAK_START": "休憩開始",
            "BREAK_END": "休憩終了",
            "CLOCK_OUT": "退勤",
        }.get(punch_type, punch_type)
