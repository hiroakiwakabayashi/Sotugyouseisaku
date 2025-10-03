# app/main.py
import sys
import json
from pathlib import Path

# --- 直実行でも -m 実行でもインポートが通るようにパス調整 ---
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.gui.app_shell import run_app

DEFAULT_CONFIG = {
    "app_name": "Kao-Kintai (Skeleton)"
}

def _project_root() -> Path:
    """
    開発時: リポジトリのルート
    exe化後(PyInstaller): 実行ファイルのあるディレクトリ
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def load_config() -> dict:
    root = _project_root()
    cfg_path = root / "config" / "app_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if not cfg_path.exists():
        cfg_path.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        # 破損していた場合はデフォルトで起動
        return DEFAULT_CONFIG.copy()

def main() -> None:
    cfg = load_config()
    run_app(cfg)

if __name__ == "__main__":
    main()
