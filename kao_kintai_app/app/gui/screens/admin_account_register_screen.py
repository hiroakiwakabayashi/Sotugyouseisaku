import customtkinter as ctk
from tkinter import messagebox
from app.infra.db.admin_repo import AdminRepo


class AdminAccountRegisterScreen(ctk.CTkFrame):
    """管理者アカウント 登録画面"""

    def __init__(self, master, current_admin: dict | None = None):
        super().__init__(master)
        self.repo = AdminRepo()
        self.current_admin = current_admin or {}
        self.is_su = (self.current_admin.get("role") == "su")

        # 背景色
        self.configure(fg_color="#f5f5f5")

        # ===== 中央パネル（BODYを大きく）=====
        panel = ctk.CTkFrame(
            self,
            corner_radius=20,
            fg_color="white",
            width=900,     # ← 少し拡張
            height=600,    # ← 少し拡張
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")
        panel.grid_propagate(False)

        # ===== タイトル =====
        ctk.CTkLabel(
            panel,
            text="管理者アカウント登録",
            font=("Meiryo UI", 28, "bold"),
            text_color="#333333",
        ).pack(pady=(40, 30))

        # ===== フォーム =====
        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.pack(fill="x", padx=80, pady=(0, 30))
        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)

        # 入力フィールド
        self.username = ctk.CTkEntry(form, placeholder_text="例: admin02", font=("Meiryo UI", 15))
        self.display  = ctk.CTkEntry(form, placeholder_text="表示名（例: 山田 太郎）", font=("Meiryo UI", 15))
        self.pw1      = ctk.CTkEntry(form, placeholder_text="パスワード", show="•", font=("Meiryo UI", 15))
        self.pw2      = ctk.CTkEntry(form, placeholder_text="パスワード（確認）", show="•", font=("Meiryo UI", 15))

        role_values = ["admin", "su"] if self.is_su else ["admin"]
        self.role_var = ctk.StringVar(value=role_values[0])
        self.role_sel = ctk.CTkOptionMenu(
            form,
            values=role_values,
            variable=self.role_var,
            font=("Meiryo UI", 15),
        )

        # 行配置
        self._row(form, 0, "ユーザーID", self.username)
        self._row(form, 1, "表示名", self.display)
        self._row(form, 2, "パスワード", self.pw1)
        self._row(form, 3, "パスワード（確認）", self.pw2)
        self._row(form, 4, "権限ロール", self.role_sel)

        # ===== ボタン =====
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.pack(pady=(10, 20))

        self.btn = ctk.CTkButton(
            btn_frame,
            text="登録する",
            width=220,
            height=44,
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
            font=("Meiryo UI", 15, "bold"),  # ← BOLD
            command=self._save,
        )
        self.btn.grid(row=0, column=0, padx=8, pady=8)

        # ===== 注意書き =====
        tip = "※ su は全権限を持つ特権アカウントです。必要最小限の作成に留めてください。"
        if not self.is_su:
            tip += "（現在のログイン権限では su を作成できません）"

        ctk.CTkLabel(
            panel,
            text=tip,
            text_color="#666666",
            font=("Meiryo UI", 13),   # ← タイトル以外なので 15 未満で補助扱い
            wraplength=780,
            justify="left",
        ).pack(pady=(0, 16), padx=60, anchor="w")

    def _row(self, parent, r: int, label: str, widget: ctk.CTkBaseClass):
        """ラベル + 入力欄"""
        ctk.CTkLabel(
            parent,
            text=label,
            width=140,
            anchor="w",
            text_color="#333333",
            font=("Meiryo UI", 15),
        ).grid(row=r, column=0, sticky="w", padx=(0, 16), pady=10)
        widget.grid(row=r, column=1, sticky="ew", pady=10)

    def _save(self):
        u = self.username.get().strip()
        d = self.display.get().strip()
        p1 = self.pw1.get()
        p2 = self.pw2.get()
        role = (self.role_var.get() or "admin").lower()

        if not u or not d or not p1 or not p2:
            messagebox.showwarning("入力不足", "全ての項目を入力してください。")
            return
        if len(u) < 4:
            messagebox.showwarning("ユーザーID", "ユーザーIDは4文字以上にしてください。")
            return
        if p1 != p2:
            messagebox.showwarning("パスワード不一致", "確認用と一致しません。")
            return
        if len(p1) < 6:
            messagebox.showwarning("パスワード", "6文字以上を推奨します。")
            return
        if role not in ("admin", "su"):
            messagebox.showwarning("ロール", "ロールは admin または su を選択してください。")
            return
        if role == "su" and not self.is_su:
            messagebox.showwarning("権限", "su アカウントの作成は su のみ許可されています。")
            return
        if self.repo.find_by_username(u):
            messagebox.showwarning("重複", "このユーザーIDは既に存在します。")
            return

        self.repo.create(
            username=u,
            display_name=d,
            password_plain=p1,
            role=role,
            is_active=True,
        )
        messagebox.showinfo("登録完了", f"管理者 '{u}'（ロール: {role}）を登録しました。")

        for e in (self.username, self.display, self.pw1, self.pw2):
            e.delete(0, "end")
        self.role_var.set("admin")
