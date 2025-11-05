# app/gui/screens/admin_account_register_screen.py
import customtkinter as ctk
from tkinter import messagebox
from app.infra.db.admin_repo import AdminRepo

class AdminAccountRegisterScreen(ctk.CTkFrame):
    """管理者アカウント 登録画面（MVP用：必須＋簡易バリデーション）"""

    def __init__(self, master):
        super().__init__(master)
        self.repo = AdminRepo()

        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(self, corner_radius=14)
        card.grid(row=0, column=0, padx=16, pady=16, sticky="n")
        for r in range(8): card.grid_rowconfigure(r, weight=0)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text="🛠 管理者アカウント登録", font=("Meiryo UI", 20, "bold"))\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(16, 6))

        # 入力
        self.username = ctk.CTkEntry(card, placeholder_text="例: admin02")
        self.display  = ctk.CTkEntry(card, placeholder_text="表示名（例: 山田 太郎）")
        self.pw1      = ctk.CTkEntry(card, placeholder_text="パスワード", show="•")
        self.pw2      = ctk.CTkEntry(card, placeholder_text="パスワード（確認）", show="•")

        self._row(card, 1, "ユーザーID", self.username)
        self._row(card, 2, "表示名",     self.display)
        self._row(card, 3, "パスワード", self.pw1)
        self._row(card, 4, "パスワード(確認)", self.pw2)

        self.btn = ctk.CTkButton(card, text="登録する", command=self._save)
        self.btn.grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(8, 14))

        ctk.CTkLabel(card, text="注意: 初期管理者 admin01 は残したままでもOK。登録後はログイン画面で動作確認してください。")\
            .grid(row=6, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 12))

    def _row(self, parent, r, label, widget):
        ctk.CTkLabel(parent, text=label, width=120, anchor="w").grid(row=r, column=0, sticky="w", padx=14, pady=6)
        widget.grid(row=r, column=1, sticky="ew", padx=(0,14), pady=6)

    def _save(self):
        u = self.username.get().strip()
        d = self.display.get().strip()
        p1 = self.pw1.get()
        p2 = self.pw2.get()

        # 最低限のバリデーション
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

        # 既存チェック
        if self.repo.find_by_username(u):
            messagebox.showwarning("重複", "このユーザーIDは既に存在します。")
            return

        self.repo.create(username=u, display_name=d, password_plain=p1, role="admin", is_active=True)
        messagebox.showinfo("登録完了", f"管理者 '{u}' を登録しました。")
        # クリア
        self.username.delete(0, "end"); self.display.delete(0, "end"); self.pw1.delete(0, "end"); self.pw2.delete(0, "end")
