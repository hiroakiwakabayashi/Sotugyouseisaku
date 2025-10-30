import customtkinter as ctk
import os

from .screens.home_screen import HomeScreen
from .screens.face_clock_screen import FaceClockScreen
from .screens.attendance_list_screen import AttendanceListScreen
from .screens.my_attendance_screen import MyAttendanceScreen
from .screens.admin_login_screen import AdminLoginScreen
# AdminMenuScreen は使わず、ボタンだけ左下に出す方式に変更

class AppShell(ctk.CTkFrame):
    def __init__(self, master, cfg: dict):
        super().__init__(master)
        self.cfg = cfg

        # レイアウト: 左=ナビ / 右=コンテンツ
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- 左ナビ ---
        self.nav = ctk.CTkFrame(self, width=220)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        title = ctk.CTkLabel(self.nav, text=cfg.get("app_name", "Kao-Kintai"),
                             font=("Meiryo UI", 18, "bold"))
        title.pack(padx=16, pady=(16, 8), anchor="w")

        self.btn_home  = ctk.CTkButton(self.nav, text="🏠 ホーム",       command=lambda: self.show("home"))
        self.btn_face  = ctk.CTkButton(self.nav, text="📷 顔認証 打刻",   command=lambda: self.show("face"))
        self.btn_list  = ctk.CTkButton(self.nav, text="📑 勤怠一覧",     command=lambda: self.show("list"))
        self.btn_my    = ctk.CTkButton(self.nav, text="👤 マイ勤怠",     command=lambda: self.show("my"))
        self.btn_admin = ctk.CTkButton(self.nav, text="🛠 管理者",       command=lambda: self.show("admin"))

        for w in (self.btn_home, self.btn_face, self.btn_list, self.btn_my, self.btn_admin):
            w.pack(padx=16, pady=6, fill="x")

        # ← ここがポイント：左下の“サブナビ”領域（管理者メニューをここに出す）
        self.subnav = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.subnav.pack(padx=8, pady=(8, 12), fill="x", anchor="n")

        # --- 右コンテンツ ---
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # 画面インスタンス（必要な時に作成）
        self._screens = {}

        # 既定はホーム
        self.show("home")

    # サブナビを空にする
    def _clear_subnav(self):
        for w in self.subnav.winfo_children():
            w.destroy()

    # サブナビに管理者メニューを描画
    def _build_admin_subnav(self):
        self._clear_subnav()
        ctk.CTkLabel(self.subnav, text="🛠 管理者メニュー", font=("Meiryo UI", 14, "bold"))\
            .pack(padx=8, pady=(6, 4), anchor="w")

        # 右側に出す画面切替ハンドラ
        def show_emp():
            from .screens.employee_register_screen import EmployeeRegisterScreen
            self._swap_right(EmployeeRegisterScreen(self.content))
        def show_face():
            from .screens.face_data_screen import FaceDataScreen
            self._swap_right(FaceDataScreen(self.content))
        def show_att():
            from .screens.attendance_list_screen import AttendanceListScreen
            self._swap_right(AttendanceListScreen(self.content))
        def show_cam():
            from .screens.camera_settings_screen import CameraSettingsScreen
            self._swap_right(CameraSettingsScreen(self.content))
        def show_acct():
            from .screens.admin_account_screen import AdminAccountScreen
            self._swap_right(AdminAccountScreen(self.content))

        btns = [
            ("👥 従業員登録 / 編集", show_emp),
            ("🖼 顔データ管理",       show_face),
            ("📑 勤怠一覧 / 検索",    show_att),
            ("🎥 カメラ・顔認証設定",  show_cam),
            ("🔐 管理者アカウント",   show_acct),
        ]
        for label, cmd in btns:
            ctk.CTkButton(self.subnav, text=label, command=cmd)\
                .pack(padx=8, pady=4, fill="x")

    # 右ペインの差し替え
    def _swap_right(self, widget: ctk.CTkFrame):
        for child in self.content.winfo_children():
            child.destroy()
        widget.grid(row=0, column=0, sticky="nsew")

    def show(self, key: str):
        # 右側まずクリア
        for child in self.content.winfo_children():
            child.destroy()
        # サブナビも一旦クリア
        self._clear_subnav()

        if key == "home":
            self._screens[key] = HomeScreen(self.content)
        elif key == "face":
            self._screens[key] = FaceClockScreen(self.content)
        elif key == "list":
            self._screens[key] = AttendanceListScreen(self.content)
        elif key == "my":
            self._screens[key] = MyAttendanceScreen(self.content)
        elif key == "admin":
            # まず管理者ログインを右側に表示
            def to_menu():
                # ログインOK後：左下に管理者メニューを展開し、デフォルトで従業員登録を表示
                self._build_admin_subnav()
                from .screens.employee_register_screen import EmployeeRegisterScreen
                self._swap_right(EmployeeRegisterScreen(self.content))

            self._screens[key] = AdminLoginScreen(self.content, switch_to_menu_callback=to_menu)
        else:
            self._screens[key] = HomeScreen(self.content)

        self._screens[key].grid(row=0, column=0, sticky="nsew")


def run_app(cfg: dict):
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.set_widget_scaling(1.1)
    ctk.set_window_scaling(1.1)

    root = ctk.CTk()
    root.title(cfg.get("app_name", "Kao-Kintai"))

    # 起動直後に最大化
    def maximize():
        if os.name == "nt":
            root.state("zoomed")
        else:
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")
    root.after(0, maximize)

    shell = AppShell(master=root, cfg=cfg)
    shell.pack(fill="both", expand=True)

    root.mainloop()
