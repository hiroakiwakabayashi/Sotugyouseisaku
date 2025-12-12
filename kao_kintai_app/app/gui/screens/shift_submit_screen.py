# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import date, timedelta
import re

from app.infra.db.employee_repo import EmployeeRepo
from app.infra.db.shift_repo import ShiftRepo

# =========================
# 時刻ユーティリティ（要件対応）
# =========================

_COMPACT = re.compile(r"^\d{3,4}$")      # 600 / 0900 / 1730
_HHMM = re.compile(r"^\d{2}:\d{2}$")     # 06:00 / 17:30


def _from_db_to_compact(hhmm: str) -> str:
    """'HH:MM' → 'HMM/HHMM'（先頭0を落としてコロン無し）"""
    if not _HHMM.match(hhmm):
        return hhmm  # 想定外はそのまま返す
    hh, mm = hhmm.split(":")
    h = str(int(hh))  # 先頭ゼロ除去（'00'→'0'）
    return f"{h}{mm}"


def _compact_to_hhmm(s: str) -> str | None:
    """
    '600' / '0900' / '1730' → 'HH:MM' に正規化。
    不正なら None を返す。
    """
    if not s:
        return None
    s = s.strip()
    if not _COMPACT.match(s):
        return None
    # 後ろ2桁が分、前が時
    mm = int(s[-2:])
    hh = int(s[:-2])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return f"{hh:02d}:{mm:02d}"


def _lt_hhmm(a: str, b: str) -> bool:
    """a < b を 'HH:MM' で判定（双方とも 'HH:MM' 前提）"""
    ah, am = map(int, a.split(":"))
    bh, bm = map(int, b.split(":"))
    return (ah, am) < (bh, bm)


