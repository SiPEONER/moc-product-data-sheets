"""Sharpen low-res product photos (under 900 px tall) with a 4x super-resolution model.

    python3 tools/upscale.py            # every photo under 900 px
    python3 tools/upscale.py 0429 0106  # just these

A stopgap until the 3D renders: edges and large type come back crisp, small label
text stays unreadable (it was never in the source). Each product file records
"photo": {"upscaled": "EDSR x4"} so these are easy to find and replace later.
Model: EDSR x4 (Saafke/EDSR_Tensorflow), downloaded to ~/.cache on first run.
"""
import json, pathlib, sys, urllib.request
import cv2, numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from photos import clean, SHARP

MODEL = pathlib.Path.home() / ".cache" / "moc-pds" / "EDSR_x4.pb"
URL = "https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x4.pb"


def main(only):
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URL, MODEL)
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(str(MODEL)); sr.setModel("edsr", 4)
    for f in sorted((ROOT / "products").glob("*.json")):
        p = json.loads(f.read_text())
        if not p.get("image") or (only and p["item"] not in only) or p.get("photo", {}).get("upscaled"):
            continue
        path = ROOT / p["image"]
        a = np.array(Image.open(path).convert("RGBA"))
        if a.shape[0] >= SHARP:
            continue
        up = sr.upsample(cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2BGR))
        alpha = cv2.resize(a[:, :, 3], (up.shape[1], up.shape[0]), interpolation=cv2.INTER_CUBIC)
        Image.fromarray(np.dstack([cv2.cvtColor(up, cv2.COLOR_BGR2RGB), alpha])).save(path)
        w, h = clean(path, path)
        p.setdefault("photo", {}).update(upscaled="EDSR x4", px=h)
        f.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n")
        print(f"{p['item']:>7}  {a.shape[0]} -> {h}px", flush=True)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
