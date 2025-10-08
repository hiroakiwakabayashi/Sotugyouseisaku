# app/gui/screens/face_data_screen.py
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
    def __init__(self, master):
        super().__init__(master)

        # ------------------ 依存 ------------------
        self.repo = EmployeeRepo()
        self.store = FaceStore()

        # Haarカスケード（OpenCV同梱）
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.eye_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )

        # ------------------ しきい値 ------------------
        # __init__ のしきい値初期化を置き換え
        cfg = ConfigService().get_vision()
        self.MIN_AREA_RATIO = float(cfg["min_area_ratio"])
        self.MIN_BLUR_VAR   = float(cfg["min_blur_var"])
        self.BRIGHT_MIN     = int(cfg["bright_min"])
        self.BRIGHT_MAX     = int(cfg["bright_max"])
        # REQUIRED_OK_FRAMES などはそのままでもOK（必要なら設定化可）

        self.REQUIRED_OK_FRAMES = 1    # 連続OKフレーム数
        self.ok_streak = 0

        self.target_count = 5          # 保存目標
        self.captured_count = 0

        # ------------------ 表示用変数 ------------------
        self.selected_code = tk.StringVar()
        self.message_var = tk.StringVar(value="カメラに顔を向けてください。")
        self.q_face_var = tk.StringVar(value="-")
        self.q_size_var = tk.StringVar(value="-")
        self.q_blur_var = tk.StringVar(value="-")
        self.q_light_var = tk.StringVar(value="-")
        self.q_eyes_var = tk.StringVar(value="-")

        # ------------------ レイアウト構成 ------------------
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)  # 左プレビュー広め
        self.grid_columnconfigure(1, weight=0)

        # 右パネル固定サイズ用の定数
        self.RIGHT_W = 420
        self.LABEL_W = 140
        self.VALUE_W = 80
        self.MSG_H = 68

        # --- 左：プレビュー ---
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.preview = ctk.CTkLabel(left, text="")
        self.preview.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # --- 右：操作パネル（固定幅/高さでチラつき防止） ---
        right = ctk.CTkFrame(self, width=self.RIGHT_W)
        right.grid(row=0, column=1, sticky="ns", padx=(6, 12), pady=12)
        right.grid_propagate(False)  # 子に引っ張られない

        ctk.CTkLabel(
            right, text="🖼 顔データ登録", font=("Meiryo UI", 20, "bold")
        ).pack(anchor="w", padx=12, pady=(12, 6))

        # 従業員選択
        emp_row = ctk.CTkFrame(right)
        emp_row.pack(fill="x", padx=12, pady=(6, 6))
        ctk.CTkLabel(emp_row, text="従業員", width=self.LABEL_W, anchor="w").pack(
            side="left", padx=(0, 8)
        )
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

        # 品質インジケータ（各行固定幅）
        ind = ctk.CTkFrame(right)
        ind.pack(fill="x", padx=12, pady=(6, 6))

        def make_row(label, var):
            row = ctk.CTkFrame(ind)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=self.LABEL_W, anchor="w").pack(
                side="left"
            )
            ctk.CTkLabel(
                row,
                textvariable=var,
                width=self.VALUE_W,
                anchor="w",
                font=("Consolas", 14),  # 等幅フォントで幅ブレ防止
            ).pack(side="left")

        make_row("顔検出", self.q_face_var)
        make_row("サイズ", self.q_size_var)
        make_row("ブレ/ピント", self.q_blur_var)
        make_row("明るさ", self.q_light_var)
        make_row("目の検出", self.q_eyes_var)

        # ステータスメッセージ（固定高さ）
        msg_wrap = ctk.CTkFrame(right, height=self.MSG_H)
        msg_wrap.pack(fill="x", padx=12, pady=(6, 6))
        msg_wrap.pack_propagate(False)
        ctk.CTkLabel(
            msg_wrap,
            textvariable=self.message_var,
            wraplength=self.RIGHT_W - 24,
            justify="left",
        ).pack(fill="both", expand=True, padx=2, pady=2)

        # カウント＆操作ボタン
        ctr = ctk.CTkFrame(right)
        ctr.pack(fill="x", padx=12, pady=(10, 6))
        self.count_label = ctk.CTkLabel(
            ctr, text=f"保存: {self.captured_count} / {self.target_count}"
        )
        self.count_label.pack(side="left")

        self.btn_capture = ctk.CTkButton(
            right, text="撮影して保存", command=self._capture, state="disabled"
        )
        self.btn_capture.pack(fill="x", padx=12, pady=(6, 6))

        self.btn_reset = ctk.CTkButton(
            right, text="カウントをリセット", command=self._reset_count
        )
        self.btn_reset.pack(fill="x", padx=12, pady=(0, 6))

        # ------------------ カメラ ------------------
        self.cap = cv2.VideoCapture(0)  # 必要ならカメラID変更
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._after_id = None
        self._loop()

    # ================== ループ ==================
    def _loop(self):
        ok, frame = self.cap.read()
        if ok:
            annotated, quality_ok = self._evaluate_and_draw(frame)

            # 撮影可否（連続OKでボタンON）
            if quality_ok and self.selected_code.get():
                self.ok_streak += 1
            else:
                self.ok_streak = 0
            self.btn_capture.configure(
                state=("normal" if self.ok_streak >= self.REQUIRED_OK_FRAMES else "disabled")
            )

            # Tk表示
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.preview.configure(image=imgtk)
            self.preview.image = imgtk

        self._after_id = self.after(30, self._loop)  # ~33fps

    # ================== 品質評価 ==================
    def _evaluate_and_draw(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(120, 120)
        )
        if len(faces) == 0:
            self._set_quality(face=False, size=None, blur=None, bright=None, eyes=None)
            self.message_var.set("顔を映してください。（カメラの前で正面を向いてください）")
            return frame_bgr, False

        # 最大の顔を採用
        x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
        cv2.rectangle(frame_bgr, (x, y), (x + fw, y + fh), (0, 200, 255), 2)

        # 顔ROI
        roi_gray = gray[y : y + fh, x : x + fw]
        roi_bgr = frame_bgr[y : y + fh, x : x + fw]

        area_ratio = (fw * fh) / (w * h)
        blur = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        bright = float(np.mean(roi_gray))

        # 目検出（簡易）
        eyes = self.eye_cascade.detectMultiScale(
            roi_gray, scaleFactor=1.1, minNeighbors=8, minSize=(30, 30)
        )
        for (ex, ey, ew, eh) in eyes[:2]:
            cv2.rectangle(roi_bgr, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 1)

        # 判定
        msgs = []
        ok_face = True
        ok_size = area_ratio >= self.MIN_AREA_RATIO
        if not ok_size:
            msgs.append("顔をもう少し近づけてください。")

        ok_blur = blur >= self.MIN_BLUR_VAR
        if not ok_blur:
            msgs.append("ピントが合っていません（ぶれ/ぼけ）。")

        ok_light = self.BRIGHT_MIN <= bright <= self.BRIGHT_MAX
        if not ok_light:
            if bright < self.BRIGHT_MIN:
                msgs.append("暗すぎます。照明を明るくしてください。")
            else:
                msgs.append("明るすぎます。逆光/露出に注意してください。")

        ok_eyes = len(eyes) >= 1
        if not ok_eyes:
            msgs.append("目が検出できません。サングラス/前髪/角度を調整。")

        all_ok = ok_face and ok_size and ok_blur and ok_light and ok_eyes
        self._set_quality(face=True, size=ok_size, blur=ok_blur, bright=ok_light, eyes=ok_eyes)
        self.message_var.set("品質OK：撮影可能です。" if all_ok else " / ".join(msgs) or "調整中…")

        # 色分け
        color = (0, 200, 0) if all_ok else (0, 165, 255) if msgs else (0, 200, 255)
        cv2.rectangle(frame_bgr, (x, y), (x + fw, y + fh), color, 2)

        return frame_bgr, all_ok

    def _set_quality(self, face, size, blur, bright, eyes):
        # OK/NG/- に固定（等幅フォント + 固定幅Labelでチラつき防止）
        def t(v, seen=False):
            if v is None and not seen:
                return "-"
            return "OK" if v else "NG"

        self.q_face_var.set(t(face, seen=True))  # faceはNoneにしない運用
        self.q_size_var.set(t(size))
        self.q_blur_var.set(t(blur))
        self.q_light_var.set(t(bright))
        self.q_eyes_var.set(t(eyes))

    # ================== 撮影保存 ==================
    def _capture(self):
        if not self.selected_code.get():
            messagebox.showwarning("従業員未選択", "先に従業員を選択してください。")
            return
        ok, frame = self.cap.read()
        if not ok:
            messagebox.showerror("カメラ", "フレームの取得に失敗しました。")
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(120, 120))
        if len(faces) == 0:
            messagebox.showwarning("顔なし", "顔が検出できませんでした。")
            return
        x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])

        # 余白付きでクロップ
        H, W = frame.shape[:2]
        margin = 0.25
        cx1 = max(0, int(x - fw * margin))
        cy1 = max(0, int(y - fh * margin))
        cx2 = min(W, int(x + fw * (1 + margin)))
        cy2 = min(H, int(y + fh * (1 + margin)))
        face_img = frame[cy1:cy2, cx1:cx2]

        p = self.store.save_image(self.selected_code.get(), face_img)
        self.captured_count += 1
        self.count_label.configure(text=f"保存: {self.captured_count} / {self.target_count}")
        self.message_var.set(f"保存しました: {p.name}")

    def _reset_count(self):
        self.captured_count = 0
        self.count_label.configure(text=f"保存: {self.captured_count} / {self.target_count}")

    # ================== 従業員関連 ==================
    def _employee_options(self):
        rows = self.repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows] if rows else []

    def _on_emp_change(self, display: str):
        code = display.split(" ")[0] if display and " " in display else ""
        self.selected_code.set(code)

    # ================== 終了処理 ==================
    def destroy(self):
        try:
            if self._after_id:
                self.after_cancel(self._after_id)
        except Exception:
            pass
        try:
            if self.cap and self.cap.isOpened():
                self.cap.release()
        except Exception:
            pass
        super().destroy()
