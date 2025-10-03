from pathlib import Path
from datetime import datetime
import cv2

class FaceStore:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[3] / "data" / "faces"
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
