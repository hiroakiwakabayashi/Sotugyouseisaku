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

        # 履歴管理
        self.history: list[str] = []
        self.hist_idx: int = -1
        self._is_history_nav = False

        # 左右レイアウト
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # === 左ナビ ===
        self.nav = ctk.CTkFrame(self, width=220)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        ctk.CTkLabel(self.nav, text=cfg.get("app_name", "Kao-Kintai"),
                     font=("Meiryo UI", 18, "bold")).pack(padx=16, pady=(16, 8), anchor="w")

        for text, key in [
            ("🏠 ホーム", "home"),
            ("📷 顔認証 打刻", "face"),
            ("📑 勤怠一覧", "list"),
            ("👤 マイ勤怠", "my"),
            ("🛠 管理者", "admin"),
        ]:
            ctk.CTkButton(self.nav, text=text, command=lambda k=key: self.show(k))\
                .pack(padx=16, pady=6, fill="x")

        self.subnav = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.subnav.pack(padx=8, pady=(8, 12), fill="x", anchor="n")

        # === 右側メイン ===
        self.right = ctk.CTkFrame(self)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        # 上部ヘッダー
        self.header = ctk.CTkFrame(self.right, height=48)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)

        # 履歴ボタン
        ctk.CTkButton(self.header, text="＜", width=42, command=lambda: self._hist(-1))\
            .pack(side="left", padx=(8, 4), pady=6)
        ctk.CTkButton(self.header, text="＞", width=42, command=lambda: self._hist(+1))\
            .pack(side="left", padx=(0, 12), pady=6)

        # 検索バー
        self.search_entry = ctk.CTkEntry(self.header, placeholder_text="検索", width=320)
        self.search_entry.pack(side="left", pady=6)

        # プロフィール
        ctk.CTkButton(self.header, text="👤", width=36)\
            .pack(side="right", padx=8, pady=6)

        # body（右ペイン本体）
        self.body = ctk.CTkFrame(self.right)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        # 各画面キャッシュ
        self._screens = {}
        self.show("home")

    # ===== 管理者メニュー構築 =====
    def _clear_subnav(self):
        for w in self.subnav.winfo_children():
            w.destroy()

    def _build_admin_subnav(self):
        self._clear_subnav()
        ctk.CTkLabel(self.subnav, text="🛠 管理者メニュー", font=("Meiryo UI", 14, "bold"))\
            .pack(padx=8, pady=(6, 4), anchor="w")

        # 呼び出しをクラス基準に修正
        from .screens.employee_register_screen import EmployeeRegisterScreen
        from .screens.face_data_screen import FaceDataScreen
        from .screens.attendance_list_screen import AttendanceListScreen
        from .screens.camera_settings_screen import CameraSettingsScreen
        from .screens.admin_account_screen import AdminAccountScreen

        btns = [
            ("👥 従業員登録 / 編集", lambda: self._swap_right(EmployeeRegisterScreen)),
            ("🖼 顔データ管理",       lambda: self._swap_right(FaceDataScreen)),
            ("📑 勤怠一覧 / 検索",    lambda: self._swap_right(AttendanceListScreen)),
            ("🎥 カメラ・顔認証設定",  lambda: self._swap_right(CameraSettingsScreen)),
            ("🔐 管理者アカウント",   lambda: self._swap_right(AdminAccountScreen)),
        ]

        for label, cmd in btns:
            ctk.CTkButton(self.subnav, text=label, command=cmd).pack(padx=8, pady=4, fill="x")

    # ===== ペイン切り替え =====
    def _swap_right(self, widget_class):
        # まず既存の子を全削除
        for child in self.body.winfo_children():
            child.destroy()
        # 新しいウィジェットを生成して配置
        widget = widget_class(self.body)
        widget.grid(row=0, column=0, sticky="nsew")
        return widget

    # ===== 履歴 =====
    def _hist(self, step: int):
        if step < 0:
            if self.hist_idx <= 0:
                return
            self.hist_idx -= 1
        else:
            if self.hist_idx >= len(self.history) - 1:
                return
            self.hist_idx += 1
        self._is_history_nav = True
        try:
            self.show(self.history[self.hist_idx])
        finally:
            self._is_history_nav = False

    # ===== 画面切替 =====
    def show(self, key: str):
        for child in self.body.winfo_children():
            child.destroy()
        self._clear_subnav()

        if not self._is_history_nav:
            if self.hist_idx < len(self.history) - 1:
                self.history = self.history[:self.hist_idx + 1]
            self.history.append(key)
            self.hist_idx = len(self.history) - 1

        if key == "admin":
            def to_menu():
                # ログイン成功後：左下サブナビ展開＋従業員登録画面表示
                self._build_admin_subnav()
                from .screens.employee_register_screen import EmployeeRegisterScreen
                self._swap_right(EmployeeRegisterScreen)
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
