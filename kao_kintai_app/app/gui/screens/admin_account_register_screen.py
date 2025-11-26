import customtkinter as ctk
from tkinter import messagebox
from app.infra.db.admin_repo import AdminRepo


class AdminAccountRegisterScreen(ctk.CTkFrame):
    """管理者アカウント 登録画面
       - ロール選択（admin/su）
       - su の作成は su ログイン時のみ可（UI/保存時で二重チェック）
    """

    def __init__(self, master, current_admin: dict | None = None):
        super().__init__(master)
        self.repo = AdminRepo()
        self.current_admin = current_admin or {}
        self.is_su = (self.current_admin.get("role") == "su")

        # 背景色をログイン画面と合わせる
        self.configure(fg_color="#f5f5f5")

        # ===== 中央の登録パネル =====
        panel = ctk.CTkFrame(
            self,
            corner_radius=20,
            fg_color="white",
            width=850,
            height=550,
        )
        panel.place(relx=0.5, rely=0.5, anchor="center")  # 画面中央に固定配置
        panel.grid_propagate(False)  # 中身でサイズが変わらないよう固定

        # ===== タイトル =====
        ctk.CTkLabel(
            panel,
            text="管理者アカウント登録",
            font=("Meiryo UI", 28, "bold"),
            text_color="#333333",
        ).pack(pady=(40, 20))

        # ===== フォーム部（グリッド） =====
        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.pack(fill="x", padx=60, pady=(0, 10))
        form.grid_columnconfigure(0, weight=0)
        form.grid_columnconfigure(1, weight=1)

        # 入力フィールド
        self.username = ctk.CTkEntry(form, placeholder_text="例: admin02")
        self.display = ctk.CTkEntry(form, placeholder_text="表示名（例: 山田 太郎）")
        self.pw1 = ctk.CTkEntry(form, placeholder_text="パスワード", show="•")
        self.pw2 = ctk.CTkEntry(form, placeholder_text="パスワード（確認）", show="•")

        # ロール選択（su ログイン時のみ su を選べる）
        role_values = ["admin", "su"] if self.is_su else ["admin"]
        self.role_var = ctk.StringVar(value=role_values[0])
        self.role_sel = ctk.CTkOptionMenu(form, values=role_values, variable=self.role_var)

        # 行ごとにラベル＋入力欄を配置
        self._row(form, 0, "ユーザーID", self.username)
        self._row(form, 1, "表示名", self.display)
        self._row(form, 2, "パスワード", self.pw1)
        self._row(form, 3, "パスワード(確認)", self.pw2)
        self._row(form, 4, "権限ロール", self.role_sel)

        # ===== 登録ボタン =====
        btn_frame = ctk.CTkFrame(panel, fg_color="transparent")
        btn_frame.pack(pady=(10, 10))
        self.btn = ctk.CTkButton(
            btn_frame,
            text="登録する",
            width=200,
            height=40,
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
            command=self._save,
        )
        self.btn.grid(row=0, column=0, padx=4, pady=4)

        # ===== 注意書き =====
        tip = "※ su は全権限を持つ特権アカウントです。必要最小限の作成に留めてください。"
        if not self.is_su:
            tip += "（現在のログイン権限では su を作成できません）"
        ctk.CTkLabel(
            panel,
            text=tip,
            text_color="#666666",
            font=("Meiryo UI", 11),
            wraplength=750,
            justify="left",
        ).pack(pady=(0, 12), padx=40, anchor="w")

    def _row(self, parent, r: int, label: str, widget: ctk.CTkBaseClass):
        """ラベル + 入力欄 を1行分配置（ログイン画面風パディングに揃える）"""
        ctk.CTkLabel(
            parent,
            text=label,
            width=120,
            anchor="w",
            text_color="#333333",
        ).grid(row=r, column=0, sticky="w", padx=(0, 12), pady=6)
        widget.grid(row=r, column=1, sticky="ew", pady=6)

    def _save(self):
        u = self.username.get().strip()
        d = self.display.get().strip()
        p1 = self.pw1.get()
        p2 = self.pw2.get()
        role = (self.role_var.get() or "admin").lower()

        # 最低限バリデーション
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

        # su 作成ガード（UI側で選べなくても保存時に再チェック）
        if role == "su" and not self.is_su:
            messagebox.showwarning("権限", "su アカウントの作成は su のみ許可されています。")
            return

        # 重複チェック
        if self.repo.find_by_username(u):
            messagebox.showwarning("重複", "このユーザーIDは既に存在します。")
            return

        # 登録
        self.repo.create(
            username=u,
            display_name=d,
            password_plain=p1,
            role=role,
            is_active=True,
        )
        messagebox.showinfo("登録完了", f"管理者 '{u}'（ロール: {role}）を登録しました。")

        # 入力クリア
        for e in (self.username, self.display, self.pw1, self.pw2):
            e.delete(0, "end")
        # su でなければ admin 固定に戻す
        self.role_var.set("admin")
