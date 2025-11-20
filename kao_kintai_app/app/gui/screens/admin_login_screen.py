# app/gui/screens/admin_login_screen.py
import customtkinter as ctk
from tkinter import messagebox
from app.infra.db.admin_repo import AdminRepo

class AdminLoginScreen(ctk.CTkFrame):
    def __init__(self, master, switch_to_menu_callback, switch_to_home_callback=None):
        super().__init__(master)
        self.switch_to_menu_callback = switch_to_menu_callback
        self.switch_to_home_callback = switch_to_home_callback

        # --- DB連携（初回は admin01/admin01 を自動投入） ---
        self.repo = AdminRepo()
        self.repo.seed_default()

        # ===== 全体設定 =====
        ctk.set_appearance_mode("light")  # 白テーマ
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#f5f5f5")  # 背景薄グレー

        # ===== ログインパネル（中央に大きめ配置） =====
        login_panel = ctk.CTkFrame(
            self, corner_radius=20, fg_color="white",
            width=850, height=550
        )
        login_panel.place(relx=0.5, rely=0.5, anchor="center")  # 中央配置

        # ===== タイトル =====
        ctk.CTkLabel(
            login_panel, text="管理者ログイン",
            font=("Meiryo UI", 28, "bold"), text_color="#333333"
        ).pack(pady=(40, 25))

        # ===== ユーザID =====
        ctk.CTkLabel(login_panel, text="ユーザID", anchor="w", text_color="#333333")\
            .pack(pady=(10, 2), padx=60, fill="x")
        self.id_entry = ctk.CTkEntry(login_panel, placeholder_text="ユーザIDを入力", height=40)
        self.id_entry.pack(pady=(0, 5), padx=60, fill="x")
        self.id_error = ctk.CTkLabel(login_panel, text="", text_color="red", anchor="w")
        self.id_error.pack(pady=(0, 5), padx=60, fill="x")
        self.id_entry.bind("<Return>", lambda e: self.pw_entry.focus_set())

        # ▼【一時対応】画面を開いたときにユーザID入力欄を自動で選択状態にする
        #   - 完成後に元の挙動へ戻したい場合：
        #     → 下の self.after(...) の1行を削除すれば元の状態に戻る。
        #   - after(100, ...) にしている理由：
        #     → ウィジェット描画より前に focus_set() を呼ぶと無視されるため、
        #        100ミリ秒後にフォーカスを当てている。
        self.after(100, lambda: self.id_entry.focus_set())


        # ===== パスワード =====
        ctk.CTkLabel(login_panel, text="パスワード", anchor="w", text_color="#333333")\
            .pack(pady=(15, 2), padx=60, fill="x")
        self.pw_entry = ctk.CTkEntry(login_panel, placeholder_text="パスワードを入力", show="•", height=40)
        self.pw_entry.pack(pady=(0, 5), padx=60, fill="x")
        self.pw_error = ctk.CTkLabel(login_panel, text="", text_color="red", anchor="w")
        self.pw_error.pack(pady=(0, 20), padx=60, fill="x")
        self.pw_entry.bind("<Return>", lambda e: self.try_login())

        # ===== ボタンエリア =====
        btn_frame = ctk.CTkFrame(login_panel, fg_color="transparent")
        btn_frame.pack(pady=15)
        ctk.CTkButton(
            btn_frame, text="ログイン", width=150, height=36,
            fg_color="#0d6efd", hover_color="#0b5ed7",
            command=self.try_login
        ).grid(row=0, column=0, padx=15)
        ctk.CTkButton(
            btn_frame, text="戻る", width=150, height=36,
            fg_color="#adb5bd", hover_color="#999",
            command=self.go_back
        ).grid(row=0, column=1, padx=15)

        # ===== パスワード変更リンク（プレースホルダ） =====
        link = ctk.CTkLabel(login_panel, text="パスワードを変更する", text_color="#0d6efd", cursor="hand2")
        link.pack(pady=(25, 10))
        link.bind("<Button-1>", lambda e: self.show_password_change())

    # ===== ログイン処理（DB照合） =====
    def try_login(self):
        uid = self.id_entry.get().strip()
        pw  = self.pw_entry.get()

        # エラー表示をクリア
        self.id_error.configure(text="")
        self.pw_error.configure(text="")

        if not uid:
            self.id_error.configure(text="※ ユーザIDを入力してください。")
            return
        if not pw:
            self.pw_error.configure(text="※ パスワードを入力してください。")
            return

        user = self.repo.verify_login(uid, pw)
        if not user:
            # IDの存在で出し分け（ほんの少し丁寧に）
            if self.repo.find_by_username(uid):
                self.pw_error.configure(text="※ パスワードが正しくありません。")
            else:
                self.id_error.configure(text="※ ユーザIDが正しくありません。")
            return

        # 成功：必要なら self.master.current_admin = user など
        self.switch_to_menu_callback(user)

    # ===== 戻る処理 =====
    def go_back(self):
        if self.switch_to_home_callback:
            self.switch_to_home_callback()

    # ===== パスワード変更リンク（プレースホルダ） =====
    def show_password_change(self):
        messagebox.showinfo("情報", "パスワード変更画面は現在準備中です。")
