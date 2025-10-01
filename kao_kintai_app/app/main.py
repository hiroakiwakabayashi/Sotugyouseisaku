import sys, pathlib, json
from pathlib import Path

# --- 直実行でも -m 実行でも通るようにパス調整 ---
if __package__ is None or __package__ == "":
    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from app.gui.app_shell import run_app

def load_config():
    # app/main.py → [..]/kao_kintai_app がルート
    project_root = Path(__file__).resolve().parents[1]
    cfg_path = project_root / "config" / "app_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if not cfg_path.exists():
        # 最小のデフォルト設定を自動生成
        default = {"app_name": "Kao-Kintai (Skeleton)"}
        cfg_path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")

    return json.loads(cfg_path.read_text(encoding="utf-8"))

def main():
    cfg = load_config()
    run_app(cfg)

if __name__ == "__main__":
    main()
