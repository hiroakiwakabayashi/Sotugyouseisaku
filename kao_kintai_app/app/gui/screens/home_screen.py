import customtkinter as ctk

class HomeScreen(ctk.CTkFrame):
    """
    右側をタイル状の遷移ボタンで埋めるホーム。
    - 顔認証打刻
    - 勤怠一覧
    - マイ勤怠
    - 管理者メニュー
    """
    def __init__(self, master, show_callback=None):
        super().__init__(master)
        self.show_callback = show_callback or (lambda key: None)

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        for i in range(3):
            self.grid_columnconfigure(i, weight=1)

        # 見出し
        title = ctk.CTkLabel(self, text="Kao-Kintai 起動テスト", font=("Meiryo UI", 24, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(24,8))

        subtitle = ctk.CTkLabel(self, text="よく使う機能へすぐ移動できます。", font=("Meiryo UI", 13))
        subtitle.grid(row=0, column=0, columnspan=3, pady=(0,18), sticky="n")

        # タイルコンテナ
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=24, pady=12)
        for i in range(2):
            wrap.grid_rowconfigure(i, weight=1)
        for j in range(2):
            wrap.grid_columnconfigure(j, weight=1)

        def tile(text, sub, emoji, key):
            card = ctk.CTkFrame(wrap, corner_radius=16)
            card._set_dimensions(width=280, height=160)  # 目安サイズ
            card.grid_propagate(False)

            ctk.CTkLabel(card, text=f"{emoji}  {text}", font=("Meiryo UI", 18, "bold")).pack(anchor="w", padx=16, pady=(14,2))
            ctk.CTkLabel(card, text=sub, font=("Meiryo UI", 12), justify="left", wraplength=240).pack(anchor="w", padx=16, pady=(0,12))
            ctk.CTkButton(card, text="開く", command=lambda: self.show_callback(key)).pack(padx=16, pady=(0,14), fill="x")
            return card

        # 2x2 タイル
        tile("顔認証打刻", "カメラで本人確認して出勤／休憩／退勤を記録します。", "📷", "clock").grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        tile("勤怠一覧",   "期間や従業員で検索・CSV出力できます。",         "📑", "list").grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        tile("マイ勤怠",   "自分の打刻履歴を素早く確認。",                   "👤", "my").grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        tile("管理者メニュー", "従業員管理・顔データ・設定へ。",               "🛠", "admin").grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
