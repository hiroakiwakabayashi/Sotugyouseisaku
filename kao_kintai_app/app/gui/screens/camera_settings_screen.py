import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from app.services.config_service import ConfigService

class CameraSettingsScreen(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.cfg = ConfigService()
        v = self.cfg.get_vision()

        # 値（文字列）を双方向で扱う
        self.var_area   = tk.DoubleVar(value=float(v["min_area_ratio"]))
        self.var_blur   = tk.DoubleVar(value=float(v["min_blur_var"]))
        self.var_bmin   = tk.IntVar(value=int(v["bright_min"]))
        self.var_bmax   = tk.IntVar(value=int(v["bright_max"]))
        self.var_match  = tk.IntVar(value=int(v["match_threshold"]))
        self.var_topk   = tk.IntVar(value=int(v["top_k_images"]))
        self.var_intvl  = tk.IntVar(value=int(v["recog_interval"]))

        ctk.CTkLabel(self, text="🎥 カメラ・顔認証設定", font=("Meiryo UI", 22, "bold")).pack(anchor="w", padx=16, pady=(16,6))

        body = ctk.CTkFrame(self); body.pack(fill="x", padx=16, pady=(6,12))

        def row_pct(parent, label, var, minv, maxv, step=0.01):
            r = ctk.CTkFrame(parent); r.pack(fill="x", pady=6)
            ctk.CTkLabel(r, text=label, width=220, anchor="w").pack(side="left")
            val_lab = ctk.CTkLabel(r, text=f"{var.get()*100:.0f} %", width=80)
            val_lab.pack(side="right")
            s = ctk.CTkSlider(r, from_=minv, to=maxv, number_of_steps=int((maxv-minv)/step))
            s.set(var.get())
            def on_slide(_):
                var.set(s.get())
                val_lab.configure(text=f"{var.get()*100:.0f} %")
            s.configure(command=on_slide)
            s.pack(fill="x", padx=8)
        def row_float(parent, label, var, minv, maxv, step=1.0):
            r = ctk.CTkFrame(parent); r.pack(fill="x", pady=6)
            ctk.CTkLabel(r, text=label, width=220, anchor="w").pack(side="left")
            val_lab = ctk.CTkLabel(r, text=f"{var.get():.0f}", width=80); val_lab.pack(side="right")
            s = ctk.CTkSlider(r, from_=minv, to=maxv, number_of_steps=int((maxv-minv)/step))
            s.set(var.get())
            def on_slide(_):
                var.set(round(s.get(), 2))
                val_lab.configure(text=f"{var.get():.0f}")
            s.configure(command=on_slide)
            s.pack(fill="x", padx=8)
        def row_int(parent, label, var, minv, maxv):
            r = ctk.CTkFrame(parent); r.pack(fill="x", pady=6)
            ctk.CTkLabel(r, text=label, width=220, anchor="w").pack(side="left")
            val_lab = ctk.CTkLabel(r, text=str(var.get()), width=80); val_lab.pack(side="right")
            s = ctk.CTkSlider(r, from_=minv, to=maxv, number_of_steps=maxv-minv)
            s.set(var.get())
            def on_slide(_):
                var.set(int(round(s.get())))
                val_lab.configure(text=str(var.get()))
            s.configure(command=on_slide)
            s.pack(fill="x", padx=8)

        row_pct (body, "顔の大きさ（フレーム比）", self.var_area, 0.05, 0.40, 0.01)
        row_float(body, "ブレ閾値（Laplacian Var）", self.var_blur, 20, 400, 1)
        row_int (body, "明るさ 下限（0-255）", self.var_bmin, 0, 255)
        row_int (body, "明るさ 上限（0-255）", self.var_bmax, 0, 255)
        row_int (body, "認識マッチ閾値（良マッチ数）", self.var_match, 5, 100)
        row_int (body, "学習に使う登録画像数", self.var_topk, 1, 15)
        row_int (body, "認識の間引き（フレーム）", self.var_intvl, 1, 10)

        btns = ctk.CTkFrame(self); btns.pack(fill="x", padx=16, pady=(8,16))
        for i in range(3): btns.grid_columnconfigure(i, weight=1)
        ctk.CTkButton(btns, text="保存", command=self.save).grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        ctk.CTkButton(btns, text="デフォルトに戻す", command=self.reset_default).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(btns, text="※ 反映には画面の開き直し or 再起動が必要です").grid(row=0, column=2, padx=6, pady=6, sticky="w")

    def save(self):
        if self.var_bmin.get() > self.var_bmax.get():
            messagebox.showwarning("入力", "明るさの下限が上限を超えています。")
            return
        self.cfg.save_vision({
            "min_area_ratio": float(self.var_area.get()),
            "min_blur_var": float(self.var_blur.get()),
            "bright_min": int(self.var_bmin.get()),
            "bright_max": int(self.var_bmax.get()),
            "match_threshold": int(self.var_match.get()),
            "top_k_images": int(self.var_topk.get()),
            "recog_interval": int(self.var_intvl.get())
        })
        messagebox.showinfo("保存", "設定を保存しました。顔登録/認証画面を開き直すと反映されます。")

    def reset_default(self):
        from app.services.config_service import DEFAULT_CFG
        v = DEFAULT_CFG["vision"]
        self.var_area.set(float(v["min_area_ratio"]))
        self.var_blur.set(float(v["min_blur_var"]))
        self.var_bmin.set(int(v["bright_min"]))
        self.var_bmax.set(int(v["bright_max"]))
        self.var_match.set(int(v["match_threshold"]))
        self.var_topk.set(int(v["top_k_images"]))
        self.var_intvl.set(int(v["recog_interval"]))
        self.save()
