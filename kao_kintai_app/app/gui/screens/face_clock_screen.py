import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import glob
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageTk

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo
from app.services.attendance_service import AttendanceService
from app.services.config_service import ConfigService


class FaceClockScreen(ctk.CTkFrame):
    """顔認証 + 打刻画面（中央カメラ + 2段ボタン構成版）
       ・未知顔(Unknown)判定
       ・品質/IDの安定化（連続フレーム確定）
    """

    def __init__(self, master):
        super().__init__(master)

        # --- 依存関係 ---
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()
        self.att_svc = AttendanceService(self.att_repo)

        # Haar / ORB
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.orb = cv2.ORB_create(nfeatures=700)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # しきい値設定（Config）
        vcfg = ConfigService().get_vision()
        self.MIN_AREA_RATIO = float(vcfg.get("min_area_ratio", 0.10))
        self.MIN_BLUR_VAR   = float(vcfg.get("min_blur_var", 80.0))
        self.BRIGHT_MIN     = int(vcfg.get("bright_min", 50))
        self.BRIGHT_MAX     = int(vcfg.get("bright_max", 210))
        self.MATCH_THRESHOLD      = int(vcfg.get("match_threshold", 22))
        self.TOP_K_IMAGES         = int(vcfg.get("top_k_images", 5))
        self.RECOG_INTERVAL       = int(vcfg.get("recog_interval", 3))
        # Unknown & 安定化
        self.UNKNOWN_MIN_GAP      = int(vcfg.get("unknown_min_gap", 8))       # 1位-2位の絶対差
        self.UNKNOWN_MARGIN_RATIO = float(vcfg.get("unknown_margin_ratio", 0.25))  # 相対差
        self.ID_OK_FRAMES         = int(vcfg.get("id_ok_frames", 2))          # 同一ID 連続Nで確定
        self.QUALITY_OK_FRAMES    = int(vcfg.get("quality_ok_frames", 2))     # 品質OK 連続Nで確定

        # 表示用変数
        self.message_var  = tk.StringVar(value="カメラに顔を向けてください。")
        self.rec_code_var = tk.StringVar(value="--")
        self.rec_name_var = tk.StringVar(value="--")

        # 状態管理
        self.frame_count = 0
        self.last_best   = ("", 0)   # (code, best_matches)
        self.allowed_next_set = set()
        self._current_code_ui = ""

        # 安定化用
        self._quality_ok_streak = 0
        self._id_ok_streak = 0
        self._last_candidate = ""

        # ====== レイアウト全体（中央寄せ） ======
        for r in (0, 2):
            self.grid_rowconfigure(r, weight=1)
        for c in (0, 2):
            self.grid_columnconfigure(c, weight=1)

        card = ctk.CTkFrame(self, corner_radius=14)
        card.grid(row=1, column=1, sticky="n", padx=18, pady=18)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=0)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=0)
        card.grid_rowconfigure(3, weight=0)
        card.grid_rowconfigure(4, weight=0)

        # --- タイトル ---
        ctk.CTkLabel(card, text="📷 顔認証 打刻", font=("Meiryo UI", 20, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        # --- 推定情報（推定コード／氏名）---
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=16, pady=(0, 8))
        self._kv(info, "推定コード", self.rec_code_var)
        self._kv(info, "推定氏名",   self.rec_name_var)

        # ===== カメラ（中央配置） =====
        cam_area = ctk.CTkFrame(card, fg_color="transparent")
        cam_area.grid(row=1, column=0, sticky="nsew", padx=16, pady=(6, 6))
        for r in (0, 2):
            cam_area.grid_rowconfigure(r, weight=1)
        for c in (0, 2):
            cam_area.grid_columnconfigure(c, weight=1)

        self.CAM_W, self.CAM_H = 700, 480
        self.preview = ctk.CTkLabel(cam_area, text="", width=self.CAM_W, height=self.CAM_H, anchor="center")
        self.preview.grid(row=1, column=1, padx=0, pady=0, sticky="")

        # --- メッセージ（品質/Unknownなど） ---
        msg = ctk.CTkLabel(card, textvariable=self.message_var, justify="left", anchor="w", wraplength=680)
        msg.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 6))

        # ===== 2段ボタン構成 =====
        btns = ctk.CTkFrame(card, corner_radius=10)
        btns.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))
        for i in range(2):
            btns.grid_columnconfigure(i, weight=1)
        for j in range(2):
            btns.grid_rowconfigure(j, weight=1)

        # 出勤・退勤・休憩開始・休憩終了ボタン
        self.btn_in = ctk.CTkButton(btns, text="出勤", fg_color="#2ECC71", hover_color="#27AE60",
                                    command=lambda: self._punch("CLOCK_IN"), state="disabled")
        self.btn_out = ctk.CTkButton(btns, text="退勤", fg_color="#E74C3C", hover_color="#C0392B",
                                     command=lambda: self._punch("CLOCK_OUT"), state="disabled")
        self.btn_break = ctk.CTkButton(btns, text="休憩開始", command=lambda: self._punch("BREAK_START"),
                                       state="disabled")
        self.btn_back = ctk.CTkButton(btns, text="休憩終了", command=lambda: self._punch("BREAK_END"),
                                      state="disabled")

        # 配置（2x2グリッド）
        self.btn_in.grid(row=0, column=0, padx=6, pady=4, sticky="ew")
        self.btn_out.grid(row=0, column=1, padx=6, pady=4, sticky="ew")
        self.btn_break.grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        self.btn_back.grid(row=1, column=1, padx=6, pady=4, sticky="ew")

        # 再読み込みボタン
        ctk.CTkButton(card, text="顔データを再読み込み", command=self._reload_dataset)\
            .grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        # ---- 顔データ読み込み ----
        self.name_map = {}
        self.des_map = {}
        self._reload_dataset(initial=True)

        # ---- カメラ起動 ----
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._after_id = None
        self._loop()

    # ---------- キー／値ラベル ----------
    def _kv(self, parent, label, var):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=120, anchor="w").pack(side="left")
        ctk.CTkLabel(row, textvariable=var, anchor="w", font=("Consolas", 14)).pack(side="left")

    # ---------- UIリセット ----------
    def _reset_recognition_ui(self, reason=None):
        self.last_best = ("", 0)
        self._current_code_ui = ""
        self.allowed_next_set = set()
        self.rec_code_var.set("--")
        self.rec_name_var.set("--")
        self._id_ok_streak = 0
        self._last_candidate = ""
        if reason:
            self.message_var.set(reason)
        self._update_buttons(can_enable=False)

    # ---------- カメラループ ----------
    def _loop(self):
        ok, frame = self.cap.read()
        if ok:
            annotated, stable_ok, face_rect, gray = self._evaluate_and_draw(frame)

            # 認識は間引き実行
            if stable_ok and face_rect is not None and (self.frame_count % self.RECOG_INTERVAL == 0):
                x, y, w, h = face_rect
                face_roi = gray[y:y+h, x:x+w]

                # ORBで顔認識（1位と2位のスコアも取得）
                code, best, second = self._recognize(face_roi)
                self.last_best = (code or "", best)

                # --- Unknown 判定 ---
                unknown = False
                if code is None or best < self.MATCH_THRESHOLD:
                    unknown = True
                else:
                    gap = best - second
                    ratio = (best - second) / max(best, 1)
                    if gap < self.UNKNOWN_MIN_GAP and ratio < self.UNKNOWN_MARGIN_RATIO:
                        unknown = True

                if unknown:
                    self._reset_recognition_ui("未登録の顔、または一致度が低いため認証できません。")
                else:
                    # 同一候補の連続フレームで確定（チラつき防止）
                    if code == self._last_candidate:
                        self._id_ok_streak += 1
                    else:
                        self._last_candidate = code
                        self._id_ok_streak = 1

                    # 確定前は確認中メッセージ、確定したら許可集合を更新
                    if self._id_ok_streak < self.ID_OK_FRAMES:
                        self.rec_code_var.set(code)
                        self.rec_name_var.set(self.name_map.get(code, "--"))
                        self.message_var.set("確認中…（ぶれずに少し静止してください）")
                    else:
                        name = self.name_map.get(code, "--")
                        self.rec_code_var.set(code)
                        self.rec_name_var.set(name)
                        if code != self._current_code_ui:
                            self._current_code_ui = code
                            last = self.att_svc.last_state(code)
                            self.allowed_next_set = self.att_svc.allowed_next(last)
                        self.message_var.set("顔を認識しました。打刻が可能です。")

            # ボタン状態（品質OK＆ID確定済みのときのみ有効）
            can_enable = stable_ok and (self._id_ok_streak >= self.ID_OK_FRAMES) and (self.last_best[0] != "")
            self._update_buttons(can_enable=can_enable)

            # カメラ画像を中央枠に出力
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (self.CAM_W, self.CAM_H))
            imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.preview.configure(image=imgtk)
            self.preview.image = imgtk
            self.frame_count += 1

        self._after_id = self.after(30, self._loop)

    # ---------- 顔検出 + 品質評価 + 安定化 ----------
    def _evaluate_and_draw(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(120, 120))

        if len(faces) == 0:
            self._quality_ok_streak = 0
            self.message_var.set("顔を映してください。（正面・適度な距離）")
            return frame_bgr, False, None, gray

        # 最大の顔を採用
        x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
        roi_gray = gray[y:y + fh, x:x + fw]

        # 品質指標
        area_ratio = (fw * fh) / (w * h)
        blur = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        bright = float(np.mean(roi_gray))

        ok_size = area_ratio >= self.MIN_AREA_RATIO
        ok_blur = blur >= self.MIN_BLUR_VAR
        ok_light = (self.BRIGHT_MIN <= bright <= self.BRIGHT_MAX)

        msgs = []
        if not ok_size:  msgs.append("顔をもう少し近づけてください。")
        if not ok_blur:  msgs.append("ピントが合っていません（ぶれ/ぼけ）。")
        if not ok_light: msgs.append("暗すぎ/明るすぎです。照明や露出を調整してください。")

        all_ok = ok_size and ok_blur and ok_light

        # 連続OKフレームで安定化
        if all_ok:
            self._quality_ok_streak += 1
        else:
            self._quality_ok_streak = 0

        stable_ok = (self._quality_ok_streak >= self.QUALITY_OK_FRAMES)
        if not stable_ok:
            self.message_var.set(" / ".join(msgs) or "調整中…")

        # 枠色（OK:緑 / 注意:橙 / 検出:シアン）
        color = (0,200,0) if stable_ok else (0,165,255) if msgs else (0,200,255)
        cv2.rectangle(frame_bgr, (x, y), (x + fw, y + fh), color, 2)

        return frame_bgr, stable_ok, (x, y, fw, fh), gray

    # ---------- 顔特徴量マッチング（Top1/Top2スコア） ----------
    def _recognize(self, roi_gray):
        kp, des_l = self.orb.detectAndCompute(roi_gray, None)
        if des_l is None or len(des_l) == 0:
            return None, 0, 0

        scores = []  # [(code, score)]
        for code, desc_list in self.des_map.items():
            best_for_code = 0
            for des_ref in desc_list:
                try:
                    matches = self.bf.match(des_l, des_ref)
                except cv2.error:
                    continue
                matches = sorted(matches, key=lambda m: m.distance)
                good = [m for m in matches if m.distance <= 60]
                best_for_code = max(best_for_code, len(good))
            scores.append((code, best_for_code))

        if not scores:
            return None, 0, 0

        scores.sort(key=lambda x: x[1], reverse=True)
        best_code, best = scores[0]
        second = scores[1][1] if len(scores) >= 2 else 0
        if best <= 0:
            return None, 0, 0
        return best_code, best, second

    # ---------- データ再読込 ----------
    def _reload_dataset(self, initial=False):
        self.name_map.clear()
        self.des_map.clear()

        for r in self.emp_repo.list_all():
            self.name_map[r["code"]] = r["name"]

        root = Path(__file__).resolve().parents[3] / "data" / "faces"
        root.mkdir(parents=True, exist_ok=True)

        for code in self.name_map.keys():
            imgs = sorted(glob.glob(str(root / code / "*.jpg")))
            if not imgs:
                continue
            imgs = imgs[-self.TOP_K_IMAGES:]

            desc_list = []
            for p in imgs:
                img = cv2.imread(p)
                if img is None:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100, 100))
                roi = gray
                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                    roi = gray[y:y + h, x:x + w]
                kp, des = self.orb.detectAndCompute(roi, None)
                if des is not None and len(des) > 0:
                    desc_list.append(des)
            if desc_list:
                self.des_map[code] = desc_list

        if not initial:
            messagebox.showinfo("再読込", "顔データを再読み込みしました。")

    # ---------- 打刻 ----------
    def _punch(self, kind: str):
        code = self.last_best[0]
        if not code or self._id_ok_streak < self.ID_OK_FRAMES:
            messagebox.showwarning("未認識", "顔が確定していません。")
            return

        ok, msg, next_allowed = self.att_svc.punch(employee_code=code, new_type=kind)
        if ok:
            messagebox.showinfo("打刻", f"{msg}\n（{code} / {self.name_map.get(code, '')}）")
            self.allowed_next_set = next_allowed
            self.message_var.set("打刻しました。")
        else:
            messagebox.showwarning("打刻できません", msg)
            self.allowed_next_set = next_allowed
        self._update_buttons(can_enable=True)

    # ---------- ボタン状態更新 ----------
    def _update_buttons(self, can_enable: bool):
        def st(ptype: str) -> str:
            return "normal" if (can_enable and (ptype in self.allowed_next_set)) else "disabled"

        self.btn_in.configure(state=st("CLOCK_IN"))
        self.btn_out.configure(state=st("CLOCK_OUT"))
        self.btn_break.configure(state=st("BREAK_START"))
        self.btn_back.configure(state=st("BREAK_END"))

    # ---------- 終了処理 ----------
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
