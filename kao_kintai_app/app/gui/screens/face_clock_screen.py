import customtkinter as ctk

class FaceClockScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="📷 顔認証 打刻（骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここにカメラ表示やボタンを後で実装します。").pack()
