# app/gui/screens/employee_su_overview_screen.py
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Dict
import csv

from app.infra.db.employee_repo import EmployeeRepo


def _norm_wage(emp: Dict) -> float:
    """ wage / hourly_wage / hourlyRate / hourly のどれかを数値にして返す（なければ 0.0） """
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
    """
    su専用：従業員の一覧（氏名／コード／時給／役職／備考）
      - 検索（コード/氏名）
      - 並び替え（コード↑ / 氏名↑ / 時給↓）
      - CSV出力
      - ★ 時給をセル編集 → チェック行だけ一括保存
    """
    def __init__(self, master):
        super().__init__(master)
        self.repo = EmployeeRepo()

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ===== タイトル =====
        ctk.CTkLabel(self, text="👥 従業員一覧（su・時給編集可）", font=("Meiryo UI", 18, "bold"))\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        # ===== 条件エリア =====
        cond = ctk.CTkFrame(self)
        cond.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        for i in range(12):
            cond.grid_columnconfigure(i, weight=0)
        cond.grid_columnconfigure(11, weight=1)

        # 検索
        ctk.CTkLabel(cond, text="検索（コード/氏名）:").grid(row=0, column=0, padx=(8,4), pady=8, sticky="w")
        self.q_var = ctk.StringVar(value="")
        ctk.CTkEntry(cond, width=220, textvariable=self.q_var, placeholder_text="例）E0001 / 山田")\
            .grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # 並び替え
        ctk.CTkLabel(cond, text="並び:").grid(row=0, column=2, padx=(16,4), pady=8, sticky="w")
        self.sort_values = ["コード昇順", "氏名昇順", "時給降順"]
        self.sort_var = ctk.StringVar(value=self.sort_values[0])
        ctk.CTkOptionMenu(cond, values=self.sort_values, variable=self.sort_var, width=130)\
            .grid(row=0, column=3, padx=4, pady=8, sticky="w")

        # 操作
        ctk.CTkButton(cond, text="検索", width=90, command=self._search).grid(row=0, column=4, padx=(12,4))
        ctk.CTkButton(cond, text="CSV出力", width=90, command=self._export_csv).grid(row=0, column=5, padx=4)

        # ===== 一覧（カード風＋ゼブラ） =====
        body = ctk.CTkFrame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 10))
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # ヘッダ（チェック列＋IDは非表示、時給は編集列）
        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew")
        titles = ["", "コード", "氏名", "時給(円)", "役職/属性", "備考"]
        for i, t in enumerate(titles):
            ctk.CTkLabel(head, text=t, anchor="w", font=("Meiryo UI", 13, "bold"))\
                .grid(row=0, column=i, padx=10, pady=(10, 8), sticky="w")
            head.grid_columnconfigure(i, weight=1 if i in (1,2,4,5) else 0)

        # 区切り線
        ctk.CTkFrame(body, height=1, fg_color="#D0D0D0").grid(row=0, column=0, sticky="ew", pady=(42, 6))

        # スクロール
        self.scroll = ctk.CTkScrollableFrame(body, height=440, fg_color="#ECEFF1")
        self.scroll.grid(row=1, column=0, sticky="nsew")

        # 下部操作（選択保存）
        ops = ctk.CTkFrame(self)
        ops.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        ctk.CTkButton(ops, text="✅ 選択行の時給を保存", command=self._save_selected_wage)\
            .pack(side="left", padx=6, pady=6)

        # サマリ
        self.summary = ctk.CTkLabel(self, text="—", anchor="w")
        self.summary.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        # データ保持
        self._rows_widgets = []
        self._row_count = 0
        self._current_data: List[Dict] = []

        # 初期表示
        self._search()

    # ===== 内部 util =====
    def _clear_rows(self):
        for w in self._rows_widgets:
            try: w.destroy()
            except: pass
        self._rows_widgets.clear()
        self._row_count = 0

    def _add_row(self, code: str, name: str, wage_val: float, role_text: str, memo: str):
        idx = self._row_count
        inner_bg = "#FAFAFA" if (idx % 2 == 0) else "#FFFFFF"

        # 外枠カード
        card = ctk.CTkFrame(self.scroll, corner_radius=10, border_width=2,
                            border_color="#B8C1CC", fg_color="#FFFFFF")
        card.grid(row=idx, column=0, sticky="ew", padx=10, pady=6)
        for i in (1,2,4,5):
            card.grid_columnconfigure(i, weight=1)

        # 内側（ゼブラ）
        inner = ctk.CTkFrame(card, fg_color=inner_bg, corner_radius=8)
        inner.grid(row=0, column=0, columnspan=6, sticky="ew", padx=6, pady=6)
        for i in (1,2,4,5):
            inner.grid_columnconfigure(i, weight=1)

        # チェック
        chk = ctk.CTkCheckBox(inner, text="")
        chk.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        # コード・氏名
        lab_code = ctk.CTkLabel(inner, text=code, anchor="w")
        lab_code.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        lab_name = ctk.CTkLabel(inner, text=name, anchor="w")
        lab_name.grid(row=0, column=2, padx=10, pady=8, sticky="w")

        # ★ 時給（編集可）
        wage_var = ctk.StringVar(value=str(int(wage_val)) if wage_val else "")
        ent_wage = ctk.CTkEntry(inner, width=100, textvariable=wage_var, placeholder_text="0")
        ent_wage.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        # 役職/備考（表示のみ）
        lab_role = ctk.CTkLabel(inner, text=role_text, anchor="w")
        lab_role.grid(row=0, column=4, padx=10, pady=8, sticky="w")
        lab_memo = ctk.CTkLabel(inner, text=memo, anchor="w")
        lab_memo.grid(row=0, column=5, padx=10, pady=8, sticky="w")

        self._rows_widgets += [card, inner, chk, lab_code, lab_name, ent_wage, lab_role, lab_memo]
        # 行の保持（保存対象を取り出す用）
        if not hasattr(self, "_row_models"):
            self._row_models = []
        self._row_models.append({
            "chk": chk,
            "code": code,
            "wage_var": wage_var
        })
        self._row_count += 1

    def _filter_sort(self, items: List[Dict]) -> List[Dict]:
        q = self.q_var.get().strip().lower()
        if q:
            items = [r for r in items
                     if q in str(r.get("code","")).lower()
                     or q in str(r.get("name","")).lower()]
        sort_key = self.sort_var.get()
        if sort_key == "氏名昇順":
            items.sort(key=lambda r: _text(r, "name"))
        elif sort_key == "時給降順":
            items.sort(key=lambda r: _norm_wage(r), reverse=True)
        else:
            items.sort(key=lambda r: _text(r, "code"))
        return items

    # ===== アクション =====
    def _search(self):
        rows = self.repo.list_all()  # [{code,name, ... wage? ...}]
        self._current_data = self._filter_sort(rows)

        self._clear_rows()
        self._row_models = []
        total_wage, count_wage = 0.0, 0

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
            text=f"人数: {len(self._current_data)}  /  平均時給: {avg:.0f} 円（{count_wage}名の有効データ）"
        )

    def _export_csv(self):
        if not self._current_data:
            messagebox.showinfo("CSV", "出力対象のデータがありません。")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSVファイル","*.csv")],
            initialfile="employees_su_overview.csv"
        )
        if not path:
            return

        base = ["code","name","wage","hourly_wage","hourlyRate","hourly","position","role","memo","phone","sex"]
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
            messagebox.showerror("CSV", f"書き出しに失敗しました。\n{e}")

    def _save_selected_wage(self):
        """チェックの入った行だけ時給を保存。数値バリデーション付き。"""
        if not hasattr(self, "_row_models") or not self._row_models:
            return
        targets = [m for m in self._row_models if m["chk"].get()]
        if not targets:
            messagebox.showwarning("保存", "保存対象の行にチェックを入れてください。")
            return

        updates = []
        for m in targets:
            txt = m["wage_var"].get().strip()
            if txt == "":
                # 空入力は 0 として扱う（お好みでスキップに変更可）
                val = 0.0
            else:
                try:
                    val = float(txt)
                except ValueError:
                    messagebox.showwarning("入力エラー", f"コード {m['code']} の時給が数値ではありません。")
                    return
                if val < 0:
                    messagebox.showwarning("入力エラー", f"コード {m['code']} の時給が負の値です。")
                    return
            updates.append((m["code"], val))

        # DBへ反映
        try:
            for code, wage in updates:
                # EmployeeRepo に update_wage がある前提。
                # 無ければ下の「# 2) EmployeeRepo への追記」を入れてください。
                self.repo.update_wage(code=code, wage=wage)
            messagebox.showinfo("保存", f"{len(updates)} 件の時給を保存しました。")
            self._search()
        except Exception as e:
            messagebox.showerror("保存失敗", f"更新に失敗しました。\n{e}")
