import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.storage.face_store import FaceStore
from app.services.config_service import ConfigService


class FaceDataScreen(ctk.CTkFrame):

    PADX = 16
    PADY = 8
    TITLE_FONT = ("Meiryo UI", 22, "bold")

    def __init__(self, master):
        super().__init__(master)
                # ------------------ フォント定義 ------------------
        self.UI_FONT_15 = ctk.CTkFont(size=15)


        # ------------------ 依存 ------------------
        self.repo = EmployeeRepo()
        self.store = FaceStore()

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )

        # ------------------ しきい値 ------------------
        cfg = ConfigService().get_vision()
        self.MIN_AREA_RATIO = float(cfg["min_area_ratio"])
        self.MIN_BLUR_VAR   = float(cfg["min_blur_var"])
        self.BRIGHT_MIN     = int(cfg["bright_min"])
        self.BRIGHT_MAX     = int(cfg["bright_max"])

        self.REQUIRED_OK_FRAMES = 1
        self.ok_streak = 0

        self.target_count = 5
        self.captured_count = 0

        # ------------------ 表示用変数 ------------------
        self.selected_code = tk.StringVar()
        self.message_var = tk.StringVar(value="カメラに顔を向けてください。")
        self.q_face_var = tk.StringVar(value="-")
        self.q_size_var = tk.StringVar(value="-")
        self.q_blur_var = tk.StringVar(value="-")
        self.q_light_var = tk.StringVar(value="-")
        self.q_eyes_var = tk.StringVar(value="-")

        # ------------------ レイアウト ------------------
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=0)

        self.RIGHT_W = 420
        self.LABEL_W = 140
        self.VALUE_W = 80
        self.MSG_H = 68

        # ==================================================
        # 左：タイトル＋カメラ
        # ==================================================
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_columnconfigure(0, weight=1)

        camera_wrap = ctk.CTkFrame(left, fg_color="transparent")
        camera_wrap.grid(row=0, column=0, sticky="n")

        ctk.CTkLabel(
            camera_wrap,
            text="📸 顔データ登録",
            font=self.TITLE_FONT,
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        self.preview = ctk.CTkLabel(camera_wrap, text="")
        self.preview.pack()

        # ==================================================
        # 右：操作パネル
        # ==================================================
        right = ctk.CTkFrame(self, width=self.RIGHT_W)
        right.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        right.grid_propagate(False)

        # 従業員選択
        emp_row = ctk.CTkFrame(right)
        emp_row.pack(fill="x", padx=12, pady=(6, 6))

        ctk.CTkLabel(
            emp_row,
            text="従業員",
            width=self.LABEL_W,
            anchor="w",
            font=self.UI_FONT_15
        ).pack(side="left", padx=(0, 8))

        opts = self._employee_options()
        self.emp_menu = ctk.CTkOptionMenu(
            emp_row,
            values=opts if opts else ["従業員が未登録です"],
            command=self._on_emp_change,
            width=self.RIGHT_W - self.LABEL_W - 40,
        )
        self.emp_menu.pack(side="left", fill="x", expand=True)

        if opts:
            self.emp_menu.set(opts[0])
            self.selected_code.set(opts[0].split(" ")[0])
        else:
            self.emp_menu.set("従業員が未登録です")
            self.selected_code.set("")

        # 品質インジケータ
        ind = ctk.CTkFrame(right)
        ind.pack(fill="x", padx=12, pady=(6, 6))

        SETTING_FONT = ctk.CTkFont(size=15)

        def make_row(label, var):
            row = ctk.CTkFrame(ind)
            row.pack(fill="x", pady=4)  # ← 余白は維持

            ctk.CTkLabel(
                row,
                text=label,
                width=self.LABEL_W,
                anchor="w",
                font=SETTING_FONT,
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                textvariable=var,
                width=self.VALUE_W,
                anchor="w",
                font=SETTING_FONT,
            ).pack(side="left")

        make_row("顔検出", self.q_face_var)
        make_row("サイズ", self.q_size_var)
        make_row("ブレ/ピント", self.q_blur_var)
        make_row("明るさ", self.q_light_var)
        make_row("目の検出", self.q_eyes_var)

        # メッセージ（カメラ状態）
        msg_wrap = ctk.CTkFrame(right, height=self.MSG_H)
        msg_wrap.pack(fill="x", padx=12, pady=(6, 6))
        msg_wrap.pack_propagate(False)

        # 項目名：カメラ状態
        ctk.CTkLabel(
            msg_wrap,
            text="カメラ状態",
            font=("Meiryo UI", 15, "bold"),
            anchor="w",
        ).pack(fill="x", padx=4, pady=(2, 0))

        # メッセージ本文
        ctk.CTkLabel(
            msg_wrap,
            textvariable=self.message_var,
            font=("Meiryo UI", 15),
            wraplength=self.RIGHT_W - 24,
            justify="left",
            anchor="w",
        ).pack(fill="both", expand=True, padx=4, pady=(0, 2))


        # カウント・ボタン
        ctr = ctk.CTkFrame(right)
        ctr.pack(fill="x", padx=12, pady=(10, 6))

        self.count_label = ctk.CTkLabel(
            ctr,
            text=f"保存: {self.captured_count} / {self.target_count}",
            font=self.UI_FONT_15
        )
        self.count_label.pack(side="left")

        BTN_FONT = ("Meiryo UI", 15, "bold")
        self.UI_FONT_15 = ctk.CTkFont(size=15)


        self.btn_capture = ctk.CTkButton(
            right,
            text="撮影して保存",
            command=self._capture,
            state="disabled",
            font=BTN_FONT,
        )
        self.btn_capture.pack(fill="x", padx=12, pady=(6, 6))

        self.btn_reset = ctk.CTkButton(
            right,
            text="カウントをリセット",
            command=self._reset_count,
            font=BTN_FONT,
        )
        self.btn_reset.pack(fill="x", padx=12, pady=(0, 0))

        # ------------------ カメラ ------------------
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._after_id = None
        self._loop()

    # ================== ループ ==================
    def _loop(self):
        ok, frame = self.cap.read()
        if ok:
            annotated, quality_ok = self._evaluate_and_draw(frame)

            self.ok_streak = self.ok_streak + 1 if quality_ok else 0
            self.btn_capture.configure(
                state="normal" if self.ok_streak >= self.REQUIRED_OK_FRAMES else "disabled"
            )

            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.preview.configure(image=imgtk)
            self.preview.image = imgtk

        self._after_id = self.after(30, self._loop)

    # ================== 品質評価 ==================
    def _evaluate_and_draw(self, frame):
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(120, 120))
        if len(faces) == 0:
            self._set_quality(False, None, None, None, None)
            self.message_var.set("顔を映してください。")
            return frame, False

        x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
        roi_gray = gray[y:y+fh, x:x+fw]

        area_ratio = (fw * fh) / (w * h)
        blur = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        bright = np.mean(roi_gray)

        eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 8)

        ok_size = area_ratio >= self.MIN_AREA_RATIO
        ok_blur = blur >= self.MIN_BLUR_VAR
        ok_light = self.BRIGHT_MIN <= bright <= self.BRIGHT_MAX
        ok_eyes = len(eyes) >= 1

        all_ok = ok_size and ok_blur and ok_light and ok_eyes
        self._set_quality(True, ok_size, ok_blur, ok_light, ok_eyes)
        self.message_var.set("品質OK：撮影可能です。" if all_ok else "調整中…")

        color = (0, 200, 0) if all_ok else (0, 165, 255)
        cv2.rectangle(frame, (x, y), (x + fw, y + fh), color, 2)

        return frame, all_ok

    def _set_quality(self, face, size, blur, bright, eyes):
        def t(v):
            return "-" if v is None else "OK" if v else "NG"

        self.q_face_var.set(t(face))
        self.q_size_var.set(t(size))
        self.q_blur_var.set(t(blur))
        self.q_light_var.set(t(bright))
        self.q_eyes_var.set(t(eyes))

    # ================== 撮影 ==================
    def _capture(self):
        ok, frame = self.cap.read()
        if not ok:
            messagebox.showerror("エラー", "撮影に失敗しました")
            return

        self.store.save_image(self.selected_code.get(), frame)
        self.captured_count += 1
        self.count_label.configure(text=f"保存: {self.captured_count} / {self.target_count}")

    def _reset_count(self):
        self.captured_count = 0
        self.count_label.configure(text=f"保存: 0 / {self.target_count}")

    # ================== 従業員 ==================
    def _employee_options(self):
        rows = self.repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows] if rows else []

    def _on_emp_change(self, display):
        self.selected_code.set(display.split(" ")[0])

    # ================== 終了 ==================
    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        super().destroy()
