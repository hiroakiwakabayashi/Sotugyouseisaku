import customtkinter as ctk

#　全体を白で統一する
ctk.set_appearance_mode("Light")

class HomeScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        title = ctk.CTkLabel(self, text="Kao-Kintai 起動テスト", font=("Meiryo UI", 24, "bold"))
        subtitle = ctk.CTkLabel(self, text="ここから画面を増やしていきます。", font=("Meiryo UI", 14))
        title.pack(pady=(40,10))
        subtitle.pack()
