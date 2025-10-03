# app/gui/screens/face_clock_screen.py
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import os, glob
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageTk

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo


class FaceClockScreen(ctk.CTkFrame):
    """
    MVP版の顔認証打刻画面
    - 左：カメラプレビュー（顔枠・簡易品質チェック・認識候補の描画）
    - 右：認識結果・品質インジケータ・打刻ボタン・データ再読込
    - 簡易認識：ORB特徴 + BFMatcher（OpenCVのみで完結）
      -> data/faces/<社員コード>/*.jpg を学習として読み込み、最もマッチ数が多いコードを候補に
    """
    def __init__(self, master):
        super().__init__(master)

        # ---------------- 依存 ----------------
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()

        # Haarカスケード（顔検出）
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        # ORB + BFMatcher（簡易特徴マッチ）
        self.orb = cv2.ORB_create(nfeatures=700)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # ---------------- パラメータ ----------------
        # 品質（撮影条件の可否）
        self.MIN_AREA_RATIO = 0.10   # 顔の面積/フレーム
        self.MIN_BLUR_VAR   = 100.0  # ぼけ(Laplacian var)
        self.BRIGHT_MIN     = 60
        self.BRIGHT_MAX     = 190

        # 認識（マッチ閾値）
        self.MATCH_THRESHOLD = 24    # 「よいマッチ」の最低数（経験則）
        self.TOP_K_IMAGES    = 5     # 各従業員につき最新N枚を学習に使用
        self.RECOG_INTERVAL  = 3     # Nフレームに1回認識（軽量化）

        self.frame_count = 0
        self.last_best = ("", 0)     # (code, matches)

        # 右パネル固定サイズ（チラつき防止）
        self.RIGHT_W = 420
        self.LABEL_W = 140
        self.VALUE_W = 100
        self.MSG_H   = 68

        # 表示用変数
        self.message_var  = tk.StringVar(value="カメラに顔を向けてください。")
        self.q_face_var   = tk.StringVar(value="-")
        self.q_size_var   = tk.StringVar(value="-")
        self.q_blur_var   = tk.StringVar(value="-")
        self.q_light_var  = tk.StringVar(value="-")
        self.rec_code_var = tk.StringVar(value="--")
        self.rec_name_var = tk.StringVar(value="--")
        self.rec_score_var= tk.StringVar(value="-")

        # ---------------- レイアウト ----------------
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=0)

        # 左：プレビュー
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12,6), pady=12)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self.preview = ctk.CTkLabel(left, text="")
        self.preview.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # 右：情報＆操作（固定幅）
        right = ctk.CTkFrame(self, width=self.RIGHT_W)
        right.grid(row=0, column=1, sticky="ns", padx=(6,12), pady=12)
        right.grid_propagate(False)

        ctk.CTkLabel(right, text="📷 顔認証 打刻", font=("Meiryo UI", 20, "bold")).pack(anchor="w", padx=12, pady=(12,6))

        # 認識結果表示
        res = ctk.CTkFrame(right); res.pack(fill="x", padx=12, pady=(4,6))
        self._kv(res, "推定コード", self.rec_code_var)
        self._kv(res, "推定氏名",   self.rec_name_var)
        self._kv(res, "マッチ数",    self.rec_score_var)

        # 品質インジケータ
        ind = ctk.CTkFrame(right); ind.pack(fill="x", padx=12, pady=(6,6))
        self._kv(ind, "顔検出", self.q_face_var)
        self._kv(ind, "サイズ", self.q_size_var)
        self._kv(ind, "ブレ/ピント", self.q_blur_var)
        self._kv(ind, "明るさ", self.q_light_var)

        # メッセージ（固定高さ）
        msg_wrap = ctk.CTkFrame(right, height=self.MSG_H)
        msg_wrap.pack(fill="x", padx=12, pady=(6,6))
        msg_wrap.pack_propagate(False)
        ctk.CTkLabel(msg_wrap, textvariable=self.message_var, wraplength=self.RIGHT_W-24, justify="left").pack(fill="both", expand=True, padx=2, pady=2)

        # 打刻ボタン
        btns = ctk.CTkFrame(right); btns.pack(fill="x", padx=12, pady=(6,6))
        for i in range(4): btns.grid_columnconfigure(i, weight=1)
        self.btn_in    = ctk.CTkButton(btns, text="出勤",     command=lambda: self._punch("CLOCK_IN"),    state="disabled")
        self.btn_break = ctk.CTkButton(btns, text="休憩開始", command=lambda: self._punch("BREAK_START"), state="disabled")
        self.btn_back  = ctk.CTkButton(btns, text="休憩終了", command=lambda: self._punch("BREAK_END"),   state="disabled")
        self.btn_out   = ctk.CTkButton(btns, text="退勤",     command=lambda: self._punch("CLOCK_OUT"),   state="disabled")
        self.btn_in.grid(   row=0, column=0, padx=4, pady=4, sticky="ew")
        self.btn_break.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.btn_back.grid( row=0, column=2, padx=4, pady=4, sticky="ew")
        self.btn_out.grid(  row=0, column=3, padx=4, pady=4, sticky="ew")

        # データ再読込
        ctk.CTkButton(right, text="顔データを再読み込み", command=self._reload_dataset).pack(fill="x", padx=12, pady=(6,6))

        # ---------------- データセット読込 ----------------
        self.name_map = {}       # code -> name
        self.des_map  = {}       # code -> list[np.ndarray] (ORB descriptors)
        self._reload_dataset(initial=True)

        # ---------------- カメラ ----------------
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._after_id = None
        self._loop()

    # ====== UIユーティリティ ======
    def _kv(self, parent, label, var):
        row = ctk.CTkFrame(parent); row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=self.LABEL_W, anchor="w").pack(side="left")
        ctk.CTkLabel(row, textvariable=var, width=self.VALUE_W, anchor="w", font=("Consolas", 14)).pack(side="left")

    def _reset_recognition_ui(self, reason: str | None = None):
        """顔未検出時などに推定結果とボタンをリセット"""
        self.last_best = ("", 0)
        self.rec_code_var.set("--")
        self.rec_name_var.set("--")
        self.rec_score_var.set("-")
        if reason:
            self.message_var.set(reason)
        self._update_buttons(False)

    # ====== ループ ======
    def _loop(self):
        ok, frame = self.cap.read()
        if ok:
            annotated, quality_ok, face_roi = self._evaluate_and_draw(frame)
            self._update_buttons(enabled=quality_ok and self.last_best[0] != "")

            # 認識（数フレームに1回）
            if quality_ok and face_roi is not None:
                if self.frame_count % self.RECOG_INTERVAL == 0:
                    code, matches = self._recognize(face_roi)
                    self.last_best = (code, matches) if code else ("", 0)
                    if code:
                        name = self.name_map.get(code, "--")
                        self.rec_code_var.set(code)
                        self.rec_name_var.set(name)
                        self.rec_score_var.set(str(matches))
                        self.message_var.set("顔を認識しました。ボタンで打刻できます。")
                    else:
                        self.rec_code_var.set("--")
                        self.rec_name_var.set("--")
                        self.rec_score_var.set("-")
                        self.message_var.set("未登録の顔です。明るさ/距離/角度を調整するか、顔データを登録してください。")

            # 表示
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.preview.configure(image=imgtk)
            self.preview.image = imgtk

            self.frame_count += 1

        self._after_id = self.after(30, self._loop)

    # ====== 品質評価（顔検出＋サイズ/ブレ/明るさ） ======
    def _evaluate_and_draw(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(120,120))

        if len(faces) == 0:
            self._set_quality(face=False, size=None, blur=None, bright=None)
            # ★ここで推定結果をリセット
            self._reset_recognition_ui("顔を映してください。（カメラの前で正面を向いてください）")
            return frame_bgr, False, None

        # 最大の顔
        x, y, fw, fh = max(faces, key=lambda r: r[2]*r[3])
        cv2.rectangle(frame_bgr, (x,y), (x+fw,y+fh), (0,200,255), 2)

        roi_gray = gray[y:y+fh, x:x+fw]
        area_ratio = (fw*fh) / (w*h)
        blur = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        bright = float(np.mean(roi_gray))

        ok_size = area_ratio >= self.MIN_AREA_RATIO
        ok_blur = blur >= self.MIN_BLUR_VAR
        ok_light = (self.BRIGHT_MIN <= bright <= self.BRIGHT_MAX)

        msgs = []
        if not ok_size:  msgs.append("顔をもう少し近づけてください。")
        if not ok_blur:  msgs.append("ピントが合っていません（ぶれ/ぼけ）。")
        if not ok_light:
            msgs.append("暗すぎ/明るすぎです。照明や露出を調整してください。")

        all_ok = ok_size and ok_blur and ok_light
        self._set_quality(face=True, size=ok_size, blur=ok_blur, bright=ok_light)
        if not all_ok:
            self.message_var.set(" / ".join(msgs) or "調整中…")

        color = (0,200,0) if all_ok else (0,165,255) if msgs else (0,200,255)
        cv2.rectangle(frame_bgr, (x,y), (x+fw,y+fh), color, 2)

        return frame_bgr, all_ok, roi_gray if all_ok else None

    def _set_quality(self, face, size, blur, bright):
        def t(v, seen=False):
            if v is None and not seen:
                return "-"
            return "OK" if v else "NG"
        self.q_face_var.set(t(face, seen=True))
        self.q_size_var.set(t(size))
        self.q_blur_var.set(t(blur))
        self.q_light_var.set(t(bright))

    # ====== 簡易認識（ORB + BFMatcher） ======
    def _recognize(self, roi_gray):
        # live descriptors
        kpl, desl = self.orb.detectAndCompute(roi_gray, None)
        if desl is None or len(desl) == 0:
            return None, 0

        best_code, best_matches = None, 0
        for code, desc_list in self.des_map.items():
            total_good = 0
            for des_ref in desc_list:
                try:
                    matches = self.bf.match(desl, des_ref)
                except cv2.error:
                    continue
                matches = sorted(matches, key=lambda m: m.distance)
                good = [m for m in matches if m.distance <= 60]  # 経験則
                total_good = max(total_good, len(good))
            if total_good > best_matches:
                best_matches = total_good
                best_code = code

        if best_code and best_matches >= self.MATCH_THRESHOLD:
            return best_code, best_matches
        return None, 0

    # ====== データセット再読込 ======
    def _reload_dataset(self, initial=False):
        self.name_map.clear()
        self.des_map.clear()

        # 従業員一覧
        employees = self.emp_repo.list_all()
        for r in employees:
            code, name = r["code"], r["name"]
            self.name_map[code] = name

        # data/faces/<code>/*.jpg を各人TOP_K_IMAGESだけ使用
        root = Path(__file__).resolve().parents[3] / "data" / "faces"
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)

        for code in self.name_map.keys():
            imgs = sorted(glob.glob(str(root / code / "*.jpg")))
            if not imgs:
                continue
            imgs = imgs[-self.TOP_K_IMAGES:]  # 新しい順に最大N枚

            desc_list = []
            for p in imgs:
                img = cv2.imread(p)
                if img is None:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100,100))
                if len(faces) > 0:
                    x,y,w,h = max(faces, key=lambda r: r[2]*r[3])
                    gray_roi = gray[y:y+h, x:x+w]
                else:
                    gray_roi = gray

                kp, des = self.orb.detectAndCompute(gray_roi, None)
                if des is not None and len(des) > 0:
                    desc_list.append(des)

            if desc_list:
                self.des_map[code] = desc_list

        if not initial:
            messagebox.showinfo("再読込", "顔データを再読み込みしました。")

    # ====== 打刻 ======
    def _punch(self, kind: str):
        code = self.last_best[0]
        if not code:
            messagebox.showwarning("未認識", "顔が認識されていません。")
            return
        self.att_repo.add(employee_code=code, punch_type=kind)
        label = {
            "CLOCK_IN": "出勤",
            "BREAK_START": "休憩開始",
            "BREAK_END": "休憩終了",
            "CLOCK_OUT": "退勤"
        }.get(kind, kind)
        messagebox.showinfo("打刻", f"{label} を記録しました（{code} / {self.name_map.get(code,'')}）。")

    def _update_buttons(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_in.configure(state=state)
        self.btn_break.configure(state=state)
        self.btn_back.configure(state=state)
        self.btn_out.configure(state=state)

    # ====== 終了処理 ======
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
