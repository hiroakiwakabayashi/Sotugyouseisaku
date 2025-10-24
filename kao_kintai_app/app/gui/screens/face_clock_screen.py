import os
print("[DEBUG] Loaded FaceClockScreen from:", os.path.abspath(__file__))

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

import os
print("Loaded FaceClockScreen from:", os.path.abspath(__file__))


class FaceClockScreen(ctk.CTkFrame):
    """
    顔認証 + 打刻画面（状態遷移ガード対応）
    - ORB + BFMatcher で簡易認識
    - AttendanceService で状態遷移をチェックしてから記録
    - 認識済みの人に対し「許可されるボタンのみ」有効化
    """
    def __init__(self, master):
        super().__init__(master)

        # 依存
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()
        self.att_svc  = AttendanceService(self.att_repo)

        # Haar（顔検出）/ ORB
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.orb = cv2.ORB_create(nfeatures=700)
        self.bf  = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # しきい値（設定から読込）
        vcfg = ConfigService().get_vision()
        self.MIN_AREA_RATIO = float(vcfg["min_area_ratio"])
        self.MIN_BLUR_VAR   = float(vcfg["min_blur_var"])
        self.BRIGHT_MIN     = int(vcfg["bright_min"])
        self.BRIGHT_MAX     = int(vcfg["bright_max"])
        self.MATCH_THRESHOLD = int(vcfg["match_threshold"])
        self.TOP_K_IMAGES    = int(vcfg["top_k_images"])
        self.RECOG_INTERVAL  = int(vcfg["recog_interval"])

        # 右ペイン固定
        self.RIGHT_W = 420; self.LABEL_W = 140; self.VALUE_W = 100; self.MSG_H = 68

        # 表示用
        self.message_var  = tk.StringVar(value="カメラに顔を向けてください。")
        self.q_face_var   = tk.StringVar(value="-")
        self.q_size_var   = tk.StringVar(value="-")
        self.q_blur_var   = tk.StringVar(value="-")
        self.q_light_var  = tk.StringVar(value="-")
        self.rec_code_var = tk.StringVar(value="--")
        self.rec_name_var = tk.StringVar(value="--")
        self.rec_score_var= tk.StringVar(value="-")

        # 状態
        self.frame_count = 0
        self.last_best: tuple[str,int] = ("", 0)   # (code, matches)
        self.allowed_next_set: set[str] = set()
        self._current_code_ui: str = ""            # UIに表示中のコード

        # レイアウト ------------------
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=0)

        # 左：プレビュー
        left = ctk.CTkFrame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(12,6), pady=12)
        left.grid_rowconfigure(0, weight=1); left.grid_columnconfigure(0, weight=1)
        self.preview = ctk.CTkLabel(left, text="")
        self.preview.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # 右：情報＆操作（固定幅）
        right = ctk.CTkFrame(self, width=self.RIGHT_W)
        right.grid(row=0, column=1, sticky="ns", padx=(6,12), pady=12)
        right.grid_propagate(False)

        ctk.CTkLabel(right, text="📷 顔認証 打刻", font=("Meiryo UI", 20, "bold")).pack(anchor="w", padx=12, pady=(12,6))

        res = ctk.CTkFrame(right); res.pack(fill="x", padx=12, pady=(4,6))
        self._kv(res, "推定コード", self.rec_code_var)
        self._kv(res, "推定氏名",   self.rec_name_var)
        self._kv(res, "マッチ数",    self.rec_score_var)

        ind = ctk.CTkFrame(right); ind.pack(fill="x", padx=12, pady=(6,6))
        self._kv(ind, "顔検出", self.q_face_var)
        self._kv(ind, "サイズ", self.q_size_var)
        self._kv(ind, "ブレ/ピント", self.q_blur_var)
        self._kv(ind, "明るさ", self.q_light_var)

        msg_wrap = ctk.CTkFrame(right, height=self.MSG_H); msg_wrap.pack(fill="x", padx=12, pady=(6,6))
        msg_wrap.pack_propagate(False)
        ctk.CTkLabel(msg_wrap, textvariable=self.message_var, wraplength=self.RIGHT_W-24, justify="left").pack(fill="both", expand=True, padx=2, pady=2)

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

        ctk.CTkButton(right, text="顔データを再読み込み", command=self._reload_dataset).pack(fill="x", padx=12, pady=(6,6))

        # データセット
        self.name_map: dict[str,str] = {}
        self.des_map: dict[str, list[np.ndarray]] = {}
        self._reload_dataset(initial=True)

        # カメラ
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self._after_id = None
        self._loop()

    # ---------- UIユーティリティ ----------
    def _kv(self, parent, label, var):
        row = ctk.CTkFrame(parent); row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=self.LABEL_W, anchor="w").pack(side="left")
        ctk.CTkLabel(row, textvariable=var, width=self.VALUE_W, anchor="w", font=("Consolas", 14)).pack(side="left")

    def _reset_recognition_ui(self, reason: str | None = None):
        self.last_best = ("", 0)
        self._current_code_ui = ""
        self.allowed_next_set = set()
        self.rec_code_var.set("--"); self.rec_name_var.set("--"); self.rec_score_var.set("-")
        if reason: self.message_var.set(reason)
        self._update_buttons(can_enable=False)

    # ---------- ループ ----------
    def _loop(self):
        ok, frame = self.cap.read()
        if ok:
            annotated, quality_ok, face_roi = self._evaluate_and_draw(frame)

            # 品質OK & 顔ROIが取れている時のみ認識
            if quality_ok and face_roi is not None and (self.frame_count % self.RECOG_INTERVAL == 0):
                code, matches = self._recognize(face_roi)
                self.last_best = (code, matches) if code else ("", 0)

                if code:
                    # 認識UI更新
                    name = self.name_map.get(code, "--")
                    self.rec_code_var.set(code); self.rec_name_var.set(name); self.rec_score_var.set(str(matches))
                    self.message_var.set("顔を認識しました。打刻が可能です。")
                    # 新しい人物を認識したら許可セットを更新
                    if code != self._current_code_ui:
                        self._current_code_ui = code
                        last = self.att_svc.last_state(code)
                        self.allowed_next_set = self.att_svc.allowed_next(last)
                else:
                    # 未認識（登録なし/閾値未満）
                    self._reset_recognition_ui("未登録の顔です。明るさ/距離/角度を調整するか、顔データを登録してください。")

            # ボタン状態を反映（品質OKかつ認識済みのときのみ、有効ボタンを限定ON）
            self._update_buttons(can_enable=quality_ok and (self.last_best[0] != ""))

            # 表示
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.preview.configure(image=imgtk); self.preview.image = imgtk
            self.frame_count += 1

        self._after_id = self.after(30, self._loop)

    # ---------- 品質評価 ----------
    def _evaluate_and_draw(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(120,120))

        if len(faces) == 0:
            self._set_quality(face=False, size=None, blur=None, bright=None)
            self._reset_recognition_ui("顔を映してください。（カメラの前で正面を向いてください）")
            return frame_bgr, False, None

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
        if not ok_light: msgs.append("暗すぎ/明るすぎです。照明や露出を調整してください。")

        all_ok = ok_size and ok_blur and ok_light
        self._set_quality(face=True, size=ok_size, blur=ok_blur, bright=ok_light)
        if not all_ok:
            self.message_var.set(" / ".join(msgs) or "調整中…")

        color = (0,200,0) if all_ok else (0,165,255) if msgs else (0,200,255)
        cv2.rectangle(frame_bgr, (x,y), (x+fw,y+fh), color, 2)

        return frame_bgr, all_ok, roi_gray if all_ok else None

    def _set_quality(self, face, size, blur, bright):
        def t(v, seen=False):
            if v is None and not seen: return "-"
            return "OK" if v else "NG"
        self.q_face_var.set(t(face, seen=True))
        self.q_size_var.set(t(size))
        self.q_blur_var.set(t(blur))
        self.q_light_var.set(t(bright))

    # ---------- 簡易認識（ORB + BFMatcher） ----------
    def _recognize(self, roi_gray):
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
                good = [m for m in matches if m.distance <= 60]
                total_good = max(total_good, len(good))
            if total_good > best_matches:
                best_matches = total_good; best_code = code

        if best_code and best_matches >= self.MATCH_THRESHOLD:
            return best_code, best_matches
        return None, 0

    # ---------- データセット再読込 ----------
    def _reload_dataset(self, initial=False):
        self.name_map.clear(); self.des_map.clear()

        for r in self.emp_repo.list_all():
            self.name_map[r["code"]] = r["name"]

        root = Path(__file__).resolve().parents[3] / "data" / "faces"
        root.mkdir(parents=True, exist_ok=True)

        for code in self.name_map.keys():
            imgs = sorted(glob.glob(str(root / code / "*.jpg")))
            if not imgs: continue
            imgs = imgs[-self.TOP_K_IMAGES:]

            desc_list = []
            for p in imgs:
                img = cv2.imread(p); 
                if img is None: continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(100,100))
                roi = gray
                if len(faces) > 0:
                    x,y,w,h = max(faces, key=lambda r: r[2]*r[3])
                    roi = gray[y:y+h, x:x+w]
                kp, des = self.orb.detectAndCompute(roi, None)
                if des is not None and len(des) > 0:
                    desc_list.append(des)
            if desc_list:
                self.des_map[code] = desc_list

        if not initial:
            messagebox.showinfo("再読込", "顔データを再読み込みしました。")

    # ---------- 打刻（ガード付き） ----------
    def _punch(self, kind: str):
        code = self.last_best[0]
        if not code:
            messagebox.showwarning("未認識", "顔が認識されていません。")
            return

        ok, msg, next_allowed = self.att_svc.punch(employee_code=code, new_type=kind)
        if ok:
            messagebox.showinfo("打刻", f"{msg}\n（{code} / {self.name_map.get(code,'')}）")
            # 許可セット更新（今の状態=kind に基づく）
            self.allowed_next_set = next_allowed
            self.message_var.set("打刻しました。次の操作が可能です。")
            # 直近状態が変わったのでボタン再反映
            self._update_buttons(can_enable=True)
        else:
            messagebox.showwarning("打刻できません", msg)
            # 許可セットだけ反映（メッセージで案内済み）
            self.allowed_next_set = next_allowed
            self._update_buttons(can_enable=True)

    def _update_buttons(self, can_enable: bool):
        def st(ptype: str) -> str:
            return "normal" if (can_enable and (ptype in self.allowed_next_set)) else "disabled"
        self.btn_in.configure(   state=st("CLOCK_IN"))
        self.btn_break.configure(state=st("BREAK_START"))
        self.btn_back.configure( state=st("BREAK_END"))
        self.btn_out.configure(  state=st("CLOCK_OUT"))

    # ---------- 終了処理 ----------
    def destroy(self):
        try:
            if self._after_id: self.after_cancel(self._after_id)
        except Exception: pass
        try:
            if self.cap and self.cap.isOpened(): self.cap.release()
        except Exception: pass
        super().destroy()
