import customtkinter as ctk

class AdminAccountScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="🔐 管理者アカウント（MVP骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここに：管理者ID/パス変更、権限ロール設定").pack()
