import customtkinter as ctk

class MyAttendanceScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="👤 マイ勤怠（骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここに自分の勤怠一覧や月集計を実装します。").pack()
