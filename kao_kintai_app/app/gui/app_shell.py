import customtkinter as ctk
import os

from .screens.home_screen import HomeScreen
from .screens.face_clock_screen import FaceClockScreen
from .screens.attendance_list_screen import AttendanceListScreen
from .screens.admin_menu_screen import AdminMenuScreen
from .screens.my_attendance_screen import MyAttendanceScreen
from .screens.admin_login_screen import AdminLoginScreen
from app.services.config_service import ConfigService

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

        # タイトル（設定から）
        app_name = ConfigService().get_app_name()
        ctk.CTkLabel(self.nav, text=app_name, font=("Meiryo UI", 16, "bold")).pack(
            anchor="w", padx=12, pady=(8, 6)
        )

        # ナビボタン
        self.btn_home  = ctk.CTkButton(self.nav, text="🏠 ホーム",      command=lambda: self.show("home"))
        self.btn_face  = ctk.CTkButton(self.nav, text="📷 顔認証 打刻", command=lambda: self.show("face"))
        self.btn_list  = ctk.CTkButton(self.nav, text="📑 勤怠一覧",     command=lambda: self.show("list"))
        self.btn_my    = ctk.CTkButton(self.nav, text="👤 マイ勤怠",     command=lambda: self.show("my"))
        self.btn_admin = ctk.CTkButton(self.nav, text="🛠 管理者",       command=lambda: self.show("admin"))
        for w in (self.btn_home, self.btn_face, self.btn_list, self.btn_my, self.btn_admin):
            w.pack(padx=16, pady=6, fill="x")

        # --- 右コンテンツ ---
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # 画面キャッシュ
        self._screens: dict[str, ctk.CTkFrame] = {}

        # 初期表示
        self.show("home")

    def show(self, key: str):
        """画面切替（必要に応じて遅延生成）"""
        # 既にあれば再利用、なければ作成
        if key not in self._screens:
            if key == "home":
                self._screens[key] = HomeScreen(self.content, show_callback=self.show)
            elif key == "face":
                self._screens[key] = FaceClockScreen(self.content)
            elif key == "list":
                self._screens[key] = AttendanceListScreen(self.content)
            elif key == "my":
                self._screens[key] = MyAttendanceScreen(self.content)
            elif key == "admin":
                def to_menu():
                    self._screens["admin_menu"] = AdminMenuScreen(self.content)
                    self._swap(self._screens["admin_menu"])
                self._screens[key] = AdminLoginScreen(self.content, switch_to_menu_callback=to_menu)
            else:
                self._screens[key] = HomeScreen(self.content, show_callback=self.show)

        self._swap(self._screens[key])

    def _swap(self, frame: ctk.CTkFrame):
        for w in self.content.winfo_children():
            w.grid_forget()
        frame.grid(row=0, column=0, sticky="nsew")


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
