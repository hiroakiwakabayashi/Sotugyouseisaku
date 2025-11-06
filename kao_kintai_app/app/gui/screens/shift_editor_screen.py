# app/gui/screens/shift_view_screen.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import date, datetime, timedelta
import csv

from app.infra.db.shift_repo import ShiftRepo
from app.infra.db.employee_repo import EmployeeRepo


def _today_str():
    return date.today().strftime("%Y-%m-%d")

def _week_range():
    d = date.today()
    start = d - timedelta(days=d.weekday())  # 月曜はじめ
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def _month_range():
    d = date.today().replace(day=1)
    if d.month == 12:
        next_first = d.replace(year=d.year+1, month=1, day=1)
    else:
        next_first = d.replace(month=d.month+1, day=1)
    last = next_first - timedelta(days=1)
    return d.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d")

def _hhmm_to_minutes(hhmm: str) -> int:
    try:
        h, m = map(int, hhmm.split(":"))
        return h*60 + m
    except Exception:
        return 0


class ShiftViewScreen(ctk.CTkFrame):
    """シフト閲覧（読み取り専用）
       - 従業員選択（空=全員）
       - 期間絞り込み（今日 / 今週 / 今月 / 任意）
       - 一覧表示（日付・開始・終了・合計時間・メモ）
       - 件数/合計時間サマリ
       - CSV出力
    """
    def __init__(self, master):
        super().__init__(master)
        self.shift_repo = ShiftRepo()
        self.emp_repo = EmployeeRepo()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(self, text="🗓 シフト閲覧", font=("Meiryo UI", 18, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # ===== 条件行 =====
        cond = ctk.CTkFrame(self)
        cond.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))
        for i in range(12):
            cond.grid_columnconfigure(i, weight=0)
        cond.grid_columnconfigure(11, weight=1)

        # 従業員選択
        ctk.CTkLabel(cond, text="従業員:").grid(row=0, column=0, padx=(8,4), pady=8, sticky="w")
        self.emp_values = ["(全員)"] + [f'{r["code"]}:{r["name"]}' for r in self.emp_repo.list_all()]
        self.emp_var = ctk.StringVar(value=self.emp_values[0])
        self.emp_sel = ctk.CTkOptionMenu(cond, values=self.emp_values, variable=self.emp_var, width=200)
        self.emp_sel.grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # 期間
        ctk.CTkLabel(cond, text="期間:").grid(row=0, column=2, padx=(16,4), pady=8, sticky="w")
        s0, e0 = _week_range()
        self.start_var = ctk.StringVar(value=s0)
        self.end_var   = ctk.StringVar(value=e0)
        self.start_e = ctk.CTkEntry(cond, width=120, textvariable=self.start_var, placeholder_text="YYYY-MM-DD")
        self.end_e   = ctk.CTkEntry(cond, width=120, textvariable=self.end_var,   placeholder_text="YYYY-MM-DD")
        self.start_e.grid(row=0, column=3, padx=4, pady=8, sticky="w")
        self.end_e.grid(row=0, column=4, padx=4, pady=8, sticky="w")

        ctk.CTkButton(cond, text="今日",  width=64, command=self._quick_today).grid(row=0, column=5, padx=4)
        ctk.CTkButton(cond, text="今週",  width=64, command=self._quick_week).grid(row=0, column=6, padx=4)
        ctk.CTkButton(cond, text="今月",  width=64, command=self._quick_month).grid(row=0, column=7, padx=4)
        ctk.CTkButton(cond, text="検索",  width=90, command=self._search).grid(row=0, column=8, padx=(12,4))
        ctk.CTkButton(cond, text="CSV出力", width=90, command=self._export_csv).grid(row=0, column=9, padx=4)

        # ===== 一覧（カード枠＋区切り線＋ゼブラ） =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # ヘッダ
        header = ctk.CTkFrame(body, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        titles = ["従業員コード", "氏名", "日付", "開始", "終了", "合計(h)", "メモ"]
        for i, t in enumerate(titles):
            ctk.CTkLabel(header, text=t, anchor="w", font=("Meiryo UI", 13, "bold")) \
                .grid(row=0, column=i, padx=10, pady=(10, 8), sticky="w")
            header.grid_columnconfigure(i, weight=1 if i in (0,1,2,6) else 0)

        # 区切り線（細フレーム）
        ctk.CTkFrame(body, height=1, fg_color="#D0D0D0") \
            .grid(row=0, column=0, sticky="ew", pady=(42, 6))

        self.scroll = ctk.CTkScrollableFrame(body, height=420)
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self._row_widgets = []

        self.summary = ctk.CTkLabel(body, text="—", anchor="w")
        self.summary.grid(row=2, column=0, sticky="ew", padx=8, pady=(8, 4))

        # 初回検索
        self._search()

    # ==== helpers ====
    def _emp_code(self):
        v = self.emp_var.get()
        return None if v == "(全員)" else v.split(":", 1)[0].strip()

    def _quick_today(self):
        t = _today_str()
        self.start_var.set(t); self.end_var.set(t)
        self._search()

    def _quick_week(self):
        s, e = _week_range()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    def _quick_month(self):
        s, e = _month_range()
        self.start_var.set(s); self.end_var.set(e)
        self._search()

    def _clear_rows(self):
        for w in self._row_widgets:
            try: w.destroy()
            except: pass
        self._row_widgets.clear()

    def _add_row(self, code, name, work_date, start, end, hours, note):
        idx = len(self._row_widgets)  # ウィジェット総数ベース
        row_index = idx // 7          # 1行=7セルなのでおおよその行番号

        # ゼブラ行の背景色
        bg_even = "#FAFAFA"
        bg_odd  = "#FFFFFF"
        row_bg  = bg_even if (row_index % 2 == 0) else bg_odd

        # 行を「カード」っぽく囲う
        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=10,
            border_width=1,
            border_color="#D9D9D9",
            fg_color=row_bg
        )
        # 横に余白、縦に少し間隔
        card.grid(row=row_index, column=0, sticky="ew", padx=8, pady=5)
        # カード内のカラム伸縮
        for i in (0,1,2,6):
            card.grid_columnconfigure(i, weight=1)

        # 各セル（適度に余白を増やして見やすく）
        cells = [
            ctk.CTkLabel(card, text=code,      anchor="w"),
            ctk.CTkLabel(card, text=name,      anchor="w"),
            ctk.CTkLabel(card, text=work_date, anchor="w"),
            ctk.CTkLabel(card, text=start,     anchor="w"),
            ctk.CTkLabel(card, text=end,       anchor="w"),
            ctk.CTkLabel(card, text=f"{hours:.2f}", anchor="e"),
            ctk.CTkLabel(card, text=note,      anchor="w"),
        ]
        for i, c in enumerate(cells):
            # 右寄せの合計(h)だけ e、それ以外は w/ew
            sticky = "e" if i == 5 else ("ew" if i in (0,1,2,6) else "w")
            c.grid(row=0, column=i, padx=10, pady=8, sticky=sticky)
            self._row_widgets.append(c)

        # カード自体も破棄対象へ（クリア時にまとめて消す）
        self._row_widgets.append(card)

    # ==== actions ====
    def _search(self):
        self._clear_rows()

        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        try:
            ds = datetime.strptime(s, "%Y-%m-%d")
            de = datetime.strptime(e, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("日付エラー", "日付は YYYY-MM-DD 形式で入力してください。")
            return
        if ds > de:
            messagebox.showwarning("日付エラー", "開始日が終了日より後になっています。")
            return

        code = self._emp_code()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)

        # 名前引き（必要ならキャッシュに）
        name_map = {r["code"]: r["name"] for r in self.emp_repo.list_all()}

        total_hours = 0.0
        for r in rows:
            st_m = _hhmm_to_minutes(r["start_time"])
            en_m = _hhmm_to_minutes(r["end_time"])
            mins = max(0, en_m - st_m)
            h = mins / 60.0
            total_hours += h

            code = r["employee_code"]
            name = name_map.get(code, "")
            self._add_row(
                code=code,
                name=name,
                work_date=r["work_date"],
                start=r["start_time"],
                end=r["end_time"],
                hours=h,
                note=r.get("note", "")
            )

        self.summary.configure(
            text=f"件数: {len(rows)}  / 合計時間: {total_hours:.2f} h"
        )

    def _export_csv(self):
        s, e = self.start_var.get().strip(), self.end_var.get().strip()
        code = self._emp_code()
        rows = self.shift_repo.list_by_range(start_date=s, end_date=e, employee_code=code)
        if not rows:
            messagebox.showinfo("CSV", "出力対象データがありません。")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSVファイル","*.csv")],
            initialfile=f"shifts_{code or 'all'}_{s}_{e}.csv"
        )
        if not path:
            return

        headers = ["id","employee_code","work_date","start_time","end_time","note"]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers + ["hours"])
                for r in rows:
                    st = _hhmm_to_minutes(r["start_time"])
                    en = _hhmm_to_minutes(r["end_time"])
                    h  = max(0, en - st) / 60.0
                    w.writerow([r.get(k,"") for k in headers] + [f"{h:.2f}"])
            messagebox.showinfo("CSV", "CSVを書き出しました。")
        except Exception as ex:
            messagebox.showerror("CSV", f"書き出しに失敗しました。\n{ex}")
