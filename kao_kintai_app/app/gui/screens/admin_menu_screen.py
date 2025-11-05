import customtkinter as ctk

class AdminMenuScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)

        # レイアウト: 左=メニュー / 右=コンテンツ
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 左メニュー
        self.nav = ctk.CTkFrame(self, width=260)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        ctk.CTkLabel(self.nav, text="🛠 管理者メニュー", font=("Meiryo UI", 20, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

        btns = [
            ("👥 従業員登録 / 編集", lambda: self.show("emp")),
            ("🖼 顔データ管理",       lambda: self.show("face")),
            ("📑 勤怠一覧 / 検索",    lambda: self.show("att")),
            ("🎥 カメラ・顔認証設定",  lambda: self.show("cam")),
            ("🔐 管理者アカウント",   lambda: self.show("acct")),
        ]
        for label, cmd in btns:
            ctk.CTkButton(self.nav, text=label, command=cmd).pack(padx=16, pady=6, fill="x")

        # 右コンテンツ領域
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # 初期表示
        self.show("emp")

    def show(self, key: str):
        # 右側を差し替え
        for w in self.content.winfo_children():
            w.destroy()

        # ← ここで遅延インポート（読み込み順や存在ミスの影響を低減）
        if key == "emp":
            from .employee_register_screen import EmployeeRegisterScreen
            screen = EmployeeRegisterScreen(self.content)
        elif key == "face":
            from .face_data_screen import FaceDataScreen
            screen = FaceDataScreen(self.content)
        elif key == "att":
            from .attendance_list_screen import AttendanceListScreen
            screen = AttendanceListScreen(self.content)
        elif key == "cam":
            from .camera_settings_screen import CameraSettingsScreen
            screen = CameraSettingsScreen(self.content)
        elif key == "acct":
            from .admin_account_register_screen import AdminAccountRegisterScreen
            screen = AdminAccountRegisterScreen(self.content)
        else:
            screen = ctk.CTkFrame(self.content)
            ctk.CTkLabel(screen, text=f"🧩 未実装: {key}").pack(padx=16, pady=16)
        screen.grid(row=0, column=0, sticky="nsew")
