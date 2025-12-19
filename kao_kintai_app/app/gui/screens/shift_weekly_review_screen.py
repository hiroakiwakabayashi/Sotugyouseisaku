#app\gui\screens\shift_weekly_review_screen.py
# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
import re
from tkinter import ttk, filedialog, messagebox
from datetime import date, timedelta, datetime

from app.infra.db.shift_repo import ShiftRepo
from app.infra.db.employee_repo import EmployeeRepo


def _hhmm_to_minutes(hhmm: str) -> int:
    """'HH:MM' → 分。想定外は 0 分。"""
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _minutes_to_hhmm(mins: int) -> str:
    if mins <= 0:
        return "0:00"
    h, m = divmod(mins, 60)
    return f"{h}:{m:02d}"


class ShiftWeeklyReviewScreen(ctk.CTkFrame):
    """
    su 用：提出されたシフトの週次レビュー画面
    - 週移動（前/次）
    - 従業員フィルタ（全員 or 個人）
    - ツリー表示（従業員ごとに親ノード、その配下に日別/時間帯）
        ※ Treeview の #0 列は論理的に「従業員 / 明細」だが、
            画面上では非表示（width=0）にしている。
    - 合計時間（従業員別 & 週全体）
    - CSV エクスポート
    """
    def __init__(self, master):
        super().__init__(master)
        self.shift_repo = ShiftRepo()
        self.emp_repo = EmployeeRepo()

        # 週の基準（表示開始日＝週の月曜日）
        today = date.today()
        self.week_start = today - timedelta(days=(today.weekday() % 7))  # 月曜=0

        # フィルタ
        self.emp_var = tk.StringVar(value="全員")

        # レイアウト（勤怠一覧画面と同じ行構成）
        # row=0: タイトル
        # row=1: フィルタバー
        # row=2: テーブル本体
        # row=3: 合計ラベル
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(
            self, text="🗂 提出シフト（週次レビュー）", font=("Meiryo UI", 22, "bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # =========================================================
        # フィルタバー（勤怠一覧の filt に合わせたバランス）
        # =========================================================
        # ツールバー
        bar = ctk.CTkFrame(self)
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(6, weight=1)

        # 勤怠一覧と同じボタン高さ
        BTN_H = 32

        ctk.CTkLabel(bar, text="従業員").grid(
            row=0, column=0,
            padx=(4, 4), pady=4,
            sticky="e"
        )

        self.emp_menu = ctk.CTkOptionMenu(
            bar,
            variable=self.emp_var,
            values=self._employee_options(),
            width=240,
        )
        self.emp_menu.grid(
            row=0, column=1,
            padx=(0, 8), pady=4,
            sticky="w"
        )

        # 前の週 / 次の週（高さだけ統一、幅は勤怠一覧と同じくデフォルト）
        prev_btn = ctk.CTkButton(
            bar,
            text="◀ 前の週",
            height=BTN_H,
            font=("Meiryo UI", 15, "bold"),
            command=lambda: self._move_week(-7),
        )
        next_btn = ctk.CTkButton(
            bar,
            text="次の週 ▶",
            height=BTN_H,
            font=("Meiryo UI", 15, "bold"),
            command=lambda: self._move_week(+7),
        )
        prev_btn.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        next_btn.grid(row=0, column=3, padx=4, pady=4, sticky="ew")

        self.week_label = ctk.CTkLabel(
            bar,
            text="",
            font=("Meiryo UI", 14, "bold"),
        )
        self.week_label.grid(
            row=0, column=4,
            padx=4, pady=4,
            sticky="w"
        )

        # 更新ボタンも高さだけ合わせて、幅指定は外す（勤怠一覧の検索ボタンと同じスタイル）
        ctk.CTkButton(
            bar,
            text="更新",
            height=BTN_H,
            font=("Meiryo UI", 15, "bold"),
            command=self.reload,
        ).grid(
            row=0, column=5,
            padx=4, pady=4,
            sticky="ew"
        )

        # =========================================================
        # テーブル（ツリー）… 勤怠一覧の table_wrap と同じ比率
        # =========================================================
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 0))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        # 明細は「合計/日付/開始/終了/時間/メモ」
        # ※ 合計は親行だけ表示し、子行は空にする（X位置が必ず揃う）
        tree_columns = ("total", "date", "start", "end", "hours", "note")

        self.tree = ttk.Treeview(
            wrap,
            columns=tree_columns,
            show="tree headings",
        )

        # ※ Treeview の #0 列は論理的に「従業員 / 明細」（削除しない）
        # self.tree.heading("#0", text="従業員 / 明細")
        self.tree.heading("#0",      text="従業員")
        self.tree.heading("total",   text="合計")
        self.tree.heading("date",    text="日付")
        self.tree.heading("start",   text="開始")
        self.tree.heading("end",     text="終了")
        self.tree.heading("hours",   text="時間")
        self.tree.heading("note",    text="メモ")

        # #0 は左寄せ、合計は右寄せ固定（ここでX位置が安定する）
        self.tree.column("#0",     width=280, anchor="w")
        self.tree.column("total",  width=50, anchor="center")       # ← ここが「右端から固定」の要
        self.tree.column("date",   width=80, anchor="center")
        self.tree.column("start",  width=50,  anchor="center")
        self.tree.column("end",    width=50,  anchor="center")
        self.tree.column("hours",  width=50,  anchor="center")
        self.tree.column("note",   width=480, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # ===== Treeview 見た目（親行を薄グレー＋強調、子行はゼブラ）=====
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # ★ 行高を少し上げる（親行を“少し大きく見せる”効果）
        style.configure("Treeview", rowheight=30, font=("Meiryo UI", 12))
        style.configure("Treeview.Heading", font=("Meiryo UI", 13, "bold"))

        # ★ 親行（従業員行）
        self.tree.tag_configure("parent", background="#F3F4F6", font=("Meiryo UI", 12, "bold"))

        # ★ 子行（明細）ゼブラ：勤怠一覧と同じタグ名にする
        self.tree.tag_configure("even", background="#FFFFFF")
        self.tree.tag_configure("odd",  background="#F9FAFB")


        # ======= フッター（勤怠一覧と同じ構成）=======
        footer = ctk.CTkFrame(self)
        footer.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 12))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)

        # 左下：週合計
        self.total_var = tk.StringVar(value="週合計 0:00")
        ctk.CTkLabel(
            footer,
            textvariable=self.total_var,
            font=("Meiryo UI", 14)
        ).grid(row=0, column=0, sticky="w", padx=6)

        # 右下：CSVエクスポート
        ctk.CTkButton(
            footer,
            text="CSVエクスポート",
            command=self.export_csv,
            width=120
        ).grid(row=0, column=1, sticky="e", padx=6)

        # 初回ロード
        self.reload()

    # ------- ヘルパ -------
    def _employee_options(self):
        rows = self.emp_repo.list_all()
        return ["全員"] + [f"{r['code']} {r['name']}" for r in rows]

    def _selected_code(self) -> str | None:
        v = self.emp_var.get()
        if not v or v == "全員":
            return None
        return v.split(" ")[0] if " " in v else v

    def _move_week(self, days: int):
        self.week_start += timedelta(days=days)
        self.reload()

    def _week_label_text(self):
        s = self.week_start
        e = s + timedelta(days=6)
        return f"{s.strftime('%Y/%m/%d')} 〜 {e.strftime('%Y/%m/%d')}"

    # ------- ロード -------
    def reload(self):
        # 週ラベル
        self.week_label.configure(text=self._week_label_text())

        # クリア
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        s = self.week_start.strftime("%Y-%m-%d")
        e = (self.week_start + timedelta(days=6)).strftime("%Y-%m-%d")

        code = self._selected_code()
        rows = self.shift_repo.list_all_with_names(
            start_date=s,
            end_date=e,
            employee_code=code
        )

        # 従業員 → 明細 にグループ化
        by_emp: dict[str, dict] = {}
        for r in rows:
            emp_code = r["employee_code"]
            by_emp.setdefault(emp_code, {
                "name": r.get("name", ""),
                "rows": []
            })["rows"].append(r)

        week_total = 0

        # ★ ゼブラ柄用カウンタ（勤怠一覧と同じ even/odd パターン）
        zebra_index = 0

        # 並びを安定させる
        for emp_code in sorted(by_emp.keys()):
            emp = by_emp[emp_code]
            name = emp["name"]
            # 個人合計
            emp_total = 0

            parent = self.tree.insert(
                "",
                "end",
                text=f"{name}（{emp_code}）",
                values=("", "", "", "", "", ""),  # (total,date,start,end,hours,note)
                open=True,
                tags=("parent",),                 # ★ 親行タグ
            )

            # ★ 子行ゼブラ（親行とは別タグ）
            zebra = "even" if zebra_index % 2 == 0 else "odd"

            # 日付→開始 時刻順
            emp["rows"].sort(key=lambda x: (x["work_date"], x["start_time"], x["end_time"]))

            for r in emp["rows"]:
                mins = max(
                    0,
                    _hhmm_to_minutes(r["end_time"]) - _hhmm_to_minutes(r["start_time"]),
                )
                emp_total += mins

                # ★ 子行だけゼブラ柄を付与
                zebra = "even" if zebra_index % 2 == 0 else "odd"
                self.tree.insert(
                    parent,
                    "end",
                    text="",
                    values=(
                        "",                 # total（子は空）
                        r["work_date"],     # date
                        r["start_time"],    # start
                        r["end_time"],      # end
                        _minutes_to_hhmm(mins),  # hours
                        r.get("note", ""),  # note
                    ),
                    tags=(zebra,),
                )
                zebra_index += 1  # ← 次の行へ

            # 親ノード表示：合計位置を縦に統一（名前/コードの長さに依存しない）
            left = f"{name}（{emp_code}）"
            right = f"合計: {_minutes_to_hhmm(emp_total)}"

            # #0 列の幅(px)から「だいたい何文字入るか」を決めて整形する
            # Meiryo UI 12〜13pt 前提の目安。ズレるなら 24 を微調整。
            COL0_PX = 280  # self.tree.column("#0", width=280) と合わせる
            CHAR_PX = 8    # 1文字あたりの目安px（日本語だと誤差あり）
            LEFT_COL_CHARS = max(10, (COL0_PX // CHAR_PX) - len(right) - 2)

            text = f"{left:<{LEFT_COL_CHARS}}{right}"

            # 親行のテキストは「氏名（コード）」だけにする
            self.tree.item(
                parent,
                text=f"{name}（{emp_code}）"
            )

            # 合計は「total 列」にセット（右寄せでX位置が揃う）
            self.tree.set(
                parent,
                "total",
                _minutes_to_hhmm(emp_total)
            )
            week_total += emp_total

        self.total_var.set(f"週合計 {_minutes_to_hhmm(week_total)}")

    # ------- エクスポート -------
    def export_csv(self):
        # 週範囲
        s = self.week_start
        e = s + timedelta(days=6)
        s_str = s.strftime("%Y-%m-%d")
        e_str = e.strftime("%Y-%m-%d")

        path = filedialog.asksaveasfilename(
            title="CSVに保存",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"shifts_{s.strftime('%Y%m%d')}_{e.strftime('%Y%m%d')}.csv"
        )
        if not path:
            return

        # 現表示のデータを Treeview から吐き出し（構造そのまま）
        try:
            import csv
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                # 列順も画面と合わせる
                w.writerow(["従業員コード", "氏名", "日付", "開始", "終了", "時間(hh:mm)", "メモ"])

            for parent in self.tree.get_children(""):

                # 親ノードの表示テキストから「氏名・コード」を抽出
                ptext = self.tree.item(parent)["text"]
                # 例: "細谷 真央（208IE800）  合計: 18:00"

                m = re.search(r"^(?P<name>.+?)（(?P<code>.+?)）", ptext)
                pname = (m.group("name") if m else "").strip()
                pcode = (m.group("code") if m else "").strip()

                # 子行（実データ）
                for child in self.tree.get_children(parent):
                    vals = self.tree.item(child)["values"]  # (date, start, end, hours, note)

                    w.writerow([
                        pcode,
                        pname,
                        vals[0],  # 日付
                        vals[1],  # 開始
                        vals[2],  # 終了
                        vals[3],  # 時間
                        vals[4],  # メモ
                    ])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")
