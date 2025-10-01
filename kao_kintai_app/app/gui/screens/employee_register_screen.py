import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from app.infra.db.employee_repo import EmployeeRepo

class EmployeeRegisterScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.repo = EmployeeRepo()

        # レイアウト
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="👥 従業員登録 / 編集", font=("Meiryo UI", 22, "bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # 上段：フォーム
        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", padx=16)
        form.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(form, text="社員コード").grid(row=0, column=0, padx=8, pady=6, sticky="e")
        self.code_var = tk.StringVar()
        self.code_entry = ctk.CTkEntry(form, textvariable=self.code_var, state="readonly", width=180)
        self.code_entry.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        ctk.CTkLabel(form, text="氏名").grid(row=0, column=2, padx=8, pady=6, sticky="e")
        self.name_var = tk.StringVar()
        ctk.CTkEntry(form, textvariable=self.name_var, width=260, placeholder_text="例）山田 太郎").grid(row=0, column=3, padx=8, pady=6, sticky="w")

        ctk.CTkLabel(form, text="ロール").grid(row=1, column=0, padx=8, pady=6, sticky="e")
        self.role_var = tk.StringVar(value="USER")
        ctk.CTkOptionMenu(form, values=["USER", "MANAGER", "ADMIN"], variable=self.role_var, width=180).grid(row=1, column=1, padx=8, pady=6, sticky="w")

        self.active_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(form, text="有効（退職・休職で外す）", variable=self.active_var).grid(row=1, column=3, padx=8, pady=6, sticky="w")

        # ボタン列
        btns = ctk.CTkFrame(self)
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 8))
        for i in range(5): btns.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(btns, text="新規", command=self.on_new).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(btns, text="保存（新規/更新）", command=self.on_save).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(btns, text="有効化", command=lambda: self.on_toggle_active(True)).grid(row=0, column=2, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(btns, text="無効化", command=lambda: self.on_toggle_active(False)).grid(row=0, column=3, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(btns, text="再読込", command=self.refresh_table).grid(row=0, column=4, padx=6, pady=6, sticky="ew")

        # 下段：一覧（Treeview）
        table_wrap = ctk.CTkFrame(self)
        table_wrap.grid(row=3, column=0, sticky="nsew", padx=16, pady=(4,16))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_wrap, columns=("code","name","role","active","created_at"), show="headings")
        self.tree.heading("code", text="コード")
        self.tree.heading("name", text="氏名")
        self.tree.heading("role", text="ロール")
        self.tree.heading("active", text="有効")
        self.tree.heading("created_at", text="作成日時")
        self.tree.column("code", width=120); self.tree.column("name", width=180); self.tree.column("role", width=90); self.tree.column("active", width=60); self.tree.column("created_at", width=160)
        self.tree.grid(row=0, column=0, sticky="nsew")

        # スクロールバー
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # 行選択イベント
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

        # 初期状態
        self.refresh_table()
        self.on_new()

    # -------- UI handlers --------
    def on_new(self):
        self.code_var.set("")
        self.name_var.set("")
        self.role_var.set("USER")
        self.active_var.set(True)

    def on_save(self):
        name = self.name_var.get().strip()
        role = self.role_var.get().strip() or "USER"
        if not name:
            messagebox.showwarning("入力不足", "氏名を入力してください。")
            return

        code = self.code_var.get().strip()
        if code == "":
            # 新規（コードは自動採番）
            code = self.repo.create(name=name, role=role)
            self.code_var.set(code)
            messagebox.showinfo("登録", f"従業員を登録しました（コード: {code}）")
        else:
            # 既存更新
            self.repo.update(code=code, name=name, role=role, active=self.active_var.get())
            messagebox.showinfo("更新", f"従業員情報を更新しました（コード: {code}）")

        self.refresh_table()

    def on_toggle_active(self, active:bool):
        code = self.code_var.get().strip()
        if not code:
            messagebox.showwarning("選択なし", "一覧から従業員を選択してください。")
            return
        self.repo.set_active(code, active)
        self.active_var.set(active)
        self.refresh_table()

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        code = item["values"][0]
        emp = self.repo.get(code)
        if not emp: return
        self.code_var.set(emp["code"])
        self.name_var.set(emp["name"])
        self.role_var.set(emp["role"])
        self.active_var.set(emp["active"])

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in self.repo.list_all():
            self.tree.insert("", "end", values=(r["code"], r["name"], r["role"], "✓" if r["active"] else "-", r["created_at"]))
