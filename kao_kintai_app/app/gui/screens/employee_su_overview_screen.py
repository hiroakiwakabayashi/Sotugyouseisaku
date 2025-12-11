# app/gui/screens/employee_su_overview_screen.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Dict
import csv

from app.infra.db.employee_repo import EmployeeRepo


def _norm_wage(emp: Dict) -> float:
    for k in ("wage", "hourly_wage", "hourlyRate", "hourly"):
        if k in emp and emp[k] not in (None, ""):
            try:
                return float(emp[k])
            except Exception:
                return 0.0
    return 0.0


def _text(emp: Dict, key: str, default: str = "") -> str:
    v = emp.get(key)
    return default if v is None else str(v)


class EmployeeSuOverviewScreen(ctk.CTkFrame):
    # 列幅の基本設定（ヘッダー／ボディ共通）
    CHECK_COL_WIDTH = 42        # チェックボックス列
    CODE_COL_WIDTH = 110        # コード列
    NAME_COL_WIDTH = 220        # 氏名列
    WAGE_COL_WIDTH = 130        # 時給列（エントリ幅もこれに合わせる）
    ROLE_COL_WIDTH = 120        # 役職列

    def __init__(self, master):
        super().__init__(master)
        self.repo = EmployeeRepo()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(
            self,
            text="👥 従業員一覧（su・時給編集可）",
            font=("Meiryo UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))

        # 条件エリア
        cond = ctk.CTkFrame(self, fg_color="#E0E4EA")
        cond.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        cond.grid_columnconfigure(10, weight=1)

        ctk.CTkLabel(cond, text="検索（コード/氏名）:").grid(
            row=0, column=0, padx=(12, 4), pady=10, sticky="w"
        )
        self.q_var = ctk.StringVar(value="")
        ctk.CTkEntry(
            cond,
            width=260,
            textvariable=self.q_var,
            placeholder_text="例）E0001 / 山田",
        ).grid(row=0, column=1, padx=(0, 20), pady=10, sticky="w")

        ctk.CTkLabel(cond, text="並び:", width=50).grid(
            row=0, column=2, sticky="w"
        )
        self.sort_values = ["コード昇順", "氏名昇順", "時給降順"]
        self.sort_var = ctk.StringVar(value=self.sort_values[0])
        ctk.CTkOptionMenu(
            cond,
            values=self.sort_values,
            variable=self.sort_var,
            width=140,
        ).grid(row=0, column=3, padx=(0, 20))

        ctk.CTkButton(
            cond, text="検索", width=90, command=self._search
        ).grid(row=0, column=4, padx=(0, 10))
        ctk.CTkButton(
            cond, text="CSV出力", width=90, command=self._export_csv
        ).grid(row=0, column=5)

        # 一覧エリア
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=18)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        # ヘッダー
        head = ctk.CTkFrame(body, fg_color="#D8DEE6", corner_radius=10)
        head.grid(row=0, column=0, sticky="ew")

        # 列の minsize をボディと合わせる
        head.grid_columnconfigure(0, minsize=self.CHECK_COL_WIDTH + 28, weight=0)
        head.grid_columnconfigure(1, minsize=self.CODE_COL_WIDTH, weight=0)
        head.grid_columnconfigure(2, minsize=self.NAME_COL_WIDTH, weight=0)
        head.grid_columnconfigure(3, minsize=self.WAGE_COL_WIDTH, weight=0)
        head.grid_columnconfigure(4, minsize=self.ROLE_COL_WIDTH, weight=0)
        head.grid_columnconfigure(5, weight=1)  # 備考は伸縮

        P_HEAD = 10

        # 列0：チェック用ダミー
        ctk.CTkLabel(
            head, text="", width=self.CHECK_COL_WIDTH, anchor="w"
        ).grid(row=0, column=0, padx=(18, 10), pady=P_HEAD, sticky="w")

        ctk.CTkLabel(head, text="コード", anchor="w").grid(
            row=0, column=1, padx=(47, 10), pady=P_HEAD, sticky="w"
        )
        ctk.CTkLabel(head, text="氏名", anchor="w").grid(
            row=0, column=2, padx=(48, 10), pady=P_HEAD, sticky="w"
        )
        ctk.CTkLabel(head, text="時給(円)", anchor="w").grid(
            row=0, column=3, padx=(70, 10), pady=P_HEAD, sticky="w"
        )
        ctk.CTkLabel(head, text="役職/属性", anchor="w").grid(
            row=0, column=4, padx=(47, 10), pady=P_HEAD, sticky="w"
        )
        ctk.CTkLabel(head, text="備考", anchor="w").grid(
            row=0, column=5, padx=(10, 10), pady=P_HEAD, sticky="w"
        )

        # 下線
        ctk.CTkFrame(body, height=1, fg_color="#C0C6D0").grid(
            row=1, column=0, sticky="ew"
        )

        # スクロール領域
        self.scroll = ctk.CTkScrollableFrame(
            body, fg_color="#F5F6F8", corner_radius=8
        )
        self.scroll.grid(row=2, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        # 下部ボタン
        ops = ctk.CTkFrame(self)
        ops.grid(row=3, column=0, sticky="ew", padx=18, pady=10)
        ctk.CTkButton(
            ops,
            text="💾 選択行の時給を保存",
            command=self._save_selected_wage,
        ).pack(side="left")

        self.summary = ctk.CTkLabel(self, text="—", anchor="w")
        self.summary.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 12))

        self._rows_widgets: List[ctk.CTkBaseClass] = []
        self._row_models: List[Dict] = []
        self._current_data: List[Dict] = []
        self._row_count = 0

        self._search()

    # ===== 行生成まわり =====
    def _clear_rows(self):
        for w in self._rows_widgets:
            w.destroy()
        self._rows_widgets.clear()
        self._row_models.clear()
        self._row_count = 0

    def _add_row(self, code, name, wage_val, role_text, memo):
        idx = self._row_count

        # 外枠カード（グレーの帯は少し控えめ）
        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=10,
            border_width=1,
            border_color="#BCC5D1",
        )
        card.grid(row=idx, column=0, sticky="ew", padx=0, pady=6, ipady=2)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="#FFFFFF")
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=6)

        # 各列の幅を固定（ヘッダーと同じ値）
        inner.grid_columnconfigure(0, minsize=self.CHECK_COL_WIDTH + 28, weight=0)
        inner.grid_columnconfigure(1, minsize=self.CODE_COL_WIDTH, weight=0)
        inner.grid_columnconfigure(2, minsize=self.NAME_COL_WIDTH, weight=0)
        inner.grid_columnconfigure(3, minsize=self.WAGE_COL_WIDTH, weight=0)
        inner.grid_columnconfigure(4, minsize=self.ROLE_COL_WIDTH, weight=0)
        inner.grid_columnconfigure(5, weight=1)  # 備考だけ伸縮

        P = 10

        # 列0：チェック
        chk = ctk.CTkCheckBox(inner, text="", width=self.CHECK_COL_WIDTH)
        chk.grid(row=0, column=0, padx=(18, 10), pady=P, sticky="w")

        # 列1：コード（元の位置感に近いパディング）
        lab_code = ctk.CTkLabel(inner, text=code, anchor="w")
        lab_code.grid(row=0, column=1, padx=(10, 10), pady=P, sticky="w")

        # 列2：氏名（以前と同じくらいの位置）
        lab_name = ctk.CTkLabel(inner, text=name, anchor="w")
        lab_name.grid(row=0, column=2, padx=(10, 10), pady=P, sticky="w")

        # 列3：時給（全行同じ幅＆位置）
        wage_var = ctk.StringVar(value=str(int(wage_val)) if wage_val else "")
        ent_wage = ctk.CTkEntry(inner, width=self.WAGE_COL_WIDTH, textvariable=wage_var)
        ent_wage.grid(row=0, column=3, padx=(10, 10), pady=P, sticky="w")

        # 列4：役職/属性
        lab_role = ctk.CTkLabel(inner, text=role_text, anchor="w")
        lab_role.grid(row=0, column=4, padx=(10, 10), pady=P, sticky="w")

        # 列5：備考
        lab_memo = ctk.CTkLabel(inner, text=memo, anchor="w")
        lab_memo.grid(row=0, column=5, padx=(10, 10), pady=P, sticky="w")

        self._rows_widgets += [
            card,
            inner,
            chk,
            lab_code,
            lab_name,
            ent_wage,
            lab_role,
            lab_memo,
        ]
        self._row_models.append(
            {"chk": chk, "code": code, "wage_var": wage_var}
        )
        self._row_count += 1

    # ===== 検索・並び替え =====
    def _filter_sort(self, items):
        q = self.q_var.get().strip().lower()
        if q:
            items = [
                r
                for r in items
                if q in str(r.get("code", "")).lower()
                or q in str(r.get("name", "")).lower()
            ]

        sort_key = self.sort_var.get()
        if sort_key == "氏名昇順":
            items.sort(key=lambda r: _text(r, "name"))
        elif sort_key == "時給降順":
            items.sort(key=lambda r: _norm_wage(r), reverse=True)
        else:
            items.sort(key=lambda r: _text(r, "code"))

        return items

    def _search(self):
        rows = self.repo.list_all()
        self._current_data = self._filter_sort(rows)

        self._clear_rows()
        total_wage = 0.0
        count_wage = 0

        for r in self._current_data:
            code = _text(r, "code")
            name = _text(r, "name")
            wage = _norm_wage(r)
            role = _text(r, "position") or _text(r, "role") or _text(r, "title")
            memo = _text(r, "memo")

            self._add_row(code, name, wage, role, memo)

            if wage > 0:
                total_wage += wage
                count_wage += 1

        avg = (total_wage / count_wage) if count_wage else 0.0
        self.summary.configure(
            text=f"人数: {len(self._current_data)} / 平均時給: {avg:.0f} 円（{count_wage}名の有効データ）"
        )

    # ===== CSV出力 =====
    def _export_csv(self):
        if not self._current_data:
            messagebox.showinfo("CSV", "出力対象のデータがありません。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSVファイル", "*.csv")],
            initialfile="employees_su_overview.csv",
        )
        if not path:
            return

        base = ["code", "name", "wage", "position", "memo"]
        extra = []
        for r in self._current_data:
            for k in r.keys():
                if k not in base and k not in extra:
                    extra.append(k)
        headers = base + extra

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for r in self._current_data:
                    row = []
                    for h in headers:
                        if h == "wage":
                            row.append(str(_norm_wage(r)))
                        else:
                            row.append(r.get(h, ""))
                    w.writerow(row)
            messagebox.showinfo("CSV", "CSVを書き出しました。")
        except Exception as e:
            messagebox.showerror("CSV", f"失敗しました。\n{e}")

    # ===== 時給保存 =====
    def _save_selected_wage(self):
        targets = [m for m in self._row_models if m["chk"].get()]
        if not targets:
            messagebox.showwarning("保存", "保存対象にチェックを入れてください。")
            return

        updates = []
        for m in targets:
            txt = m["wage_var"].get().strip()
            if txt == "":
                val = 0
            else:
                try:
                    val = float(txt)
                except ValueError:
                    messagebox.showwarning(
                        "入力エラー",
                        f"コード {m['code']} の時給が数値ではありません。",
                    )
                    return
            updates.append((m["code"], val))

        for code, wage in updates:
            self.repo.update_wage(code=code, wage=wage)

        messagebox.showinfo("保存", f"{len(updates)} 件を保存しました")
        self._search()
