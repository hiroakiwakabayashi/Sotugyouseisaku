import customtkinter as ctk

class FaceDataScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="🖼 顔データ管理（MVP骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここに：顔画像の登録/再登録、特徴量の再計算、削除").pack()
