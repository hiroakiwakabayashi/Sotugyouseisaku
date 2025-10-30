from __future__ import annotations
import json
from pathlib import Path
import sys
from typing import Dict, Any

DEFAULT_CFG: Dict[str, Any] = {
    "app_name": "Kao-Kintai (Skeleton)",
    "vision": {
        "min_area_ratio": 0.12,   # 顔面積/フレーム
        "min_blur_var": 100.0,    # ぼけ(Laplacian)
        "bright_min": 60,         # 明るさ下限
        "bright_max": 190,        # 明るさ上限
        "match_threshold": 24,    # ORBマッチ数
        "top_k_images": 5,        # 学習に使う登録画像数
        "recog_interval": 3       # 認識間引き(フレーム)
    }
}

def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]

class ConfigService:
    def __init__(self):
        self.root = _project_root()
        self.cfg_path = self.root / "config" / "app_config.json"
        self.cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.cfg_path.exists():
            self._write(DEFAULT_CFG)

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_CFG.copy()

    def _write(self, data: Dict[str, Any]) -> None:
        self.cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- public ----
    def load(self) -> Dict[str, Any]:
        cfg = self._read()
        # デフォルトとマージ（不足キーを補う）
        merged = DEFAULT_CFG.copy()
        merged.update(cfg)
        merged["vision"] = {**DEFAULT_CFG["vision"], **cfg.get("vision", {})}
        return merged

    def save_vision(self, vision: Dict[str, Any]) -> None:
        cfg = self.load()
        cfg["vision"].update(vision)
        self._write(cfg)

    def get_vision(self) -> Dict[str, Any]:
        return self.load()["vision"]
    
    def get_app_name(self) -> str:
        cfg = self.load()
        return cfg.get("app_name", "Kao-Kintai 勤怠")

