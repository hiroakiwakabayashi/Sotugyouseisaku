import customtkinter as ctk

class HomeScreen(ctk.CTkFrame):
    def __init__(self, master, show_callback=None):
        super().__init__(master)
        self.show_callback = show_callback or (lambda key: None)

        # ===== レイアウト設定 =====
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        for i in range(3):
            self.grid_columnconfigure(i, weight=1)

        # ===== タイトル =====
        ctk.CTkLabel(
            self,
            text="Kao-Kintai",
            font=("Meiryo UI", 26, "bold"),
        ).grid(row=0, column=0, columnspan=3, pady=(28, 6))

        ctk.CTkLabel(
            self,
            text="よく使う機能へすぐ移動できます",
            font=("Meiryo UI", 13),
            text_color="#6B7280",
        ).grid(row=0, column=0, columnspan=3, pady=(0, 20))

        # ===== タイルコンテナ =====
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=28, pady=12)
        for i in range(2):
            wrap.grid_rowconfigure(i, weight=1)
        for j in range(2):
            wrap.grid_columnconfigure(j, weight=1)

        def tile(text, sub, emoji, key):
            card = ctk.CTkFrame(
                wrap,
                corner_radius=18,
                fg_color="#F9FAFB",
                border_width=1,
                border_color="#E5E7EB",
            )
            card._set_dimensions(width=300, height=175)
            card.grid_propagate(False)

            # ▼ 余白を詰める
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(expand=True, fill="both", padx=10, pady=10)

            # 見出し
            ctk.CTkLabel(
                inner,
                text=f"{emoji}  {text}",
                font=("Meiryo UI", 18, "bold"),
            ).pack(pady=(8, 4))

            # 説明文
            ctk.CTkLabel(
                inner,
                text=sub,
                font=("Meiryo UI", 12),
                text_color="#4B5563",
                justify="center",
                wraplength=240,
            ).pack(pady=(0, 10))

            # ボタン
            ctk.CTkButton(
                inner,
                text="開く",
                height=34,
                command=lambda: self.show_callback(key),
            ).pack(side="bottom", fill="x", padx=6, pady=(6, 0))

            return card

        # ===== タイル配置 =====
        tile(
            "顔認証打刻",
            "カメラで本人確認して\n出勤・休憩・退勤を記録します。",
            "📷",
            "clock",
        ).grid(row=0, column=0, padx=12, pady=12, sticky="nsew")

        tile(
            "勤怠一覧",
            "期間や従業員で検索し\nCSV出力が可能です。",
            "📑",
            "list",
        ).grid(row=0, column=1, padx=12, pady=12, sticky="nsew")

        tile(
            "マイ勤怠",
            "自分の打刻履歴を\n素早く確認できます。",
            "👤",
            "my",
        ).grid(row=1, column=0, padx=12, pady=12, sticky="nsew")

        tile(
            "管理者メニュー",
            "従業員管理・顔データ\n各種設定を行います。",
            "🛠",
            "admin",
        ).grid(row=1, column=1, padx=12, pady=12, sticky="nsew")
