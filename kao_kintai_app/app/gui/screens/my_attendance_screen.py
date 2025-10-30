import customtkinter as ctk
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import date
import csv

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo



class MyAttendanceScreen(ctk.CTkFrame):
    """
    本人の勤怠を閲覧・CSV出力（当面はプルダウンで自分を選択）
    その後ログイン機能と連動して自動選択にする想定
    """
    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()

        self.start_var = tk.StringVar()
        self.end_var   = tk.StringVar()
        self.emp_var   = tk.StringVar(value="")
        self.count_var = tk.StringVar(value="0 件")

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="👤 マイ勤怠", font=("Meiryo UI", 22, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16,8))

        filt = ctk.CTkFrame(self); filt.grid(row=1, column=0, sticky="ew", padx=16)
        for i in range(10): filt.grid_columnconfigure(i, weight=0)
        filt.grid_columnconfigure(9, weight=1)

        ctk.CTkLabel(filt, text="開始日").grid(row=0, column=0, padx=(8,4), pady=6, sticky="e")
        ctk.CTkEntry(filt, textvariable=self.start_var, width=130, placeholder_text="YYYY-MM-DD").grid(row=0, column=1, padx=(0,12), pady=6, sticky="w")

        ctk.CTkLabel(filt, text="終了日").grid(row=0, column=2, padx=(8,4), pady=6, sticky="e")
        ctk.CTkEntry(filt, textvariable=self.end_var, width=130, placeholder_text="YYYY-MM-DD").grid(row=0, column=3, padx=(0,12), pady=6, sticky="w")

        # 本人選択（暫定：プルダウン）
        opts = self._employee_options()
        ctk.CTkLabel(filt, text="本人").grid(row=0, column=4, padx=(8,4), pady=6, sticky="e")
        self.emp_menu = ctk.CTkOptionMenu(filt, values=opts if opts else ["従業員が未登録です"], variable=self.emp_var, width=220)
        self.emp_menu.grid(row=0, column=5, padx=(0,12), pady=6, sticky="w")
        if opts:
            self.emp_var.set(opts[0])

        ctk.CTkButton(filt, text="検索", command=self.search).grid(row=0, column=6, padx=4, pady=6)
        ctk.CTkButton(filt, text="今日", command=self.quick_today).grid(row=0, column=7, padx=4, pady=6)
        ctk.CTkButton(filt, text="今月", command=self.quick_month).grid(row=0, column=8, padx=4, pady=6)

        meta = ctk.CTkFrame(self); meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(4,12))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(meta, textvariable=self.count_var).pack(side="left", padx=6)
        ctk.CTkButton(meta, text="CSVエクスポート", command=self.export_csv).pack(side="right", padx=4)

        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0,0))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_wrap, columns=("id","ts","type"), show="headings", height=18)
        self.tree.heading("id", text="ID")
        self.tree.heading("ts", text="日時")
        self.tree.heading("type", text="区分")
        self.tree.column("id", width=80, anchor="e")
        self.tree.column("ts", width=200, anchor="w")
        self.tree.column("type", width=120, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        self.quick_today()

    # ---- helpers ----
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows] if rows else []

    def _code_from(self, s: str) -> str | None:
        if not s or " " not in s: return None
        return s.split(" ")[0]

    def _parse_date(self, s: str | None) -> str | None:
        if not s: return None
        import datetime as dt
        try:
            dt.datetime.strptime(s, "%Y-%m-%d")
            return s
        except ValueError:
            return None

    # ---- actions ----
    def search(self):
        start = self._parse_date(self.start_var.get())
        end   = self._parse_date(self.end_var.get())
        if self.start_var.get() and not start:
            messagebox.showwarning("日付形式", "開始日は YYYY-MM-DD 形式で入力してください。"); return
        if self.end_var.get() and not end:
            messagebox.showwarning("日付形式", "終了日は YYYY-MM-DD 形式で入力してください。"); return

        code = self._code_from(self.emp_var.get())
        if not code:
            messagebox.showwarning("本人未選択", "本人（従業員）を選択してください。"); return

        rows = AttendanceRepo().list_records(start_date=start, end_date=end, employee_code=code)

        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in rows:
            self.tree.insert("", "end", values=(r["id"], r["ts"].replace("T"," "), self._label_of_type(r["punch_type"])))
        self.count_var.set(f"{len(rows)} 件")

    def quick_today(self):
        d = date.today().strftime("%Y-%m-%d")
        self.start_var.set(d); self.end_var.set(d)
        self.search()

    def quick_month(self):
        t = date.today()
        start = date(t.year, t.month, 1).strftime("%Y-%m-%d")
        self.start_var.set(start); self.end_var.set(t.strftime("%Y-%m-%d"))
        self.search()

    def export_csv(self):
        if not self.tree.get_children():
            messagebox.showinfo("CSV", "出力するデータがありません。"); return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(title="CSVに保存", defaultextension=".csv",
                                            filetypes=[("CSV Files","*.csv")],
                                            initialfile=f"my_attendance_{date.today().strftime('%Y%m%d')}.csv")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f); w.writerow(["ID","日時","区分"])
                for iid in self.tree.get_children():
                    w.writerow(self.tree.item(iid)["values"])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")

    def _label_of_type(self, punch_type: str) -> str:
        return {"CLOCK_IN":"出勤","BREAK_START":"休憩開始","BREAK_END":"休憩終了","CLOCK_OUT":"退勤"}.get(punch_type, punch_type)
