# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date
import csv

# あなたの既存プロジェクトのリポジトリ
from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo


# ===============================================================
# カレンダー付きエントリー（確定/キャンセル付き・同サイズボタン）
# ===============================================================
class DatePickerEntry(ctk.CTkFrame):
    """
    クリックするとポップアップで tkcalendar.Calendar を表示。
    「確定」押下でのみ値が反映され、フォーカスが外れたら自動で閉じる。
    """
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
        self.cal = None  # 後でセット

    def _open(self, *_):
        from tkcalendar import Calendar

        # 既に開いていれば閉じる
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            self.popup.destroy()

        # 位置（エントリの直下）
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self.popup = tk.Toplevel(self)
        self.popup.overrideredirect(True)
        self.popup.geometry(f"+{x}+{y}")
        self.popup.attributes("-topmost", True)

        # 既存値を初期選択に
        selected = None
        try:
            if self.var.get():
                selected = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            selected = None

        # ---- カレンダー本体（文字大きめ／他月日非表示）----
        self.cal = Calendar(
            self.popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=(selected.year if selected else date.today().year),
            month=(selected.month if selected else date.today().month),
            day=(selected.day if selected else date.today().day),
            locale="ja_JP",
            font=("Meiryo UI", 15),      # 数字を見やすく
            showweeknumbers=False,       # 週番号を非表示
            showothermonthdays=False,    # ひと月だけ表示
            # 以下は見やすさ系（対応環境で反映）
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

        # ---- 同サイズの「確定／キャンセル」ボタン ----
        CAL_BTN_W, CAL_BTN_H = 110, 36
        btns = ctk.CTkFrame(self.popup)
        btns.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkButton(
            btns, text="確定", width=CAL_BTN_W, height=CAL_BTN_H, command=self._ok
        ).pack(side="left", padx=(30, 8), pady=4)

        ctk.CTkButton(
            btns, text="キャンセル", width=CAL_BTN_W, height=CAL_BTN_H, command=self._cancel
        ).pack(side="right", padx=(8, 30), pady=4)

        # 外れたら閉じる（＝確定しない）
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
# 勤怠一覧画面
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
            .grid(row=0, column=6, padx=4, pady=6)
        ctk.CTkButton(filt, text="今日", width=BTN_W, height=BTN_H, command=self.quick_today)\
            .grid(row=0, column=7, padx=4, pady=6)
        ctk.CTkButton(filt, text="今月", width=BTN_W, height=BTN_H, command=self.quick_month)\
            .grid(row=0, column=8, padx=4, pady=6)
        ctk.CTkButton(filt, text="全期間", width=BTN_W, height=BTN_H, command=self.quick_all)\
            .grid(row=0, column=9, padx=4, pady=6)

        # 件数 ＆ エクスポート
        meta = ctk.CTkFrame(self)
        meta.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))
        meta.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(meta, textvariable=self.count_var, font=("Meiryo UI", 14)).pack(side="left", padx=6)
        ctk.CTkButton(meta, text="CSVエクスポート", command=self.export_csv).pack(side="right", padx=4)

        # ===== Treeview スタイル（見やすく）=====
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
        self.tree.heading("id", text="ID")
        self.tree.heading("ts", text="日時")
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

            # 交互色（ゼブラ）
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert(
                "", "end",
                values=(r["id"], ts_str, r["employee_code"], r.get("name", ""), self._label_of_type(r["punch_type"])),
                tags=(tag,)
            )

        # ゼブラ色定義（tag_configure は挿入後でもOK）
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

    # ---------------- 表示ラベル ----------------
    def _label_of_type(self, punch_type: str) -> str:
        return {
            "CLOCK_IN": "出勤",
            "BREAK_START": "休憩開始",
            "BREAK_END": "休憩終了",
            "CLOCK_OUT": "退勤",
        }.get(punch_type, punch_type)
