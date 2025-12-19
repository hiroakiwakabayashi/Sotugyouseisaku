# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox
from datetime import date, timedelta, datetime
from typing import Optional

from app.infra.db.shift_repo import ShiftRepo
from app.infra.db.employee_repo import EmployeeRepo


# =========================
# 共通: カレンダー付き入力
# =========================
class DatePickerEntry(ctk.CTkFrame):
    def __init__(self, master, textvariable=None, width=130, placeholder_text="YYYY-MM-DD"):
        super().__init__(master)
        import tkinter as tk

        self.var = textvariable or tk.StringVar()
        self.entry = ctk.CTkEntry(
            self, width=width, textvariable=self.var,
            placeholder_text=placeholder_text, state="readonly"
        )
        self.entry.pack(side="left", fill="x")
        self.entry.bind("<Button-1>", self._open_popup)

        self.btn = ctk.CTkButton(self, text="📅", width=34, command=self._open_popup)
        self.btn.pack(side="left", padx=4)

        self._popup = None
        self._cal = None

    def _open_popup(self, *_):
        import tkinter as tk
        from tkcalendar import Calendar

        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            self._popup.destroy()

        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.geometry(f"+{x}+{y}")
        self._popup.attributes("-topmost", True)

        # 初期値
        sel = date.today()
        try:
            if self.var.get():
                sel = datetime.strptime(self.var.get(), "%Y-%m-%d").date()
        except Exception:
            pass

        self._cal = Calendar(
            self._popup,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            year=sel.year, month=sel.month, day=sel.day,
            locale="ja_JP", font=("Meiryo UI", 15),
            showweeknumbers=False, showothermonthdays=False
        )
        self._cal.pack(padx=8, pady=(8, 4))

        BTN_W, BTN_H = 110, 36
        btns = ctk.CTkFrame(self._popup)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(btns, text="確定", width=BTN_W, height=BTN_H, command=self._ok)\
            .pack(side="left", padx=(30, 8))
        ctk.CTkButton(btns, text="キャンセル", width=BTN_W, height=BTN_H, command=self._cancel)\
            .pack(side="right", padx=(8, 30))

        self._popup.focus_force()
        self._popup.bind("<FocusOut>", lambda e: self._cancel())

    def _ok(self):
        if self._cal:
            self.var.set(self._cal.get_date())
        self._cancel()

    def _cancel(self):
        import tkinter as tk
        if self._popup and tk.Toplevel.winfo_exists(self._popup):
            self._popup.destroy()
        self._popup = None
        self._cal = None


# =========================
# Shift Editor (カードスタイル)
# =========================
def _today_str():
    return date.today().strftime("%Y-%m-%d")


def _week_range_str():
    d = date.today()
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _month_range_str():
    d = date.today().replace(day=1)
    if d.month == 12:
        next_first = d.replace(year=d.year + 1, month=1, day=1)
    else:
        next_first = d.replace(month=d.month + 1, day=1)
    last = next_first - timedelta(days=1)
    return d.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")


