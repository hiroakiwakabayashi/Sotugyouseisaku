# -*- coding: utf-8 -*-
import customtkinter as ctk
import tkinter as tk
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

        # レイアウト
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(
            self, text="🗂 提出シフト（週次レビュー）", font=("Meiryo UI", 22, "bold")
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 8))

        # ツールバー
        bar = ctk.CTkFrame(self)
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        bar.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(bar, text="従業員").grid(row=0, column=0, padx=(6, 4), pady=6, sticky="e")
        self.emp_menu = ctk.CTkOptionMenu(
            bar, variable=self.emp_var, values=self._employee_options(), width=240
        )
        self.emp_menu.grid(row=0, column=1, padx=(0, 12), pady=6, sticky="w")

        prev_btn = ctk.CTkButton(bar, text="◀ 前の週", width=110, command=lambda: self._move_week(-7))
        next_btn = ctk.CTkButton(bar, text="次の週 ▶", width=110, command=lambda: self._move_week(+7))
        prev_btn.grid(row=0, column=2, padx=6, pady=6)
        next_btn.grid(row=0, column=3, padx=6, pady=6)

        self.week_label = ctk.CTkLabel(bar, text="", font=("Meiryo UI", 14, "bold"))
        self.week_label.grid(row=0, column=4, padx=6, pady=6, sticky="w")

        ctk.CTkButton(bar, text="更新", width=90, command=self.reload).grid(row=0, column=5, padx=6, pady=6)
        ctk.CTkButton(bar, text="CSVエクスポート", command=self.export_csv).grid(row=0, column=6, padx=6, pady=6, sticky="e")

        # テーブル（ツリー）
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 12))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=32, font=("Meiryo UI", 12))
        style.configure("Treeview.Heading", font=("Meiryo UI", 13, "bold"))

        self.tree = ttk.Treeview(
            wrap,
            columns=("date", "start", "end", "hours", "note", "code", "name"),
            show="tree headings",
        )
        self.tree.heading("#0", text="従業員 / 明細")
        self.tree.heading("date",  text="日付")
        self.tree.heading("start", text="開始")
        self.tree.heading("end",   text="終了")
        self.tree.heading("hours", text="時間")
        self.tree.heading("note",  text="メモ")
        self.tree.heading("code",  text="コード")
        self.tree.heading("name",  text="氏名")

        self.tree.column("#0",    width=260)
        self.tree.column("date",  width=120, anchor="center")
        self.tree.column("start", width=90,  anchor="center")
        self.tree.column("end",   width=90,  anchor="center")
        self.tree.column("hours", width=90,  anchor="e")
        self.tree.column("note",  width=220, anchor="w")
        self.tree.column("code",  width=120, anchor="center")
        self.tree.column("name",  width=160, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        # 合計表示
        self.total_var = tk.StringVar(value="合計 0:00")
        ctk.CTkLabel(self, textvariable=self.total_var, font=("Meiryo UI", 14)).grid(
            row=3, column=0, sticky="e", padx=16, pady=(0, 8)
        )

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
        rows = self.shift_repo.list_all_with_names(start_date=s, end_date=e, employee_code=code)

        # 従業員 → 明細 にグループ化
        by_emp = {}
        for r in rows:
            emp_code = r["employee_code"]
            by_emp.setdefault(emp_code, {
                "name": r.get("name", ""),
                "rows": []
            })["rows"].append(r)

        week_total = 0
        # 並びを安定させる
        for emp_code in sorted(by_emp.keys()):
            emp = by_emp[emp_code]
            name = emp["name"]
            # 個人合計
            emp_total = 0

            parent = self.tree.insert(
                "", "end", text=f"{name}（{emp_code}）", values=("", "", "", "", "", emp_code, name), open=True
            )

            # 日付→開始 時刻順
            emp["rows"].sort(key=lambda x: (x["work_date"], x["start_time"], x["end_time"]))

            for r in emp["rows"]:
                mins = max(0, _hhmm_to_minutes(r["end_time"]) - _hhmm_to_minutes(r["start_time"]))
                emp_total += mins
                self.tree.insert(
                    parent, "end", text="",
                    values=(
                        # date, start, end, hours, note, code, name
                        r["work_date"],
                        r["start_time"],
                        r["end_time"],
                        _minutes_to_hhmm(mins),
                        r.get("note", ""),
                        r["employee_code"],
                        r.get("name", "")
                    )
                )

            # 親ノードに合計を表示（ツリー左のテキストに追記）
            self.tree.item(parent, text=f"{name}（{emp_code}）  合計: {_minutes_to_hhmm(emp_total)}")
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

        # 現表示のデータを吐き出し（木構造を走査）
        try:
            import csv
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["従業員コード", "氏名", "日付", "開始", "終了", "時間(hh:mm)", "メモ"])
                for parent in self.tree.get_children(""):
                    pvals = self.tree.item(parent)["values"]
                    pcode, pname = pvals[5], pvals[6]
                    for child in self.tree.get_children(parent):
                        vals = self.tree.item(child)["values"]
                        w.writerow([pcode, pname, vals[0], vals[1], vals[2], vals[3], vals[4]])
            messagebox.showinfo("CSV", f"保存しました：\n{path}")
        except Exception as e:
            messagebox.showerror("CSV", f"保存に失敗しました：{e}")
