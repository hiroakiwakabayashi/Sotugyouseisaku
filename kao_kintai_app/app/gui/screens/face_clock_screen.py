# app/gui/screens/face_clock_screen.py

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import glob
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import threading  # ★追加（顔データ読込を非同期化）
import sys  # ← 追加


from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.attendance_repo import AttendanceRepo
from app.services.attendance_service import AttendanceService
from app.services.config_service import ConfigService

def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


class FaceClockScreen(ctk.CTkFrame):
    """顔認証 + 打刻画面（勤怠一覧レイアウト & 見やすいボタン・情報表示）"""

    # レイアウト共通（勤怠一覧に合わせる）
    PADX = 16
    PADY = 8
    TITLE_FONT = ("Meiryo UI", 22, "bold")
    SUBHEAD_FONT = ("Meiryo UI", 14, "bold")
    INFO_KEY_FONT = ("Meiryo UI", 14, "bold")
    INFO_VAL_FONT = ("Meiryo UI", 16, "bold")
    BTN_FONT = ("Meiryo UI", 15, "bold")

    BTN_W = 96
    BTN_H = 48
    CAM_ASPECT = (16, 9)  # カメラは 16:9 で表示

    def __init__(self, master):
        super().__init__(master)

        # --- 依存関係 ---
        self.emp_repo = EmployeeRepo()
        self.att_repo = AttendanceRepo()
        self.att_svc = AttendanceService(self.att_repo)

        # Haar / ORB
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.orb = cv2.ORB_create(nfeatures=700)
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        # しきい値（Config）
        vcfg = ConfigService().get_vision()
        self.MIN_AREA_RATIO = float(vcfg.get("min_area_ratio", 0.10))
        self.MIN_BLUR_VAR = float(vcfg.get("min_blur_var", 80.0))
        self.BRIGHT_MIN = int(vcfg.get("bright_min", 50))
        self.BRIGHT_MAX = int(vcfg.get("bright_max", 210))
        self.MATCH_THRESHOLD = int(vcfg.get("match_threshold", 22))
        self.TOP_K_IMAGES = int(vcfg.get("top_k_images", 5))
        self.RECOG_INTERVAL = int(vcfg.get("recog_interval", 3))
        self.UNKNOWN_MIN_GAP = int(vcfg.get("unknown_min_gap", 8))
        self.UNKNOWN_MARGIN_RATIO = float(vcfg.get("unknown_margin_ratio", 0.25))
        self.ID_OK_FRAMES = int(vcfg.get("id_ok_frames", 2))
        self.QUALITY_OK_FRAMES = int(vcfg.get("quality_ok_frames", 2))

        # 表示用変数
        self.message_var = tk.StringVar(value="起動中…（顔データを読み込みます）")
        self.rec_code_var = tk.StringVar(value="--")
        self.rec_name_var = tk.StringVar(value="--")

        # 状態
        self.frame_count = 0
        self.last_best = ("", 0)  # (code, best_matches)
        self.allowed_next_set = set()
        self._current_code_ui = ""
        self._quality_ok_streak = 0
        self._id_ok_streak = 0
        self._last_candidate = ""

        # カメラ出力サイズ（リサイズで更新）
        self.cam_w = 960
        self.cam_h = 540
        self._cam_image: ctk.CTkImage | None = None

        # ★ 顔データ準備フラグ（非同期で読み込み）
        self._dataset_ready = False

        # ===== レイアウト（勤怠一覧と同じ 3 行構成） =====
        # 行: 0=タイトル, 1=ツールバー（薄灰）, 2=メイン（薄灰）
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- タイトル ---
        ctk.CTkLabel(
            self,
            text="📷 顔認証 打刻",
            font=self.TITLE_FONT,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=self.PADX,
            pady=(self.PADY * 2, self.PADY),
        )

        # --- 2 行目：ツールバー（カメラ映像 / 推定情報 / 打刻ボタン） ---
        toolbar = ctk.CTkFrame(
            self,
            fg_color="#E5E7EB",      # 薄い灰色
            corner_radius=6,
            border_width=1,
            border_color="#D1D5DB"   # 少し濃いグレーで輪郭
        )
        toolbar.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=self.PADX,
            pady=(0, self.PADY),
        )
        for i in range(8):
            toolbar.grid_columnconfigure(i, weight=0)
        toolbar.grid_columnconfigure(7, weight=1)  # 右端を伸ばして余白にする

        # 左：カメラ映像ラベル（薄灰ブロックの内側にも左 16px）
        ctk.CTkLabel(
            toolbar,
            text="カメラ映像",
            font=self.SUBHEAD_FONT,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(self.PADX, 12),
            pady=6,
        )

        # 中央：推定コード／推定氏名
        info_wrap = ctk.CTkFrame(toolbar, fg_color="transparent")
        info_wrap.grid(
            row=0,
            column=6,
            sticky="w",
            padx=(8, 0),
            pady=6,
        )
        self._kv_inline(info_wrap, "推定コード", self.rec_code_var)
        self._kv_inline(info_wrap, "推定氏名", self.rec_name_var)

        # 右：打刻ボタン
        btn_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_row.grid(row=0, column=7, sticky="e", padx=(0, self.PADX), pady=6)

        self.btn_in = ctk.CTkButton(
            btn_row,
            text="出勤",
            font=self.BTN_FONT,
            fg_color="#1E8449",
            hover_color="#145A32",
            text_color="#FFFFFF",
            command=lambda: self._punch("CLOCK_IN"),
            state="disabled",
            width=self.BTN_W,
            height=self.BTN_H,
            corner_radius=8,
        )
        self.btn_out = ctk.CTkButton(
            btn_row,
            text="退勤",
            font=self.BTN_FONT,
            fg_color="#B03A2E",
            hover_color="#7B241C",
            text_color="#FFFFFF",
            command=lambda: self._punch("CLOCK_OUT"),
            state="disabled",
            width=self.BTN_W,
            height=self.BTN_H,
            corner_radius=8,
        )
        self.btn_break = ctk.CTkButton(
            btn_row,
            text="休憩開始",
            font=self.BTN_FONT,
            fg_color="#CA6F1E",
            hover_color="#A04000",
            text_color="#FFFFFF",
            command=lambda: self._punch("BREAK_START"),
            state="disabled",
            width=self.BTN_W,
            height=self.BTN_H,
            corner_radius=8,
        )
        self.btn_back = ctk.CTkButton(
            btn_row,
            text="休憩終了",
            font=self.BTN_FONT,
            fg_color="#2874A6",
            hover_color="#1B4F72",
            text_color="#FFFFFF",
            command=lambda: self._punch("BREAK_END"),
            state="disabled",
            width=self.BTN_W,
            height=self.BTN_H,
            corner_radius=8,
        )

        for i, b in enumerate((self.btn_in, self.btn_out, self.btn_break, self.btn_back)):
            # 全ボタン同じ余白にする
            b.grid(row=0, column=i, padx=8, pady=0, sticky="e")

        # --- 3 行目：メイン領域（メッセージ + カメラ） ---
        main = ctk.CTkFrame(self)
        main.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=self.PADX,
            pady=(0, 0),
        )
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # メッセージ（薄灰ブロック内側にも左 16px）
        self.msg_lbl = ctk.CTkLabel(
            main,
            textvariable=self.message_var,
            justify="left",
            anchor="w",
        )
        self.msg_lbl.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=self.PADX,
            pady=(0, self.PADY),
        )

        # カメラ枠（薄い灰色のカードで囲む）
        self.cam_border = ctk.CTkFrame(
            main,
            fg_color="#E5E7EB",
            corner_radius=6,
            border_width=1,
            border_color="#D1D5DB"
        )
        self.cam_border.grid(
            row=1,
            column=0,
            sticky="n",
            padx=self.PADX,
            pady=(0, self.PADY * 2),
        )

        self.preview = ctk.CTkLabel(
            self.cam_border,
            text="",
            width=self.cam_w,
            height=self.cam_h,
            anchor="center",
        )
        self.preview.pack(padx=8, pady=8)

        # ---- 顔データ（非同期） ----
        self.name_map: dict[str, str] = {}
        self.des_map: dict[str, list[np.ndarray]] = {}

        # ---- カメラ起動 ----
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self._after_id: str | None = None

        # リサイズ連動（中央カラム幅に合わせる）
        self.bind("<Configure>", self._on_resize)

        # ★ 非同期：顔データ読み込み開始（UIを先に表示して固まりを防ぐ）
        self._update_buttons(can_enable=False)
        self.after(50, self._start_reload_dataset_async)

        # ループ開始
        self.after(10, self._loop)

    # ---------- 顔データ読み込み：非同期開始 ----------
    def _start_reload_dataset_async(self):
        def worker():
            try:
                self._reload_dataset(initial=True)
                self._dataset_ready = True
                self.after(0, lambda: self.message_var.set("カメラに顔を向けてください。"))
            except Exception:
                # 失敗してもUIが固まらないように
                self._dataset_ready = False
                self.after(0, lambda: self.message_var.set("顔データの読み込みに失敗しました。"))
        threading.Thread(target=worker, daemon=True).start()

    # ---------- 推定情報（横並びペア） ----------
    def _kv_inline(self, parent, label, var):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        # 2つ目以降のペアは少し右に余白を入れる
        wrap.pack(side="left", padx=(0 if not parent.pack_slaves() else 24))
        ctk.CTkLabel(
            wrap,
            text=label,
            font=self.INFO_KEY_FONT,
            anchor="w",
        ).pack(side="left")
        ctk.CTkLabel(
            wrap,
            textvariable=var,
            font=self.INFO_VAL_FONT,
            text_color="#333333",
            anchor="w",
        ).pack(side="left")

    # ---------- Resize：中央カラム幅いっぱいにカメラを合わせる ----------
    def _on_resize(self, _event=None):
        # 全体幅から左右 PADX×2 を引いた分を利用可能幅とする
        avail_w = max(320, self.winfo_width() - (self.PADX * 2))
        ar_w, ar_h = self.CAM_ASPECT
        new_w = int(min(avail_w, 1280))
        new_h = int(min(new_w * ar_h / ar_w, 720))

        self.cam_w, self.cam_h = new_w, new_h
        self.preview.configure(width=self.cam_w, height=self.cam_h)
        self.msg_lbl.configure(wraplength=self.cam_w)

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

            # ★ 顔データがまだ準備できていない間は、映像表示だけして認識はしない
            if not self._dataset_ready:
                self._update_buttons(can_enable=False)

                # カメラ画像を表示
                rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                rgb = cv2.resize(rgb, (self.cam_w, self.cam_h))
                pil_img = Image.fromarray(rgb)
                self._cam_image = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(self.cam_w, self.cam_h),
                )
                self.preview.configure(image=self._cam_image)

                self.frame_count += 1
                self._after_id = self.after(30, self._loop)
                return

            # 認識は間引き実行
            if (
                stable_ok
                and face_rect is not None
                and (self.frame_count % self.RECOG_INTERVAL == 0)
            ):
                x, y, w, h = face_rect
                face_roi = gray[y : y + h, x : x + w]

                code, best, second = self._recognize(face_roi)
                self.last_best = (code or "", best)

                # Unknown 判定
                unknown = False
                if code is None or best < self.MATCH_THRESHOLD:
                    unknown = True
                else:
                    gap = best - second
                    ratio = (best - second) / max(best, 1)
                    if gap < self.UNKNOWN_MIN_GAP and ratio < self.UNKNOWN_MARGIN_RATIO:
                        unknown = True

                if unknown:
                    self._reset_recognition_ui(
                        "未登録の顔、または一致度が低いため認証できません。"
                    )
                else:
                    if code == self._last_candidate:
                        self._id_ok_streak += 1
                    else:
                        self._last_candidate = code
                        self._id_ok_streak = 1

                    if self._id_ok_streak < self.ID_OK_FRAMES:
                        self.rec_code_var.set(code)
                        self.rec_name_var.set(self.name_map.get(code, "--"))
                        self.message_var.set(
                            "確認中…（ぶれずに少し静止してください）"
                        )
                    else:
                        name = self.name_map.get(code, "--")
                        self.rec_code_var.set(code)
                        self.rec_name_var.set(name)
                        if code != self._current_code_ui:
                            self._current_code_ui = code
                            last = self.att_svc.last_state(code)
                            self.allowed_next_set = self.att_svc.allowed_next(last)
                        self.message_var.set("顔を認識しました。打刻が可能です。")

            # ボタン状態
            can_enable = (
                stable_ok
                and (self._id_ok_streak >= self.ID_OK_FRAMES)
                and (self.last_best[0] != "")
            )
            self._update_buttons(can_enable=can_enable)

            # カメラ画像を中央カラム幅にフィットさせて表示（CTkImage 使用）
            rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            rgb = cv2.resize(rgb, (self.cam_w, self.cam_h))
            pil_img = Image.fromarray(rgb)
            self._cam_image = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(self.cam_w, self.cam_h),
            )
            self.preview.configure(image=self._cam_image)

            self.frame_count += 1

        self._after_id = self.after(30, self._loop)

    # ---------- 顔検出 + 品質評価 ----------
    def _evaluate_and_draw(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, 1.1, 5, minSize=(120, 120)
        )

        if len(faces) == 0:
            self._quality_ok_streak = 0
            # 顔データ読み込み中はメッセージを上書きしない（起動中メッセージ優先）
            if self._dataset_ready:
                self.message_var.set("顔を映してください。（正面・適度な距離）")
            return frame_bgr, False, None, gray

        x, y, fw, fh = max(faces, key=lambda r: r[2] * r[3])
        roi_gray = gray[y : y + fh, x : x + fw]

        area_ratio = (fw * fh) / (w * h)
        blur = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
        bright = float(np.mean(roi_gray))

        ok_size = area_ratio >= self.MIN_AREA_RATIO
        ok_blur = blur >= self.MIN_BLUR_VAR
        ok_light = self.BRIGHT_MIN <= bright <= self.BRIGHT_MAX

        msgs = []
        if not ok_size:
            msgs.append("顔をもう少し近づけてください。")
        if not ok_blur:
            msgs.append("ピントが合っていません（ぶれ/ぼけ）。")
        if not ok_light:
            msgs.append("暗すぎ/明るすぎです。照明や露出を調整してください。")

        all_ok = ok_size and ok_blur and ok_light
        if all_ok:
            self._quality_ok_streak += 1
        else:
            self._quality_ok_streak = 0

        stable_ok = self._quality_ok_streak >= self.QUALITY_OK_FRAMES
        if not stable_ok and self._dataset_ready:
            self.message_var.set(" / ".join(msgs) or "調整中…")

        color = (0, 200, 0) if stable_ok else (0, 165, 255) if msgs else (0, 200, 255)
        cv2.rectangle(frame_bgr, (x, y), (x + fw, y + fh), color, 2)

        return frame_bgr, stable_ok, (x, y, fw, fh), gray

    # ---------- 顔特徴量マッチング ----------
    def _recognize(self, roi_gray):
        kp, des_l = self.orb.detectAndCompute(roi_gray, None)
        if des_l is None or len(des_l) == 0:
            return None, 0, 0

        scores: list[tuple[str, int]] = []
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

    # ---------- 顔データ再読込 ----------
    def _reload_dataset(self, initial: bool = False):
        self.name_map.clear()
        self.des_map.clear()

        for r in self.emp_repo.list_all():
            self.name_map[r["code"]] = r["name"]

        root = _app_root() / "data" / "faces"
        root.mkdir(parents=True, exist_ok=True)

        for code in self.name_map.keys():
            imgs = sorted(glob.glob(str(root / code / "*.jpg")))
            if not imgs:
                continue
            imgs = imgs[-self.TOP_K_IMAGES :]

            desc_list: list[np.ndarray] = []
            for p in imgs:
                img = cv2.imread(p)
                if img is None:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(
                    gray, 1.1, 5, minSize=(100, 100)
                )
                roi = gray
                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                    roi = gray[y : y + h, x : x + w]
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

        ok, msg, next_allowed = self.att_svc.punch(
            employee_code=code, new_type=kind
        )
        if ok:
            messagebox.showinfo(
                "打刻", f"{msg}\n（{code} / {self.name_map.get(code, '')}）"
            )
            self.allowed_next_set = next_allowed
            self.message_var.set("打刻しました。")
        else:
            messagebox.showwarning("打刻できません", msg)
            self.allowed_next_set = next_allowed
        self._update_buttons(can_enable=True)

    # ---------- ボタン状態更新 ----------
    def _update_buttons(self, can_enable: bool):
        def st(ptype: str) -> str:
            return (
                "normal"
                if (can_enable and (ptype in self.allowed_next_set))
                else "disabled"
            )

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
