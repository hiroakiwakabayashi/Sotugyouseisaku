import customtkinter as ctk

class EmployeeRegisterScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text="👥 従業員登録 / 編集（MVP骨組み）", font=("Meiryo UI", 22, "bold")).pack(pady=24)
        ctk.CTkLabel(self, text="ここに：追加・編集・退職フラグ・社員コード自動採番・CSVインポート等").pack()
