import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import customtkinter as ctk
from gui.screens.face_clock_screen import FaceClockScreen

if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("出席管理 - 顔認証画面")
    app.geometry("1280x720")

    screen = FaceClockScreen(app)
    screen.pack(fill="both", expand=True)

    app.mainloop()
