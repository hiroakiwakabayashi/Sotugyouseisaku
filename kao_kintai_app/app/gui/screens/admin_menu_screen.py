import customtkinter as ctk


class AdminMenuScreen(ctk.CTkFrame):
    """
    旧：左に独自メニューを持っていた管理者メニュー画面
    新：AppShell 側のサブナビから呼び出される「コンテンツ用コンテナ」

    - 左メニューは AppShell._build_admin_subnav() に集約したため、このクラスでは持たない
    - 右側コンテンツ領域だけを管理し、show(key) で画面を差し替える
    """

    def __init__(self, master):
        super().__init__(master)

        # ===== レイアウト（単純に 1 枚のコンテンツ領域を持つ） =====
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # コンテンツ領域
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # 現在表示中の画面
        self.current_key: str | None = None

        # 初期表示（例：従業員登録画面）
        self.show("emp")

    # ------------------------------------------------------------------
    # 画面切り替え
    # ------------------------------------------------------------------
    def show(self, key: str):
        """key に応じて右側コンテンツを差し替える"""

        # すでに同じ画面なら何もしない
        if key == self.current_key:
            return
        self.current_key = key

        # 既存ウィジェットを削除
        for w in self.content.winfo_children():
            w.destroy()

        # 遅延インポートで循環依存を回避しつつ画面を生成
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
            # 未実装キー用の簡易プレースホルダ
            screen = ctk.CTkFrame(self.content)
            ctk.CTkLabel(
                screen,
                text=f"🧩 未実装: {key}",
                font=("Meiryo UI", 14),
            ).pack(padx=16, pady=16)

        # コンテンツ領域に配置
        screen.grid(row=0, column=0, sticky="nsew")
