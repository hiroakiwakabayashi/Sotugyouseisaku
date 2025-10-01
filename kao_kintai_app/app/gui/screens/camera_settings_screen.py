import customtkinter as ctk

class CameraSettingsScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="🎥 カメラ・顔認証設定（MVP骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここに：カメラ選択・解像度・照合しきい値・バックエンド切替").pack()
