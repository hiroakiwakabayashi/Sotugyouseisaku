# app_shell.py
import customtkinter as ctk
import os

from .screens.home_screen import HomeScreen
from .screens.face_clock_screen import FaceClockScreen
from .screens.attendance_list_screen import AttendanceListScreen
from .screens.my_attendance_screen import MyAttendanceScreen
from .screens.admin_login_screen import AdminLoginScreen


class AppShell(ctk.CTkFrame):
    def __init__(self, master, cfg: dict):
        super().__init__(master)
        self.cfg = cfg

        # 履歴
        self.history: list[str] = []
        self.hist_idx: int = -1
        self._is_history_nav = False

        # 左=ナビ / 右=コンテンツ（ヘッダー+ボディ）
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- 左ナビ ---
        self.nav = ctk.CTkFrame(self, width=220)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        title = ctk.CTkLabel(self.nav, text=cfg.get("app_name","Kao-Kintai"),
                             font=("Meiryo UI",18,"bold"))
        title.pack(padx=16, pady=(16,8), anchor="w")

        for text, key in [
            ("🏠 ホーム","home"),
            ("📷 顔認証 打刻","face"),
            ("📑 勤怠一覧","list"),
            ("👤 マイ勤怠","my"),
            ("🛠 管理者","admin"),
        ]:
            ctk.CTkButton(self.nav, text=text, command=lambda k=key: self.show(k))\
                .pack(padx=16, pady=6, fill="x")

        self.subnav = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.subnav.pack(padx=8, pady=(8,12), fill="x", anchor="n")

        # --- 右側：共通ヘッダー + 本体 ---
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)      # body が伸びる
        right.grid_columnconfigure(0, weight=1)

        # 共通ヘッダー（Teams風のボタン群）
        self.header = ctk.CTkFrame(right, height=48)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)

        # 戻る/進む
        ctk.CTkButton(self.header, text="＜", width=42, command=lambda: self._hist(-1))\
            .pack(side="left", padx=(8,4), pady=6)
        ctk.CTkButton(self.header, text="＞", width=42, command=lambda: self._hist(+1))\
            .pack(side="left", padx=(0,12), pady=6)

        # 検索
        self.search_entry = ctk.CTkEntry(self.header, placeholder_text="検索", width=320)
        self.search_entry.pack(side="left", pady=6)

        # 右寄せ（プロフィール）
        ctk.CTkButton(self.header, text="👤", width=36)\
            .pack(side="right", padx=8, pady=6)

        # 画面本体（差し替え先）
        self.body = ctk.CTkFrame(right)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self._screens = {}
        self.show("home")

    # ---- 履歴ナビ ----
    def _hist(self, step: int):
        if step < 0:
            if self.hist_idx <= 0: return
            self.hist_idx -= 1
        else:
            if self.hist_idx >= len(self.history) - 1: return
            self.hist_idx += 1
        self._is_history_nav = True
        try:
            self.show(self.history[self.hist_idx])
        finally:
            self._is_history_nav = False

    # ---- 右ペイン差し替え ----
    def _swap_right(self, widget: ctk.CTkFrame):
        for child in self.body.winfo_children():
            child.destroy()
        widget.grid(row=0, column=0, sticky="nsew")

    # ---- 画面表示 ----
    def show(self, key: str):
        for child in self.body.winfo_children():
            child.destroy()

        if not self._is_history_nav:
            if self.hist_idx < len(self.history) - 1:
                self.history = self.history[:self.hist_idx+1]
            self.history.append(key)
            self.hist_idx = len(self.history) - 1

        if key == "admin":
            def to_menu():
                from .screens.employee_register_screen import EmployeeRegisterScreen
                self._swap_right(EmployeeRegisterScreen(self.body))
            screen = AdminLoginScreen(self.body, switch_to_menu_callback=to_menu)
        elif key == "home":
            screen = HomeScreen(self.body)
        elif key == "face":
            screen = FaceClockScreen(self.body)
        elif key == "list":
            screen = AttendanceListScreen(self.body)
        elif key == "my":
            screen = MyAttendanceScreen(self.body)
        else:
            screen = HomeScreen(self.body)

        screen.grid(row=0, column=0, sticky="nsew")


def run_app(cfg: dict):
    # テーマとスケール（DPI二重拡大を避けるため1.0固定）
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)

    root = ctk.CTk()
    root.title(cfg.get("app_name", "Kao-Kintai"))

    # ルートのグリッド（ヘッダー/本体を入れる親に合わせる）
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    shell = AppShell(master=root, cfg=cfg)
    shell.grid(row=0, column=0, sticky="nsew")

    # OS標準の最大化でフル表示（タスクバー/影/移動 全部OK）
    if os.name == "nt":
        root.state("zoomed")
    else:
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{sw}x{sh}+0+0")

    # 戻る/進むショートカット（任意）
    root.bind("<Control-Left>",  lambda e: shell._hist(-1))
    root.bind("<Control-Right>", lambda e: shell._hist(+1))

    root.mainloop()
