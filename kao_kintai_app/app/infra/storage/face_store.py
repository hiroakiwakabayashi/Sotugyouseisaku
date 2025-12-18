from pathlib import Path
from datetime import datetime
import cv2
import sys  # ← 追加


def _app_root() -> Path:
    # exe化（PyInstaller）時は exe のあるフォルダを基準にする（書き込み可能）
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # 開発時はプロジェクトルート（…/kao_kintai_app）を基準
    return Path(__file__).resolve().parents[3]


class FaceStore:
    def __init__(self):
        self.root = _app_root() / "data" / "faces"
        self.root.mkdir(parents=True, exist_ok=True)

    def dir_for(self, employee_code: str) -> Path:
        d = self.root / employee_code
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_image(self, employee_code: str, img_bgr) -> Path:
        d = self.dir_for(employee_code)
        fn = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".jpg"
        p = d / fn
        cv2.imwrite(str(p), img_bgr)
        return p
