# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
import csv

# 既存プロジェクト
from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo
from app.services.attendance_service import AttendanceService  # ★ 追加


# ===============================================================
# カレンダー付きエントリー（確定/キャンセル付き・同サイズボタン）
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


# ===============================================================
# 勤怠一覧画面（★ 月次給与 集計付き）
# ===============================================================
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
        # ★ 月次給与用
        today = date.today()
        self.year_var = tk.StringVar(value=str(today.year))
        self.month_var = tk.StringVar(value=f"{today.month:02d}")

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
        for i in range(12):
            filt.grid_columnconfigure(i, weight=0)
        filt.grid_columnconfigure(11, weight=1)

        ctk.CTkLabel(filt, text="開始日").grid(row=0, column=0, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.start_var, width=130).grid(
            row=0, column=1, padx=(0, 12), pady=6, sticky="w"
        )

        ctk.CTkLabel(filt, text="終了日").grid(row=0, column=2, padx=(8, 4), pady=6, sticky="e")
        DatePickerEntry(filt, textvariable=self.end_var, width=130).grid(
            row=0, column=3, padx=(0, 12), pady=6, sticky="w"
        )

        ctk.CTkLabel(filt, text="従業員").grid(row=0, column=4, padx=(8, 4), pady=6, sticky="e")
        ctk.CTkOptionMenu(filt, values=self._employee_options(), variable=self.emp_var, width=220).grid(
            row=0, column=5, padx=(0, 12), pady=6, sticky="w"
        )

        # 検索系ボタン（同サイズ統一）
        BTN_W, BTN_H = 120, 36
        ctk.CTkButton(filt, text="検索", width=BTN_W, height=BTN_H, command=self.search)\
            .grid(row=0, column=6,  padx=4, pady=6)
        ctk.CTkButton(filt, text="今日", width=BTN_W, height=BTN_H, command=self.quick_today)\
            .grid(row=0, column=7,  padx=4, pady=6)
        ctk.CTkButton(filt, text="今月", width=BTN_W, height=BTN_H, command=self.quick_month)\
            .grid(row=0, column=8,  padx=4, pady=6)
        ctk.CTkButton(filt, text="全期間", width=BTN_W, height=BTN_H, command=self.quick_all)\
            .grid(row=0, column=9,  padx=4, pady=6)

        # ★ 月次給与（フィルタの2段目にまとめて追加）
        ctk.CTkLabel(filt, text="年").grid(row=1, column=0, padx=(8, 4), pady=(6, 2), sticky="e")
        ctk.CTkEntry(filt, width=100, textvariable=self.year_var, placeholder_text="YYYY")\
            .grid(row=1, column=1, padx=(0, 12), pady=(6, 2), sticky="w")

        ctk.CTkLabel(filt, text="月").grid(row=1, column=2, padx=(8, 4), pady=(6, 2), sticky="e")
        ctk.CTkEntry(filt, width=80, textvariable=self.month_var, placeholder_text="MM")\
            .grid(row=1, column=3, padx=(0, 12), pady=(6, 2), sticky="w")

        ctk.CTkButton(filt, text="月次給与", width=BTN_W, height=BTN_H, command=self._show_monthly_payroll)\
            .grid(row=1, column=4, padx=(8, 4), pady=(6, 2), sticky="w")

        # 件数 ＆ エクスポート
        meta = ctk.CTkFrame(self)
        meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(meta, textvariable=self.count_var, font=("Meiryo UI", 14)).pack(side="left", padx=6)
        ctk.CTkButton(meta, text="CSVエクスポート", command=self.export_csv).pack(side="right", padx=4)

        # ===== Treeview スタイル =====
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            font=("Meiryo UI", 14),
            rowheight=34,
            background="#FFFFFF",
            foreground="#222222",
            fieldbackground="#FFFFFF",
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Treeview.Heading",
            font=("Meiryo UI", 15, "bold"),
            background="#E5E7EB",
            foreground="#111111",
            borderwidth=1,
            relief="solid",
        )
        style.map(
            "Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", "#111827")]
        )

        # 表コンテナ
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 0))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        # Treeview 本体
        self.tree = ttk.Treeview(
            table_wrap,
            columns=("id", "ts", "code", "name", "type"),
            show="headings",
            height=18
        )
        self.tree.heading("id",   text="ID")
        self.tree.heading("ts",   text="日時")
        self.tree.heading("code", text="コード")
        self.tree.heading("name", text="氏名")
        self.tree.heading("type", text="区分")

        self.tree.column("id",   width=90,  anchor="center")
        self.tree.column("ts",   width=210, anchor="center")
        self.tree.column("code", width=150, anchor="center")
        self.tree.column("name", width=180, anchor="center")
        self.tree.column("type", width=110, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        # スクロールバー
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # 初期表示：今日
        self.quick_today()

    # ---------------- フィルタ支援 ----------------
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

    # ---------------- アクション ----------------
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

        # クリア
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # 反映（秒以下→分まで）
        for idx, r in enumerate(rows):
            try:
                ts_str = datetime.strptime(r["ts"], "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = r["ts"].replace("T", " ")

            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "", "end",
                values=(r["id"], ts_str, r["employee_code"], r.get("name", ""), self._label_of_type(r["punch_type"])),
                tags=(tag,)
            )

        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd",  background="#F9FAFB")

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

    # ---------------- CSV出力 ----------------
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

    # ---------------- 月次給与（★追加） ----------------
    def _show_monthly_payroll(self):
        y = self.year_var.get().strip()
        m = self.month_var.get().strip()
        if not (y.isdigit() and m.isdigit()):
            messagebox.showwarning("月次給与", "年と月は数値で入力してください。")
            return
        year, month = int(y), int(m)
        if not (1 <= month <= 12):
            messagebox.showwarning("月次給与", "月は 1〜12 を入力してください。")
            return

        # 集計（全員。個別集計にしたい場合は _emp_code_selected() を渡す）
        svc = AttendanceService(self.att_repo)
        results = svc.calc_monthly_payroll(year, month, emp_repo=self.emp_repo, employee_code=None)

        # ダイアログ
        win = ctk.CTkToplevel(self)
        win.title(f"月次給与 {year}-{month:02d}")
        win.geometry("780x540")
        win.grab_set()

        head = ctk.CTkFrame(win)
        head.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(head, text=f"📊 月次給与 {year}-{month:02d}", font=("Meiryo UI", 16, "bold"))\
            .pack(side="left")

        def _export():
            if not results:
                messagebox.showinfo("CSV", "出力対象がありません。")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSVファイル","*.csv")],
                initialfile=f"payroll_{year}{month:02d}.csv"
            )
            if not path:
                return
            import csv as _csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = _csv.writer(f)
                w.writerow(["code", "name", "total_minutes", "hours", "hourly_wage", "amount"])
                for r in results:
                    hours = r["total_minutes"] / 60.0
                    w.writerow([r["code"], r["name"], r["total_minutes"], f"{hours:.2f}", r["hourly_wage"], r["amount"]])
            messagebox.showinfo("CSV", "CSVを書き出しました。")

        ctk.CTkButton(head, text="CSV出力", command=_export).pack(side="right")

        body = ctk.CTkScrollableFrame(win, height=440, fg_color="#ECEFF1")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        hdr = ctk.CTkFrame(body, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew")
        cols = ["コード", "氏名", "実働(分)", "実働(時間)", "時給", "支給額"]
        for i, t in enumerate(cols):
            ctk.CTkLabel(hdr, text=t, font=("Meiryo UI", 13, "bold")).grid(row=0, column=i, padx=8, pady=6, sticky="w")
            hdr.grid_columnconfigure(i, weight=1 if i in (1,) else 0)

        total_amount = 0
        for idx, r in enumerate(results, start=1):
            row_bg = "#FFFFFF" if idx % 2 == 0 else "#FAFAFA"
            card = ctk.CTkFrame(body, corner_radius=8, border_width=1, border_color="#D0D7DF", fg_color=row_bg)
            card.grid(row=idx, column=0, sticky="ew", padx=6, pady=4)
            hours = r["total_minutes"] / 60.0
            vals = [
                r["code"],
                r["name"],
                str(r["total_minutes"]),
                f"{hours:.2f}",
                f"{int(r['hourly_wage']):,}",
                f"{int(r['amount']):,}",
            ]
            total_amount += int(r["amount"])
            for j, v in enumerate(vals):
                sticky = "e" if j in (2,3,4,5) else "w"
                ctk.CTkLabel(card, text=v, anchor=sticky).grid(row=0, column=j, padx=10, pady=8, sticky=sticky)
                card.grid_columnconfigure(j, weight=1 if j == 1 else 0)

        # フッタ合計
        foot = ctk.CTkFrame(win)
        foot.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(foot, text=f"合計支給額: {total_amount:,} 円", font=("Meiryo UI", 14, "bold"))\
            .pack(side="right")

    # ---------------- 表示ラベル ----------------
    def _label_of_type(self, punch_type: str) -> str:
        return {
            "CLOCK_IN": "出勤",
            "BREAK_START": "休憩開始",
            "BREAK_END": "休憩終了",
            "CLOCK_OUT": "退勤",
        }.get(punch_type, punch_type)
