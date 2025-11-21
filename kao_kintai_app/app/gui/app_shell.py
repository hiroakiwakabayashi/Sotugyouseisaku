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

        # ===== レイアウト =====
        # 左ナビは幅固定（weight=0）、右側だけ伸縮（weight=1）
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ===== 左ナビ =====
        # 幅 220px 固定・子ウィジェットでサイズが変わらないよう grid_propagate(False)
        self.nav = ctk.CTkFrame(self, width=220)
        self.nav.grid(row=0, column=0, sticky="nsw")
        self.nav.grid_propagate(False)

        ctk.CTkLabel(
            self.nav,
            text=cfg.get("app_name", "Kao-Kintai"),
            font=("Meiryo UI", 18, "bold"),
        ).pack(padx=16, pady=(16, 8), anchor="w")

        # 左ナビボタンの統一スタイル
        nav_btn_kwargs = dict(
            width=170,
            height=34,
            corner_radius=8,
            anchor="center",
            font=("Meiryo UI", 14),
        )

        for text, key in [
            ("🏠 ホーム", "home"),
            ("📷 顔認証 打刻", "face"),
            ("📑 勤怠一覧", "list"),
            ("🗓 シフト", "shift"),
            ("👤 マイ勤怠", "my"),
            ("🛠 管理者", "admin"),
        ]:
            ctk.CTkButton(
                self.nav,
                text=text,
                command=lambda k=key: self.show(k),
                **nav_btn_kwargs,
            ).pack(padx=16, pady=5)

        # 管理者用サブナビ
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

        # --- プロフィールボタン（元コード）
        # ctk.CTkButton(self.header, text="👤", width=36).pack(
        #     side="right", padx=8, pady=6
        # )

        # ▼【追加】プロフィールボタン（押すとメニュー表示）
        self.profile_btn = ctk.CTkButton(
            self.header, text="👤", width=36, command=self._toggle_profile_menu
        )
        self.profile_btn.pack(side="right", padx=8, pady=6)

        # ▼【追加】プロフィールメニュー用 Toplevel
        self.profile_menu: tk.Toplevel | None = None

        # --- body ---
        self.body = ctk.CTkFrame(self.right)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_columnconfigure(0, weight=1)

        self._screens = {}

        # 画面どこかクリックでサジェストを閉じる
        root = self.winfo_toplevel()
        root.bind("<Button-1>", self._on_root_click, add="+")
        # ▼【サジェスト用】ウィンドウ移動・リサイズ・最小化時の処理
        #   - 位置を追従させる
        #   - 最小化されたらサジェストを閉じる
        root.bind("<Configure>", self._on_root_configure, add="+")
        # ウィンドウが最小化（タスクバーにしまわれる）されたときにサジェストを閉じる
        root.bind("<Unmap>", self._on_root_unmap, add="+")
        root.bind("<FocusOut>", self._on_root_focus_out, add="+")

        self.show("home")

    def _on_root_focus_out(self, event: tk.Event):
        """別アプリをアクティブにしたときなど、rootのフォーカスが外れたら閉じる"""
        self._destroy_search_popup()
        self._destroy_profile_menu()


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

        # --- Toplevel 準備 ---
        if self.search_popup is None or not tk.Toplevel.winfo_exists(self.search_popup):
            self.search_popup = tk.Toplevel(self)
            self.search_popup.overrideredirect(True)

            # 親ウィンドウに紐づける（別アプリを前面に出したら一緒に隠れる）
            root = self.winfo_toplevel()
            self.search_popup.transient(root)

        # ▼位置だけを別メソッドで更新
        self._update_search_popup_position()

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

    def _update_search_popup_position(self):
        # 検索ボックスの位置に合わせてサジェストポップアップを動かす #
        if self.search_popup is None or not tk.Toplevel.winfo_exists(self.search_popup):
            return

        # 検索ボックス直下の位置に追従させる
        width = max(self.search_container.winfo_width(), 380)
        height = 260  # _update_search_popup と同じ高さ

        x = self.search_container.winfo_rootx()
        y = self.search_container.winfo_rooty() + self.search_container.winfo_height()

        self.search_popup.geometry(f"{width}x{height}+{x}+{y}")
        self.search_popup.lift()
        
    def _on_root_configure(self, event: tk.Event):
        """ウィンドウのサイズ変更・移動・状態変更時の共通処理"""
        root = self.winfo_toplevel()
        state = str(root.state())

        # ▼最小化（iconic）または非表示（withdrawn）のときだけポップアップを閉じる
        if state in ("iconic", "withdrawn"):
            self._destroy_search_popup()
            self._destroy_profile_menu()
            return

        # それ以外（normal / zoomed）は「表示されたまま」位置だけ追従させる
        self._update_search_popup_position()

    def _on_root_unmap(self, event: tk.Event):
        """ウィンドウが最小化されたときに呼ばれる（<Unmap>）"""
        # ルートウィンドウがタスクバーにしまわれたタイミングで、
        # 画面上にサジェストだけ取り残されないよう必ず破棄する。
        self._destroy_search_popup()
        self._destroy_profile_menu()


    def _destroy_search_popup(self):
        if self.search_popup and tk.Toplevel.winfo_exists(self.search_popup):
            self.search_popup.destroy()
        self.search_popup = None

    def _destroy_profile_menu(self):
        """プロフィールメニューを閉じる"""
        if self.profile_menu and tk.Toplevel.winfo_exists(self.profile_menu):
            self.profile_menu.destroy()
        self.profile_menu = None

    # ================= プロフィールメニュー =================

    def _toggle_profile_menu(self):
        """プロフィールメニューを開閉"""

        # すでに開いている場合は閉じる（トグル）
        if self.profile_menu and tk.Toplevel.winfo_exists(self.profile_menu):
            self._destroy_profile_menu()
            return

        # current_admin が None の場合はメニュー表示しない
        user = self.current_admin
        if not user:
            return

        # --- Toplevel 作成 ---
        self.profile_menu = tk.Toplevel(self)
        self.profile_menu.withdraw() 

        # いったん非表示のまま設定・レイアウトを行う
        self.profile_menu.withdraw()

        self.profile_menu.overrideredirect(True)
        self.profile_menu.attributes("-topmost", True)  # 以前と同じく最前面フラグ

        # 親ウィンドウ（root）と連動させる
        root = self.winfo_toplevel()
        self.profile_menu.transient(root)

        # --- 外枠 ---
        outer = ctk.CTkFrame(self.profile_menu, corner_radius=12, fg_color="white")
        outer.pack(fill="both", expand=True)

        # ========= 管理者情報部分 =========
        name = user.get("name") or user.get("username", "Unknown")
        role_code = user.get("role", "admin")
        role_label = "システム管理者" if role_code == "su" else "一般管理者"

        # 情報表示用フレーム（3列グリッド）
        info_frame = ctk.CTkFrame(outer, fg_color="white")
        info_frame.pack(fill="x", padx=12, pady=(12, 8))

        # 1行目：名前
        ctk.CTkLabel(
            info_frame,
            text=f"👤 {name}",
            font=("Meiryo UI", 14, "bold"),
            text_color="#111",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        label_width = 60  # 「ID」「権限」の幅をそろえる

        # 2行目：ID
        ctk.CTkLabel(
            info_frame,
            text="ID",
            width=label_width,
            anchor="center",
            font=("Meiryo UI", 12),
        ).grid(row=1, column=0, sticky="w", pady=2)

        ctk.CTkLabel(
            info_frame,
            text="：",
            width=10,
            font=("Meiryo UI", 12),
        ).grid(row=1, column=1, sticky="w", pady=2)

        ctk.CTkLabel(
            info_frame,
            text=user.get("username", "-"),
            font=("Meiryo UI", 12),
        ).grid(row=1, column=2, sticky="w", pady=2)

        # 3行目：権限
        ctk.CTkLabel(
            info_frame,
            text="権限",
            width=label_width,
            anchor="center",
            font=("Meiryo UI", 12),
        ).grid(row=2, column=0, sticky="w", pady=2)

        ctk.CTkLabel(
            info_frame,
            text="：",
            width=10,
            font=("Meiryo UI", 12),
        ).grid(row=2, column=1, sticky="w", pady=2)

        ctk.CTkLabel(
            info_frame,
            text=role_label,
            font=("Meiryo UI", 12),
        ).grid(row=2, column=2, sticky="w", pady=2)

        # 区切り線
        ctk.CTkFrame(outer, height=1, fg_color="#E5E7EB").pack(
            fill="x", padx=8, pady=(4, 4)
        )

        # ========= ログアウトボタン =========
        logout_btn = ctk.CTkButton(
            outer,
            text="🔓  ログアウト",
            fg_color="#ef4444",
            hover_color="#dc2626",
            text_color="white",
            corner_radius=10,
            height=44,
            font=("Meiryo UI", 14, "bold"),
            command=self._logout_admin,
        )
        logout_btn.pack(fill="x", padx=16, pady=(12, 16))

        # ===== 実サイズ確定後に、「👤ボタンのすぐ下・右端ぴったり」に配置 =====
        self.profile_menu.update_idletasks()

        # ボタンの画面座標とサイズ
        bx = self.profile_btn.winfo_rootx()
        by = self.profile_btn.winfo_rooty()
        bw = self.profile_btn.winfo_width()
        bh = self.profile_btn.winfo_height()

        # メニューの実サイズ
        menu_w = self.profile_menu.winfo_width()
        menu_h = self.profile_menu.winfo_height()

        # メニュー右端 = ボタン右端
        x = bx + bw - menu_w
        # メニュー上端 = ボタン下端 + 4px
        y = by + bh + 4

        # 位置を反映して表示
        self.profile_menu.geometry(f"{menu_w}x{menu_h}+{x}+{y}")
        self.profile_menu.deiconify()

    def _logout_admin(self):
        """管理者をログアウトさせる"""
        # メニューを閉じる
        self._destroy_profile_menu()

        # 管理者情報をクリア
        self.current_admin = None
        self._clear_subnav()

        # ホーム画面へ戻す
        self.show("home")

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

        # 左ナビとほぼ同じボタンスタイルに統一
        admin_btn_style = dict(
            width=170,
            height=34,
            corner_radius=8,
            anchor="center",
            font=("Meiryo UI", 13),
        )

        from .screens.attendance_list_screen import AttendanceListScreen
        ctk.CTkButton(
            self.subnav,
            text="📑 勤怠一覧 / 検索",
            command=lambda: self._swap_right(AttendanceListScreen),
            **admin_btn_style,
        ).pack(padx=8, pady=4)

        if role != "su":
            from .screens.face_data_screen import FaceDataScreen
            ctk.CTkButton(
                self.subnav,
                text="🖼 顔データ管理",
                command=lambda: self._swap_right(FaceDataScreen),
                **admin_btn_style,
            ).pack(padx=8, pady=4)
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
            **admin_btn_style,
        ).pack(padx=8, pady=4)
        ctk.CTkButton(
            self.subnav,
            text="🎥 カメラ・顔認証設定",
            command=lambda: self._swap_right(CameraSettingsScreen),
            **admin_btn_style,
        ).pack(padx=8, pady=4)
        ctk.CTkButton(
            self.subnav,
            text="🔐 管理者アカウント",
            command=lambda: self._swap_right(
                lambda parent: AdminAccountRegisterScreen(
                    parent, self.current_admin
                )
            ),
            **admin_btn_style,
        ).pack(padx=8, pady=4)
        ctk.CTkButton(
            self.subnav,
            text="🖼 顔データ管理",
            command=lambda: self._swap_right(FaceDataScreen),
            **admin_btn_style,
        ).pack(padx=8, pady=4)
        ctk.CTkButton(
            self.subnav,
            text="🗓 シフト作成 / 編集",
            command=lambda: self._swap_right(ShiftEditorScreen),
            **admin_btn_style,
        ).pack(padx=8, pady=4)
        ctk.CTkButton(
            self.subnav,
            text="📊 従業員一覧（時給）",
            command=lambda: self._swap_right(EmployeeSuOverviewScreen),
            **admin_btn_style,
        ).pack(padx=8, pady=4)


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
        # 画面本体をいったんクリア
        for child in self.body.winfo_children():
            child.destroy()
        self._clear_subnav()

        # ▼ 管理者画面以外へ遷移する場合は、管理者ログイン状態を解除する
        #   - 左メニューから「ホーム」「勤怠一覧」などに直接移動したとき
        #   - 右上プロフィールメニューも未ログイン状態にする
        if key != "admin":
            self.current_admin = None
            self._destroy_profile_menu()

        # 履歴管理
        if not self._is_history_nav:
            if self.hist_idx < len(self.history) - 1:
                self.history = self.history[: self.hist_idx + 1]
            self.history.append(key)
            self.hist_idx = len(self.history) - 1

        # 画面切り替え
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

    # レイアウト
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    shell = AppShell(master=root, cfg=cfg)
    shell.grid(row=0, column=0, sticky="nsew")

    def _maximize_window():
        if os.name == "nt":
            root.state("zoomed")  # Windowsなら最大化
        else:
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry(f"{sw}x{sh}+0+0")  # 他OSは画面サイズに合わせる

    root.after(100, _maximize_window)


    # 履歴ナビ用ショートカット
    root.bind("<Control-Left>", lambda e: shell._hist(-1))
    root.bind("<Control-Right>", lambda e: shell._hist(+1))

    root.mainloop()