class ShiftSubmitScreen(ctk.CTkFrame):
    """
    従業員が週次でシフトを「希望提出」する画面。
    - 入力形式は 数字（600, 930, 1730 など）
    - フォーカスアウト or Enter で 'HH:MM' に自動整形
    - 7日分がスクロール無しで1画面に入るように調整
    """

    # ★ 列幅を固定してズレをなくす
    DATE_COL_WIDTH = 200   # 日付列の固定幅（px）
    TIME_ENTRY_WIDTH = 96  # 各 HHMM エントリの幅

    def __init__(self, master):
        super().__init__(master)
        self.emp_repo = EmployeeRepo()
        self.shift_repo = ShiftRepo()

        # 週の基準（表示開始日＝週の月曜日）
        today = date.today()
        self.week_start = today - timedelta(days=(today.weekday() % 7))  # 月曜=0

        # 従業員選択
        self.emp_var = tk.StringVar()
        emp_opts = self._employee_options()
        if emp_opts:
            self.emp_var.set(emp_opts[0])

        # レイアウト
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="🗓 シフト提出（週次 / 第1・第2希望、時刻はHHMM入力）",
            font=("Meiryo UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        # ツールバー（従業員・週移動）
        bar = ctk.CTkFrame(self)
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(bar, text="従業員").grid(
            row=0, column=0, padx=(8, 4), pady=6, sticky="e"
        )
        self.emp_menu = ctk.CTkOptionMenu(
            bar, variable=self.emp_var, values=emp_opts, width=250
        )
        self.emp_menu.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        prev_btn = ctk.CTkButton(
            bar, text="◀ 前の週", command=lambda: self._move_week(-7), width=110, height=34
        )
        next_btn = ctk.CTkButton(
            bar, text="次の週 ▶", command=lambda: self._move_week(+7), width=110, height=34
        )
        self.week_label = ctk.CTkLabel(bar, text="", font=("Meiryo UI", 14, "bold"))

        prev_btn.grid(row=0, column=2, padx=6, pady=6)
        next_btn.grid(row=0, column=3, padx=6, pady=6)
        self.week_label.grid(row=0, column=4, padx=6, pady=6, sticky="w")

        # ===== 行コンテナ（通常の Frame：スクロール無し） =====
        self.rows = ctk.CTkFrame(self, corner_radius=10, fg_color="#F3F4F6")
        self.rows.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 4))

        # ヘッダー用の列幅（親フレーム側）
        self.rows.grid_columnconfigure(0, weight=0, minsize=self.DATE_COL_WIDTH)
        for col in (1, 2, 3, 4):
            self.rows.grid_columnconfigure(col, weight=0, minsize=110)
        self.rows.grid_columnconfigure(5, weight=1)

        # 操作用ボタン
        foot = ctk.CTkFrame(self)
        foot.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))
        foot.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            foot,
            text="この週を保存",
            command=self._save_week,
            height=40,
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
        ).pack(side="right", padx=6)

        # 週表示・行構築
        self._build_week_rows()

    # ---------------- 支援 ----------------
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return [f"{r['code']} {r['name']}" for r in rows]

    def _selected_code(self) -> str | None:
        v = self.emp_var.get()
        if not v:
            return None
        return v.split(" ")[0] if " " in v else v

    def _move_week(self, days: int):
        self.week_start += timedelta(days=days)
        self._build_week_rows()

    def _week_label_text(self):
        s = self.week_start
        e = self.week_start + timedelta(days=6)
        return f"{s.strftime('%Y/%m/%d')} 〜 {e.strftime('%Y/%m/%d')}"

    # ===== 時刻エントリ用：自動コロン挿入 =====
    def _auto_colon(self, widget: tk.Entry | ctk.CTkEntry):
        txt = widget.get().strip()
        if not txt:
            return
        # 既に HH:MM なら何もしない
        if _HHMM.match(txt):
            return
        hhmm = _compact_to_hhmm(txt)
        if hhmm:
            widget.delete(0, tk.END)
            widget.insert(0, hhmm)

    def _attach_time_entry_behaviors(self, entry: ctk.CTkEntry):
        """時刻入力エントリに共通の挙動を付与（フォーカスアウト時に自動フォーマット）"""
        entry.bind("<FocusOut>", lambda e, w=entry: self._auto_colon(w))

    # ---------------- 行構築 ----------------
    def _build_week_rows(self):
        # クリア
        for w in self.rows.winfo_children():
            w.destroy()

        # 週ラベル更新
        self.week_label.configure(text=self._week_label_text())

        # ヘッダ行（row=0）
        header_titles = ["日付", "第1希望 IN", "第1希望 OUT", "第2希望 IN", "第2希望 OUT", "メモ"]
        for col, text in enumerate(header_titles):
            if col == 0:
                ctk.CTkLabel(
                    self.rows,
                    text=text,
                    font=("Meiryo UI", 13, "bold"),
                    text_color="#4B5563",
                    width=self.DATE_COL_WIDTH,
                    anchor="w",
                ).grid(row=0, column=col, padx=6, pady=(4, 4), sticky="w")
            else:
                ctk.CTkLabel(
                    self.rows,
                    text=text,
                    font=("Meiryo UI", 13, "bold"),
                    text_color="#4B5563",
                ).grid(row=0, column=col, padx=(18,18), pady=(4, 4), sticky="w")

        # 行エディット用保持: {date_str: {...widgets}}
        self._editors: dict[str, dict[str, ctk.CTkEntry]] = {}
        # キー移動用マトリクス [7日][5列]
        self._entry_matrix: list[list[ctk.CTkEntry]] = []

        # 7日分作成（row=1〜7）
        for i in range(7):
            d = self.week_start + timedelta(days=i)
            row_entries = self._add_day_row(d, row_index=i + 1)
            self._entry_matrix.append(row_entries)

        # 行全体が下の余白まで広がるように、1〜7行に重みを付ける
        for i in range(1, 8):
            self.rows.grid_rowconfigure(i, weight=1)

        # キーバインド設定（矢印キー & Enter）
        self._bind_entry_keys()

        # 既存データを反映
        self._fill_from_db()

    def _add_day_row(self, day: date, row_index: int) -> list[ctk.CTkEntry]:
        """
        1 日分の行をコンパクトなフレームにまとめて作成。
        rows(row=row_index) に row_frame を 1 行だけ置いて、その中を横並びにする。
        """
        dstr = day.strftime("%Y-%m-%d")
        editors: dict[str, ctk.CTkEntry] = {}
        self._editors[dstr] = editors

        # 行コンテナ（ゼブラ柄）
        zebra_color = "#EEF2FF" if row_index % 2 == 1 else "#F9FAFB"
        row_frame = ctk.CTkFrame(self.rows, fg_color=zebra_color, corner_radius=6)
        row_frame.grid(
            row=row_index,
            column=0,
            columnspan=6,
            sticky="ew",
            padx=4,
            pady=(3, 3),
        )

        # 行内の列幅（ここでも同じ幅を固定）
        row_frame.grid_columnconfigure(0, weight=0, minsize=self.DATE_COL_WIDTH)
        for col in (1, 2, 3, 4):
            row_frame.grid_columnconfigure(col, weight=0, minsize=110)
        row_frame.grid_columnconfigure(5, weight=1)

        # 日付ラベル
        ctk.CTkLabel(
            row_frame,
            text=day.strftime("%Y-%m-%d (%a)"),
            font=("Meiryo UI", 13, "bold"),
            text_color="#111827",
            width=self.DATE_COL_WIDTH,
            anchor="w",
        ).grid(row=0, column=0, padx=6, pady=6, sticky="w")

        # エントリ生成ヘルパ（placeholder は HHMM）
        def _mk_entry(col: int, placeholder: str = "HHMM", width: int = None):
            e = ctk.CTkEntry(
                row_frame,
                placeholder_text=placeholder,
                width=width or self.TIME_ENTRY_WIDTH,
                height=30,
            )
            e.grid(row=0, column=col, padx=6, pady=6, sticky="w")
            # 時刻欄には自動コロン挿入を付与
            if placeholder == "HHMM":
                self._attach_time_entry_behaviors(e)
            return e

        editors["in1"] = _mk_entry(1)
        editors["out1"] = _mk_entry(2)
        editors["in2"] = _mk_entry(3)
        editors["out2"] = _mk_entry(4)

        editors["note"] = ctk.CTkEntry(
            row_frame,
            placeholder_text="メモ（任意）",
            width=420,
            height=30,
        )
        editors["note"].grid(row=0, column=5, padx=6, pady=6, sticky="ew")

        # 行ごとのエントリ配列（キー移動用）
        return [
            editors["in1"],
            editors["out1"],
            editors["in2"],
            editors["out2"],
            editors["note"],
        ]

    # ---------- キー移動 ----------
    def _bind_entry_keys(self):
        rows = len(self._entry_matrix)
        cols = 5
        for r in range(rows):
            for c in range(cols):
                w = self._entry_matrix[r][c]
                if not w:
                    continue

                # Enter は「コロン整形 → 右へ移動」
                w.bind(
                    "<Return>",
                    lambda e, rr=r, cc=c: (
                        self._auto_colon(e.widget),
                        self._move_focus(rr, cc, "RIGHT"),
                    ),
                )
                w.bind("<Right>",  lambda e, rr=r, cc=c: self._move_focus(rr, cc, "RIGHT"))
                w.bind("<Left>",   lambda e, rr=r, cc=c: self._move_focus(rr, cc, "LEFT"))
                w.bind("<Up>",     lambda e, rr=r, cc=c: self._move_focus(rr, cc, "UP"))
                w.bind("<Down>",   lambda e, rr=r, cc=c: self._move_focus(rr, cc, "DOWN"))

    def _move_focus(self, r: int, c: int, direction: str):
        rows = len(self._entry_matrix)
        cols = 5

        nr, nc = r, c
        if direction == "RIGHT":
            if c < cols - 1:
                nc = c + 1
            else:
                # 行末 → 次の行の一番左
                if r < rows - 1:
                    nr = r + 1
                    nc = 0
        elif direction == "LEFT":
            if c > 0:
                nc = c - 1
            else:
                if r > 0:
                    nr = r - 1
                    nc = cols - 1
        elif direction == "UP":
            if r > 0:
                nr = r - 1
        elif direction == "DOWN":
            if r < rows - 1:
                nr = r + 1

        target = self._entry_matrix[nr][nc]
        if target:
            target.focus_set()
            try:
                target.icursor(tk.END)
            except Exception:
                pass

    # ---------------- 既存データ反映 ----------------
    def _fill_from_db(self):
        code = self._selected_code()
        if not code:
            return
        s = self.week_start
        e = s + timedelta(days=6)
        rows = self.shift_repo.list_by_range(
            s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), employee_code=code
        )

        # 同日のレコードを時間順にして第1/第2へ割り振る
        by_day: dict[str, list[dict]] = {}
        for r in rows:
            by_day.setdefault(r["work_date"], []).append(r)

        def _key(r):
            return (r["start_time"], r["end_time"])

        for d, lst in by_day.items():
            lst.sort(key=_key)
            ed = self._editors.get(d)
            if not ed:
                continue
            if len(lst) >= 1:
                ed["in1"].delete(0, tk.END)
                ed["in1"].insert(0, _from_db_to_compact(lst[0]["start_time"]))
                ed["out1"].delete(0, tk.END)
                ed["out1"].insert(0, _from_db_to_compact(lst[0]["end_time"]))
                if lst[0].get("note"):
                    ed["note"].delete(0, tk.END)
                    ed["note"].insert(0, lst[0]["note"])
            if len(lst) >= 2:
                ed["in2"].delete(0, tk.END)
                ed["in2"].insert(0, _from_db_to_compact(lst[1]["start_time"]))
                ed["out2"].delete(0, tk.END)
                ed["out2"].insert(0, _from_db_to_compact(lst[1]["end_time"]))

    # ---------------- 保存 ----------------
    def _save_week(self):
        code = self._selected_code()
        if not code:
            messagebox.showwarning("従業員", "従業員を選択してください。")
            return

        items = []  # (id, code, work_date, start_time, end_time, note)
        errors = []

        for dkey, ed in self._editors.items():
            in1_raw = ed["in1"].get().strip()
            out1_raw = ed["out1"].get().strip()
            in2_raw = ed["in2"].get().strip()
            out2_raw = ed["out2"].get().strip()
            note = ed["note"].get().strip()

            # 第1希望（両方埋まっているときだけ登録対象）
            if in1_raw or out1_raw:
                in1 = _compact_to_hhmm(in1_raw) or (in1_raw if _HHMM.match(in1_raw) else None)
                out1 = _compact_to_hhmm(out1_raw) or (out1_raw if _HHMM.match(out1_raw) else None)
                if not (in1 and out1 and _lt_hhmm(in1, out1)):
                    errors.append(f"{dkey} 第1希望は HHMM / IN<OUT で入力してください。例: 600, 930, 1730")
                else:
                    items.append((None, code, dkey, in1, out1, note))

            # 第2希望（任意／両方埋まっているときだけ登録対象）
            if in2_raw or out2_raw:
                in2 = _compact_to_hhmm(in2_raw) or (in2_raw if _HHMM.match(in2_raw) else None)
                out2 = _compact_to_hhmm(out2_raw) or (out2_raw if _HHMM.match(out2_raw) else None)
                if not (in2 and out2 and _lt_hhmm(in2, out2)):
                    errors.append(f"{dkey} 第2希望は HHMM / IN<OUT で入力してください。例: 600, 930, 1730")
                else:
                    items.append((None, code, dkey, in2, out2, note))

        if errors:
            messagebox.showwarning(
                "入力チェック",
                "\n".join(errors[:8]) + ("\n…他" if len(errors) > 8 else ""),
            )
            return

        if not items:
            if messagebox.askyesno("確認", "入力が空です。この週の既存シフトをすべて削除しますか？"):
                self._delete_all_in_week(code)
                messagebox.showinfo("シフト", "この週のシフトを削除しました。")
                self._build_week_rows()
            return

        # 週の既存シフトを削除してから一括保存（上書き）
        self._delete_all_in_week(code)
        self.shift_repo.upsert_many(items)
        messagebox.showinfo("シフト", "この週のシフトを保存しました。")
        self._build_week_rows()

    def _delete_all_in_week(self, code: str):
        s = self.week_start
        e = s + timedelta(days=6)
        exists = self.shift_repo.list_by_range(
            s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"), employee_code=code
        )
        for r in exists:
            self.shift_repo.delete(r["id"])
