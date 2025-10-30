import customtkinter as ctk

class AdminLoginScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_menu_callback, switch_to_home_callback=None):
        super().__init__(master)
        self.switch_to_menu_callback = switch_to_menu_callback
        self.switch_to_home_callback = switch_to_home_callback

        # ===== 全体設定 =====
        ctk.set_appearance_mode("light")  # 白テーマ
        ctk.set_default_color_theme("blue")

        self.configure(fg_color="#f5f5f5")  # 背景薄グレー

        # ===== ログインパネル（中央に大きめ配置） =====
        login_panel = ctk.CTkFrame(
            self,
            corner_radius=20,
            fg_color="white",
            width=850,   # ← 幅を広げた
            height=550   # ← 高さを広げた
        )
        login_panel.place(relx=0.5, rely=0.5, anchor="center")  # 中央配置

        # ===== タイトル =====
        title = ctk.CTkLabel(
            login_panel,
            text="管理者ログイン",
            font=("Meiryo UI", 28, "bold"),
            text_color="#333333"
        )
        title.pack(pady=(40, 25))

        # ===== ユーザID入力 =====
        id_label = ctk.CTkLabel(login_panel, text="ユーザID", anchor="w", text_color="#333333")
        id_label.pack(pady=(10, 2), padx=60, fill="x")

        self.id_entry = ctk.CTkEntry(login_panel, placeholder_text="ユーザIDを入力", height=40)
        self.id_entry.pack(pady=(0, 5), padx=60, fill="x")

        self.id_error = ctk.CTkLabel(login_panel, text="", text_color="red", anchor="w")
        self.id_error.pack(pady=(0, 5), padx=60, fill="x")
        
        # ここを追加（IDでEnter → パスワード欄へフォーカス）
        self.id_entry.bind("<Return>", lambda e: self.pw_entry.focus_set())

        # ===== パスワード入力 =====
        pw_label = ctk.CTkLabel(login_panel, text="パスワード", anchor="w", text_color="#333333")
        pw_label.pack(pady=(15, 2), padx=60, fill="x")

        self.pw_entry = ctk.CTkEntry(login_panel, placeholder_text="パスワードを入力", show="*", height=40)
        self.pw_entry.pack(pady=(0, 5), padx=60, fill="x")

        self.pw_error = ctk.CTkLabel(login_panel, text="", text_color="red", anchor="w")
        self.pw_error.pack(pady=(0, 20), padx=60, fill="x")

        # ここを追加（PWでEnter → ログイン実行）
        self.pw_entry.bind("<Return>", lambda e: self.try_login())

        # ===== ボタンエリア =====
        btn_frame = ctk.CTkFrame(login_panel, fg_color="transparent")
        btn_frame.pack(pady=15)

        login_btn = ctk.CTkButton(
            btn_frame,
            text="ログイン",
            width=150,
            height=36,
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
            command=self.try_login
        )
        login_btn.grid(row=0, column=0, padx=15)

        back_btn = ctk.CTkButton(
            btn_frame,
            text="戻る",
            width=150,
            height=36,
            fg_color="#adb5bd",
            hover_color="#999",
            command=self.go_back
        )
        back_btn.grid(row=0, column=1, padx=15)

        # ===== パスワード変更リンク =====
        link = ctk.CTkLabel(
            login_panel,
            text="パスワードを変更する",
            text_color="#0d6efd",
            cursor="hand2"
        )
        link.pack(pady=(25, 10))
        link.bind("<Button-1>", lambda e: self.show_password_change())

    # ===== ログイン処理 =====
    def try_login(self):
        uid = self.id_entry.get().strip()
        pw = self.pw_entry.get().strip()

        self.id_error.configure(text="")
        self.pw_error.configure(text="")

        if uid != "admin01":
            self.id_error.configure(text="※ ユーザIDが正しくありません。")
        elif pw != "admin01":
            self.pw_error.configure(text="※ パスワードが正しくありません。")
        else:
            self.switch_to_menu_callback()

    # ===== 戻る処理 =====
    def go_back(self):
        if self.switch_to_home_callback:
            self.switch_to_home_callback()

    # ===== パスワード変更リンク =====
    def show_password_change(self):
        ctk.CTkMessagebox(title="情報", message="パスワード変更画面は現在準備中です。")