class ShiftEditorScreen(ctk.CTkFrame):
    """シフト作成・編集（カード版）"""

    def __init__(self, master):
        super().__init__(master)
        self.shift_repo = ShiftRepo()
        self.emp_repo = EmployeeRepo()

        self._rows: list[dict] = []
        self._row_count = 0

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== タイトル =====
        ctk.CTkLabel(
            self,
            text="🗓 シフト作成・編集",
            font=("Meiryo UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # =========================
        # フィルタ用の変数（UI生成より先に必ず作る）
        # =========================

        # 従業員候補
        self.emp_values = ["(全員)"] + [
            f'{r["code"]}:{r["name"]}' for r in self.emp_repo.list_all()
        ]
        self.emp_var = ctk.StringVar(value=self.emp_values[0])

        # 期間（初期値：今週）
        s0, e0 = _week_range_str()
        self.start_var = ctk.StringVar(value=s0)
        self.end_var = ctk.StringVar(value=e0)


        # =========================================================
        # フィルタエリア（勤怠一覧と同一UI構造：2段・均等配置）
        # =========================================================
        filt = ctk.CTkFrame(self)
        filt.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        filt.grid_columnconfigure(0, weight=1)

        BTN_H = 32  # 勤怠一覧と同じ

        # ---------- 1段目：従業員 / 開始日 / 終了日 ----------
        row1 = ctk.CTkFrame(filt, fg_color="transparent")
        row1.grid(row=0, column=0, sticky="w")

        # ★ 間隔を狭める（4→2）
        PADX = 10
        PADY = 4
        LABEL_PAD = (0, 4)

        # 従業員（col=0）
        emp_box = ctk.CTkFrame(row1, fg_color="transparent")
        emp_box.grid(row=0, column=0, sticky="w", padx=PADX, pady=PADY)
        ctk.CTkLabel(emp_box, text="従業員").pack(side="left", padx=LABEL_PAD)
        ctk.CTkOptionMenu(
            emp_box,
            values=self.emp_values,
            variable=self.emp_var,
            width=220,
        ).pack(side="left")

        # 開始日（col=1）
        start_box = ctk.CTkFrame(row1, fg_color="transparent")
        start_box.grid(row=0, column=1, sticky="w", padx=PADX, pady=PADY)
        ctk.CTkLabel(start_box, text="開始日").pack(side="left", padx=LABEL_PAD)
        DatePickerEntry(start_box, textvariable=self.start_var, width=130).pack(side="left")

        # 終了日（col=2）
        end_box = ctk.CTkFrame(row1, fg_color="transparent")
        end_box.grid(row=0, column=2, sticky="w", padx=PADX, pady=PADY)
        ctk.CTkLabel(end_box, text="終了日").pack(side="left", padx=LABEL_PAD)
        DatePickerEntry(end_box, textvariable=self.end_var, width=130).pack(side="left")
        
        # ---------- 2段目：クイックボタン列（均等5分割） ----------
        row2 = ctk.CTkFrame(filt, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        for c in range(4):
            row2.grid_columnconfigure(c, weight=1)

        quick_buttons = [
            ("今日", self._quick_today),
            ("今週", self._quick_week),
            ("今月", self._quick_month),
            ("今年", self._quick_year),
        ]
        for col, (label, cmd) in enumerate(quick_buttons):
            ctk.CTkButton(
                row2,
                text=label,
                height=BTN_H,
                command=cmd,
                font=("Meiryo UI", 15, "bold"),
            ).grid(row=0, column=col, padx=4, pady=(2, 4), sticky="ew")

        # ===== 一覧エリア（ヘッダー＋カード） =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 8))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        list_frame = ctk.CTkFrame(body, fg_color="transparent")
        list_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=0)
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # 0:選択, 1:ID, 2:従業員コード, 3:氏名, 4:日付, 5:開始, 6:終了, 7:メモ
        self._col_widths = [46, 50, 130, 240, 130, 80, 80, 250]

                # カード内の「入力欄(Entry)」の実際の幅
        # 0:選択, 1:ID, 2:従業員コード, 3:氏名, 4:日付, 5:開始, 6:終了, 7:メモ
        # 0,1,7 は Entry ではないので 0、他は好きな値を入れる
        self._entry_widths = [0, 0, 80, 160, 80, 45, 45, 0]
        # ↑ 数値を変えるだけで各入力欄の幅を調整できる


        # ===== ヘッダー（カードと同じ大枠＋セル） =====
        head_card = ctk.CTkFrame(
            list_frame,
            corner_radius=10,
            border_width=1,
            border_color="#B8C1CC",
            fg_color="#FFFFFF",
        )
        # ★ ヘッダー全体を 4px 右へずらす（カードのチェックボックス枠に合わせる）
        HEAD_OFFSET = 4
        head_card.grid(row=0, column=0, sticky="ew", padx=(HEAD_OFFSET, 0), pady=6)

        # ★ 余った横幅はメモ列だけが食う（カードと同じルール）
        for i, w in enumerate(self._col_widths):
            if i == 7:  # メモ列
                head_card.grid_columnconfigure(i, weight=1, minsize=w)
            else:       # 0〜6列は固定幅
                head_card.grid_columnconfigure(i, weight=0, minsize=w)

        PADY = 4
        PADX_NORMAL = (8, 4)          # 通常列の左右余白（カードと同じ）

        # ★ ヘッダーを 4px 右に寄せたぶん、メモ列の右余白も 4px 増やして
        #    「ヘッダーのメモ右端 ＝ カードのメモ右端」を維持する
        SCROLLBAR_PAD = 16 + HEAD_OFFSET   # 16 + 4 = 20
        PADX_LAST = (8, 4 + SCROLLBAR_PAD)

        def make_head_cell(col: int, title: str, anchor: str = "w", is_last: bool = False):
            # メモ列だけ右余白を広げて、カード側のメモ右端と合わせる
            pad = PADX_LAST if is_last else PADX_NORMAL

            border_color = "#D1D5DB"
            border_width = 1

            cell = ctk.CTkFrame(
                head_card,
                fg_color="#FFFFFF",
                corner_radius=6,
                border_width=border_width,
                border_color=border_color,
                height=28,
            )
            cell.grid(row=0, column=col, padx=pad, pady=PADY, sticky="ew")
            cell.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(
                cell,
                text=title,
                font=("Meiryo UI", 13, "bold"),
                text_color="#374151",
                anchor=anchor,
            )
            # ★ ここが「選択」と同じ余白（左右 4px）
            lbl.pack(expand=True, fill="both", padx=4, pady=2)

            return cell

        # 0列目（選択）は中央寄せ。それ以外は左寄せ。
        # ★ 親が head_card なので、左端はカードの cell_sel と同じ位置になる
        make_head_cell(0, "選択", anchor="center")
        make_head_cell(1, "ID", anchor="center")
        make_head_cell(2, "従業員コード", anchor="center")
        make_head_cell(3, "氏名")
        make_head_cell(4, "日付")
        make_head_cell(5, "開始", anchor="center")
        make_head_cell(6, "終了", anchor="center")
        # ★ メモ列だけ is_last=True で、右端をカードのメモ列と完全一致させる
        make_head_cell(7, "メモ", is_last=True)

        # ===== スクロール（カード）=====
        self.scroll = ctk.CTkScrollableFrame(list_frame, height=420, fg_color="#ECEFF1")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        # ===== 操作 =====
        ops = ctk.CTkFrame(self)
        ops.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))

        ctk.CTkButton(ops, text="追加行", width=120, command=self._new_row)\
            .pack(side="left", padx=6)
        ctk.CTkButton(ops, text="選択行を保存（追加/更新）", width=180, command=self._save_selected)\
            .pack(side="left", padx=6)
        ctk.CTkButton(ops, text="選択行を削除",
                    fg_color="#E74C3C", hover_color="#C0392B",
                    width=140, command=self._delete_selected)\
            .pack(side="left", padx=6)

        self._search()

    # ===== クイック =====
    def _quick_today(self):
        t = _today_str()
        self.start_var.set(t)
        self.end_var.set(t)
        self._search()

    def _quick_week(self):
        s, e = _week_range_str()
        self.start_var.set(s)
        self.end_var.set(e)
        self._search()

    def _quick_month(self):
        s, e = _month_range_str()
        self.start_var.set(s)
        self.end_var.set(e)
        self._search()

    def _quick_year(self):
        today = date.today()
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
        self.start_var.set(start.strftime("%Y-%m-%d"))
        self.end_var.set(end.strftime("%Y-%m-%d"))
        self._search()
    
    
    # ===== 行管理 =====
    def _clear_rows(self):
        for r in self._rows:
            for w in r["widgets"]:
                try:
                    w.destroy()
                except Exception:
                    pass
        self._rows.clear()
        self._row_count = 0

    def _add_row(
        self,
        *,
        id: Optional[int],
        employee_code: str,
        employee_name: str,
        work_date: str,
        start_time: str,
        end_time: str,
        note: str,
    ):
        rindex = self._row_count

        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=10,
            border_width=1,
            border_color="#B8C1CC",
            fg_color="#FFFFFF",
        )
        card.grid(row=rindex, column=0, sticky="ew", padx=0, pady=6)

        # 余った横幅はメモ列だけが食う（ヘッダーと同じルール）
        #   0:選択, 1:ID, 2:従業員コード, 3:氏名, 4:日付, 5:開始, 6:終了, 7:メモ
        for i, w in enumerate(self._col_widths):
            if i == 7:
                # メモ列だけは余り幅を食う
                card.grid_columnconfigure(i, weight=1, minsize=w)
            else:
                # 0〜6列は固定幅（ヘッダーと同じ）
                card.grid_columnconfigure(i, weight=0, minsize=w)

        PADY = 4
        PADX = (8, 4)

        def make_cell(parent, col):
            """全列共通の通常セル"""
            cell = ctk.CTkFrame(
                parent,
                fg_color="#FFFFFF",
                corner_radius=6,
                border_width=1,
                border_color="#D1D5DB",
                height=28,
            )
            cell.grid(row=0, column=col, padx=PADX, pady=PADY, sticky="ew")
            cell.grid_columnconfigure(0, weight=1)
            return cell

        # 0: チェックボックス
        sel_var = ctk.BooleanVar(value=False)

        # ★ 列幅50 - 左右pad(8+4) = 38px → ヘッダーの赤枠と同じ幅
        SELECT_INNER_WIDTH = self._col_widths[0] - (8 + 4)
        cell_sel = ctk.CTkFrame(
            card,
            fg_color="#FFFFFF",
            corner_radius=0,
            border_width=0,
            width=SELECT_INNER_WIDTH,
            height=32,
        )
        # ★ 列0内で左寄せ固定。col幅は 38 + 8 + 4 = 50 に収まるのでヘッダーと同じ。
        cell_sel.grid(row=0, column=0, padx=(8, 1), pady=4, sticky="w")
        cell_sel.grid_propagate(False)

        sel = ctk.CTkCheckBox(
            cell_sel,
            text="",
            variable=sel_var,
            width=0,
        )
        # 赤枠の中で左右均等になるよう中央配置
        sel.place(relx=0.5, rely=0.5, anchor="center")

        # 1: ID
        cell_id = make_cell(card, 1)
        id_lbl = ctk.CTkLabel(cell_id, text=str(id) if id else "-", anchor="center")
        id_lbl.pack(expand=True, fill="both", padx=0, pady=0)

        # 2: 従業員コード
        cell_code = make_cell(card, 2)
        code_e = ctk.CTkEntry(
            cell_code,
            width=self._entry_widths[2],
            border_width=0,
        )
        code_e.insert(0, employee_code)
        # 横方向には広げず、枠の中で左寄せ
        code_e.pack(
            side="left",
            padx=4,
            pady=2,
            fill="y",
            expand=False,
        )

        # 3: 氏名
        cell_name = make_cell(card, 3)
        name_e = ctk.CTkEntry(
            cell_name,
            width=self._entry_widths[3],
            border_width=0,
        )
        name_e.insert(0, employee_name)
        name_e.pack(
            side="left",
            padx=4,
            pady=2,
            fill="y",
            expand=False,
        )

        # 4: 日付
        cell_date = make_cell(card, 4)
        date_e = ctk.CTkEntry(
            cell_date,
            width=self._entry_widths[4],
            border_width=0,
        )
        date_e.insert(0, work_date)
        date_e.pack(
            side="left",
            padx=4,
            pady=2,
            fill="y",
            expand=False,
        )

        # 5: 開始
        cell_st = make_cell(card, 5)
        st_e = ctk.CTkEntry(
            cell_st,
            width=self._entry_widths[5],
            border_width=0,
        )
        st_e.insert(0, start_time)
        st_e.pack(
            side="left",
            padx=4,
            pady=2,
            fill="y",
            expand=False,
        )

        # 6: 終了
        cell_en = make_cell(card, 6)
        en_e = ctk.CTkEntry(
            cell_en,
            width=self._entry_widths[6],
            border_width=0,
        )
        en_e.insert(0, end_time)
        en_e.pack(
            side="left",
            padx=4,
            pady=2,
            fill="y",
            expand=False,
        )

        # 7: メモ
        cell_note = make_cell(card, 7)
        note_e = ctk.CTkEntry(cell_note, border_width=0)
        note_e.insert(0, note)
        note_e.pack(expand=True, fill="both", padx=4, pady=2)

        self._rows.append({
            "id": id,
            "widgets": [card, cell_sel, sel, id_lbl, name_e, code_e, date_e, st_e, en_e, note_e],
            "map": {
                "sel_var": sel_var,
                "id_lbl": id_lbl,     # ← ラベルへの参照を保持
                "name": name_e,
                "code": code_e,
                "date": date_e,
                "st": st_e,
                "en": en_e,
                "note": note_e,
            }
        })
        self._row_count += 1

    # ===== 入出力 =====
    def _selected_maps(self):
        """
        選択行を (row_dict, data_dict) のタプルで返す。
        data_dict["id"] は row_dict["id"] をそのまま持つ。
        """
        out: list[tuple[dict, dict]] = []
        for r in self._rows:
            if r["map"]["sel_var"].get():
                m = {
                    "id": r["id"],
                    "employee_name": r["map"]["name"].get().strip(),
                    "employee_code": r["map"]["code"].get().strip(),
                    "work_date": r["map"]["date"].get().strip(),
                    "start_time": r["map"]["st"].get().strip(),
                    "end_time": r["map"]["en"].get().strip(),
                    "note": r["map"]["note"].get().strip(),
                }
                out.append((r, m))
        return out

    def _validate(self, m: dict) -> tuple[bool, str]:
        if not m["employee_code"]:
            return False, "従業員コードが未入力です。"

        d = m["work_date"]
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            return False, "日付は YYYY-MM-DD 形式で入力してください。"

        for key, label in (("start_time", "開始"), ("end_time", "終了")):
            t = m[key]
            try:
                datetime.strptime(t, "%H:%M")
            except Exception:
                return False, f"{label}は HH:MM 形式で入力してください。"

        if m["start_time"] >= m["end_time"]:
            return False, "開始≧終了 になっています。"

        return True, ""

    # ===== 動作 =====
    def _new_row(self):
        v = self.emp_var.get()
        code = ""
        name = ""
        if v != "(全員)":
            p = v.split(":", 1)
            if len(p) == 2:
                code, name = p[0].strip(), p[1].strip()

        day = (
            self.start_var.get()
            if self.start_var.get() == self.end_var.get()
            else _today_str()
        )

        self._add_row(
            id=None,
            employee_code=code,
            employee_name=name,
            work_date=day,
            start_time="09:00",
            end_time="18:00",
            note="",
        )

    def _search(self):
        self._clear_rows()

        s, e = self.start_var.get().strip(), self.end_var.get().strip()

        v = self.emp_var.get()
        code = None if v == "(全員)" else v.split(":", 1)[0].strip()

        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)

        name_map = {r["code"]: r["name"] for r in self.emp_repo.list_all()}

        for r in rows:
            self._add_row(
                id=r["id"],
                employee_code=r["employee_code"],
                employee_name=name_map.get(r["employee_code"], ""),
                work_date=r["work_date"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                note=r.get("note", ""),
            )

    def _save_selected(self):
        items = self._selected_maps()
        if not items:
            messagebox.showwarning("保存", "保存対象の行にチェックを入れてください。")
            return

        # 入力チェック
        for _row, m in items:
            ok, msg = self._validate(m)
            if not ok:
                messagebox.showwarning("入力エラー", msg)
                return

        # 保存 ＋ 新規行には ID を反映
        for row, m in items:
            new_id = self.shift_repo.upsert(
                id=m["id"],
                employee_code=m["employee_code"],
                work_date=m["work_date"],
                start_time=m["start_time"],
                end_time=m["end_time"],
                note=m["note"],
            )

            # ★ 新規（m["id"] が None）のとき、upsert が返した ID を UI に反映
            if (m["id"] is None or m["id"] == "") and new_id:
                row["id"] = new_id
                row["map"]["id_lbl"].configure(text=str(new_id))

        messagebox.showinfo("保存", f"{len(items)} 件を保存しました。")
        # 必要なら再検索で完全同期
        self._search()

    def _delete_selected(self):
        items = self._selected_maps()
        if not items:
            messagebox.showwarning("削除", "削除対象の行にチェックを入れてください。")
            return

        if not messagebox.askyesno("確認", f"{len(items)} 件を削除します。"):
            return

        for _row, m in items:
            if m["id"]:
                self.shift_repo.delete(m["id"])

        messagebox.showinfo("削除", f"{len(items)} 件を削除しました。")
        self._search()
