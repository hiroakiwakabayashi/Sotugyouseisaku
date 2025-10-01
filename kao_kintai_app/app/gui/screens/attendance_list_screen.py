import customtkinter as ctk

class AttendanceListScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="📑 勤怠一覧（骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここにテーブル表示・検索・エクスポート等を実装します。").pack()
