import customtkinter as ctk
import os
import tkinter as tk
from datetime import datetime

from .screens.home_screen import HomeScreen
from .screens.face_clock_screen import FaceClockScreen
from .screens.attendance_list_screen import AttendanceListScreen
from .screens.my_attendance_screen import MyAttendanceScreen
from .screens.admin_login_screen import AdminLoginScreen
from .screens.shift_view_screen import ShiftViewScreen

from app.infra.db.attendance_repo import AttendanceRepo


class AppShell(ctk.CTkFrame):
    def __init__(self, master, cfg: dict):
        super().__init__(master)
        self.cfg = cfg

        self.current_admin = None
        self.history: list[str] = []
        self.hist_idx: int = -1
        self._is_history_nav = False
        self.current_screen = None

        # 検索サジェスト
        self.att_repo = AttendanceRepo()
        self.search_popup: tk.Toplevel | None = None

        # レイアウト
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ===== 左ナビ =====
        self.nav = ctk.CTkFrame(self, width=220)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        ctk.CTkLabel(
            self.nav,
            text=cfg.get("app_name", "Kao-Kintai"),
            font=("Meiryo UI", 18, "bold"),
        ).pack(padx=16, pady=(16, 8), anchor="w")

        for text, key in [
            ("🏠 ホーム", "home"),
            ("📷 顔認証 打刻", "face"),
            ("📑 勤怠一覧", "list"),
            ("🗓 シフト", "shift"),
            ("👤 マイ勤怠", "my"),
            ("🛠 管理者", "admin"),
        ]:
            ctk.CTkButton(
                self.nav, text=text, command=lambda k=key: self.show(k)
            ).pack(padx=16, pady=6, fill="x")

        self.subnav = ctk.CTkFrame(self.nav, fg_color="transparent")
        self.subnav.pack(padx=8, pady=(8, 12), fill="x", anchor="n")

        # ===== 右側メイン =====
        self.right = ctk.CTkFrame(self)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        # --- ヘッダー ---
        self.header = ctk.CTkFrame(self.right, height=48)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_propagate(False)

        ctk.CTkButton(
            self.header, text="＜", width=42, command=lambda: self._hist(-1)
        ).pack(side="left", padx=(8, 4), pady=6)
        ctk.CTkButton(
            self.header, text="＞", width=42, command=lambda: self._hist(+1)
        ).pack(side="left", padx=(0, 12), pady=6)

        # --- Teams風検索ボックス (Entry+✕ 一体化) ---
        self.search_container = ctk.CTkFrame(
            self.header, fg_color="#FFFFFF", corner_radius=18
        )
        self.search_container.pack(side="left", pady=6)

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            self.search_container,
            textvariable=self.search_var,
            placeholder_text="検索（氏名 / コード）",
            width=280,
            border_width=0,
        )
        self.search_entry.pack(side="left", padx=(10, 0), pady=4)

        self.clear_btn = ctk.CTkButton(
            self.search_container,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#E5E7EB",
            text_color="#6B7280",
            corner_radius=12,
            command=self._clear_search,
        )
        self.clear_btn.pack(side="left", padx=(4, 10), pady=4)

        # イベント
        self.search_entry.bind("<KeyRelease>", self._on_search_change)
        self.search_entry.bind("<Return>", self._on_search)
        self.search_entry.bind("<Button-1>", self._on_search_click)

        # プロフィールボタン
        ctk.CTkButton(self.header, text="👤", width=36).pack(
            side="right", padx=8, pady=6
        )

        # --- body ---
        self.body = ctk.CTkFrame(self.right)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self._screens = {}

        # 画面どこかクリックでサジェストを閉じる
        root = self.winfo_toplevel()
        root.bind("<Button-1>", self._on_root_click, add="+")

        self.show("home")

    # ================= 検索系 =================
    def _on_search(self, event=None):
        kw = self.search_var.get().strip()
        if not kw:
            return
        self.show("list")
        if isinstance(self.current_screen, AttendanceListScreen):
            self.current_screen.on_search(kw)
        self._destroy_search_popup()

    def _on_search_change(self, event: tk.Event):
        if event.keysym == "Return":
            return
        kw = self.search_var.get().strip()
        self._update_search_popup(kw)

    def _on_search_click(self, event: tk.Event):
        kw = self.search_var.get().strip()
        if kw:
            self.after(10, lambda: self._update_search_popup(kw))
        else:
            self._destroy_search_popup()

    def _update_search_popup(self, keyword: str):
        """検索キーワードに応じてサジェストポップアップを表示/更新"""
        # 空文字なら閉じる
        if not keyword:
            self._destroy_search_popup()
            return

        # --- 勤怠テーブルから候補抽出 ---
        try:
            rows = self.att_repo.list_records(
                start_date=None, end_date=None, employee_code=None
            )
        except Exception:
            rows = []

        kw = keyword.lower()
        matches = []
        for r in rows:
            name = str(r.get("name", "")).lower()
            code = str(r.get("employee_code", "")).lower()
            if kw in name or kw in code:
                matches.append(r)

        # 日時の新しい順に最大30件
        def _parse_ts(ts: str):
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(ts, fmt)
                except Exception:
                    pass
            try:
                return datetime.fromisoformat(ts.replace(" ", "T"))
            except Exception:
                return datetime.min

        matches.sort(key=lambda r: _parse_ts(r["ts"]), reverse=True)
        matches = matches[:30]

        if not matches:
            self._destroy_search_popup()
            return

        # --- 幅・高さ・位置を決定 ---
        width = max(self.search_container.winfo_width(), 380)
        height = 260  # 固定高さ（中身はスクロール）

        x = self.search_container.winfo_rootx()
        y = self.search_container.winfo_rooty() + self.search_container.winfo_height()

        # --- Toplevel 準備 ---
        if self.search_popup is None or not tk.Toplevel.winfo_exists(self.search_popup):
            self.search_popup = tk.Toplevel(self)
            self.search_popup.overrideredirect(True)
            self.search_popup.attributes("-topmost", True)

        self.search_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.search_popup.lift()
        # フォーカスは常に検索欄に
        self.search_entry.focus_set()

        # 中身クリア
        for w in self.search_popup.winfo_children():
            w.destroy()

        # --- 外枠（白・角丸）---
        outer = ctk.CTkFrame(
            self.search_popup,
            corner_radius=16,
            fg_color="#FFFFFF",
        )
        outer.pack(fill="both", expand=True)

        # 1段目：ヘッダー
        header_row = ctk.CTkFrame(outer, fg_color="#FFFFFF")
        header_row.pack(fill="x", padx=8, pady=(4, 4))

        ctk.CTkLabel(
            header_row,
            text=self.search_var.get(),
            font=("Meiryo UI", 14, "bold"),
            text_color="#111827",
        ).pack(side="left", padx=(8, 6), pady=4)

        ctk.CTkLabel(
            header_row,
            text="Enter キーを押して勤怠一覧を表示。",
            font=("Meiryo UI", 12),
            text_color="#6B7280",
        ).pack(side="left", pady=4)

        # 区切り線
        ctk.CTkFrame(outer, height=1, fg_color="#E5E7EB").pack(
            fill="x", padx=8, pady=(0, 4)
        )

        # 2段目：セクションタイトル
        ctk.CTkLabel(
            outer,
            text="ユーザー",
            font=("Meiryo UI", 11),
            text_color="#6B7280",
        ).pack(anchor="w", padx=14, pady=(2, 4))

        # 3段目：候補一覧（スクロール可能）
        list_container = ctk.CTkScrollableFrame(
            outer,
            fg_color="#FFFFFF",
            corner_radius=0,
        )
        list_container.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        for r in matches:
            name = r.get("name", "")
            ts_text = r["ts"].replace("T", " ")
            label_text = f"{name}   {ts_text}"

            btn = ctk.CTkButton(
                list_container,
                text=label_text,
                anchor="w",
                fg_color="#FFFFFF",
                hover_color="#F3F4F6",
                text_color="#111111",
                corner_radius=8,
                height=32,
                command=lambda rec=r: self._select_search_result(rec),
            )
            btn.pack(fill="x", padx=8, pady=2)

        self.search_popup.update_idletasks()

    def _destroy_search_popup(self):
        if self.search_popup and tk.Toplevel.winfo_exists(self.search_popup):
            self.search_popup.destroy()
        self.search_popup = None

    def _is_child_of_popup(self, widget: tk.Widget) -> bool:
        if self.search_popup is None:
            return False
        w = widget
        while w is not None:
            if w == self.search_popup:
                return True
            w = getattr(w, "master", None)
        return False

    def _is_in_search_box(self, widget: tk.Widget) -> bool:
        w = widget
        while w is not None:
            if w == self.search_container:
                return True
            w = getattr(w, "master", None)
        return False

    def _on_root_click(self, event: tk.Event):
        if self.search_popup is None:
            return
        w = event.widget
        if self._is_in_search_box(w):
            return
        if self._is_child_of_popup(w):
            return
        self._destroy_search_popup()

    def _select_search_result(self, record: dict):
        name = record.get("name", "")
        self.search_var.set(name)
        self._destroy_search_popup()
        self.show("list")
        if isinstance(self.current_screen, AttendanceListScreen):
            self.current_screen.on_search(name)

    def _clear_search(self):
        self.search_var.set("")
        self._destroy_search_popup()
        if isinstance(self.current_screen, AttendanceListScreen):
            self.current_screen.on_search("")

    # =============== サブナビ/画面切替 ===============
    def _clear_subnav(self):
        for w in self.subnav.winfo_children():
            w.destroy()

    def _build_admin_subnav(self):
        self._clear_subnav()
        ctk.CTkLabel(
            self.subnav,
            text="🛠 管理者メニュー",
            font=("Meiryo UI", 14, "bold"),
        ).pack(padx=8, pady=(6, 4), anchor="w")

        role = (self.current_admin or {}).get("role", "admin")

        from .screens.attendance_list_screen import AttendanceListScreen
        ctk.CTkButton(
            self.subnav,
            text="📑 勤怠一覧 / 検索",
            command=lambda: self._swap_right(AttendanceListScreen),
        ).pack(padx=8, pady=4, fill="x")

        if role != "su":
            from .screens.face_data_screen import FaceDataScreen
            ctk.CTkButton(
                self.subnav,
                text="🖼 顔データ管理",
                command=lambda: self._swap_right(FaceDataScreen),
            ).pack(padx=8, pady=4, fill="x")
            return

        from .screens.employee_register_screen import EmployeeRegisterScreen
        from .screens.camera_settings_screen import CameraSettingsScreen
        from .screens.admin_account_register_screen import (
            AdminAccountRegisterScreen,
        )
        from .screens.face_data_screen import FaceDataScreen
        from .screens.shift_editor_screen import ShiftEditorScreen
        from .screens.employee_su_overview_screen import (
            EmployeeSuOverviewScreen,
        )

        ctk.CTkButton(
            self.subnav,
            text="👥 従業員登録 / 編集",
            command=lambda: self._swap_right(EmployeeRegisterScreen),
        ).pack(padx=8, pady=4, fill="x")
        ctk.CTkButton(
            self.subnav,
            text="🎥 カメラ・顔認証設定",
            command=lambda: self._swap_right(CameraSettingsScreen),
        ).pack(padx=8, pady=4, fill="x")
        ctk.CTkButton(
            self.subnav,
            text="🔐 管理者アカウント",
            command=lambda: self._swap_right(
                lambda parent: AdminAccountRegisterScreen(
                    parent, self.current_admin
                )
            ),
        ).pack(padx=8, pady=4, fill="x")
        ctk.CTkButton(
            self.subnav,
            text="🖼 顔データ管理",
            command=lambda: self._swap_right(FaceDataScreen),
        ).pack(padx=8, pady=4, fill="x")
        ctk.CTkButton(
            self.subnav,
            text="🗓 シフト作成 / 編集",
            command=lambda: self._swap_right(ShiftEditorScreen),
        ).pack(padx=8, pady=4, fill="x")
        ctk.CTkButton(
            self.subnav,
            text="📊 従業員一覧（時給）[su]",
            command=lambda: self._swap_right(EmployeeSuOverviewScreen),
        ).pack(padx=8, pady=4, fill="x")

    def _swap_right(self, widget_class_or_factory):
        for child in self.body.winfo_children():
            child.destroy()
        widget = widget_class_or_factory(self.body)
        widget.grid(row=0, column=0, sticky="nsew")
        self.current_screen = widget
        return widget

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

    def show(self, key: str):
        for child in self.body.winfo_children():
            child.destroy()
        self._clear_subnav()

        if not self._is_history_nav:
            if self.hist_idx < len(self.history) - 1:
                self.history = self.history[: self.hist_idx + 1]
            self.history.append(key)
            self.hist_idx = len(self.history) - 1

        if key == "admin":
            def to_menu(user):
                self.current_admin = user
                self._build_admin_subnav()
                if user.get("role") == "su":
                    from .screens.employee_register_screen import (
                        EmployeeRegisterScreen,
                    )

                    self._swap_right(EmployeeRegisterScreen)
                else:
                    from .screens.face_data_screen import FaceDataScreen

                    self._swap_right(FaceDataScreen)

            screen = AdminLoginScreen(
                self.body, switch_to_menu_callback=to_menu
            )
        elif key == "home":
            screen = HomeScreen(self.body)
        elif key == "face":
            screen = FaceClockScreen(self.body)
        elif key == "list":
            screen = AttendanceListScreen(self.body)
        elif key == "my":
            screen = MyAttendanceScreen(self.body)
        elif key == "shift":
            screen = ShiftViewScreen(self.body)
        else:
            screen = HomeScreen(self.body)

        screen.grid(row=0, column=0, sticky="nsew")
        self.current_screen = screen


def run_app(cfg: dict):
    # ===== テーマ & スケールを固定 =====
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    ctk.set_widget_scaling(1.0)   # ウィジェット倍率固定
    ctk.set_window_scaling(1.0)   # ウィンドウ倍率固定

    root = ctk.CTk()
    root.title(cfg.get("app_name", "Kao-Kintai"))

    # フルスクリーン（PCごとに共通レイアウトを保ちつつ全画面表示）
    if os.name == "nt":
        # Windows はズーム（最大化）状態
        root.state("zoomed")
    else:
        # mac / Linux は画面サイズいっぱいに
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{sw}x{sh}+0+0")

    # レイアウト
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    shell = AppShell(master=root, cfg=cfg)
    shell.grid(row=0, column=0, sticky="nsew")

    # 履歴ナビ用ショートカット
    root.bind("<Control-Left>", lambda e: shell._hist(-1))
    root.bind("<Control-Right>", lambda e: shell._hist(+1))

    root.mainloop()
