import customtkinter as ctk

class AdminLoginScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_menu_callback):
        super().__init__(master)
        self.switch_to_menu_callback = switch_to_menu_callback

        title = ctk.CTkLabel(self, text="🔑 管理者ログイン", font=("Meiryo UI", 22, "bold"))
        title.pack(pady=(40,20))

        # ID入力
        self.id_entry = ctk.CTkEntry(self, placeholder_text="管理者ID")
        self.id_entry.pack(pady=10, padx=20)

        # パスワード入力
        self.pw_entry = ctk.CTkEntry(self, placeholder_text="パスワード", show="*")
        self.pw_entry.pack(pady=10, padx=20)

        # ステータス表示
        self.status = ctk.CTkLabel(self, text="")
        self.status.pack(pady=10)

        # ログインボタン
        login_btn = ctk.CTkButton(self, text="ログイン", command=self.try_login)
        login_btn.pack(pady=20)

    def try_login(self):
        uid = self.id_entry.get().strip()
        pw = self.pw_entry.get().strip()

        if uid == "admin01" and pw == "admin01":
            self.switch_to_menu_callback()  # 認証成功したら管理者メニューへ
        else:
            self.status.configure(text="❌ IDまたはパスワードが違います", text_color="red")
