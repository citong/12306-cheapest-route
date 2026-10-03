"""把生成的 1024x1024 PNG 压缩成网页用的小 JPEG，并统一命名。"""
import os, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(os.path.dirname(HERE), "images")

# 文件名特征片段 -> 目标拼音名
MAP = {
    "the_Forb": "beijing",
    "the_Bund": "shanghai",
    "a_giant":  "chengdu",
    "the_Terr": "xian",
    "West_Lak": "hangzhou",
    "Hongyado": "chongqing",
    "Canton_T": "guangzhou",
    "a_tropic": "sanya",
    "the_Ston": "kunming",
    "Gulangyu": "xiamen",
    "the_Li_R": "guilin",
    "Lijiang_": "lijiang",
}
MAX = 640          # 卡片实际显示很小，640 足够
QUALITY = 82


def main():
    done = {}
    for path in glob.glob(os.path.join(IMG_DIR, "*.png")):
        base = os.path.basename(path)
        key = next((v for k, v in MAP.items() if k in base), None)
        if not key:
            print("skip (unmapped):", base)
            continue
        im = Image.open(path).convert("RGB")
        im.thumbnail((MAX, MAX), Image.LANCZOS)
        out = os.path.join(IMG_DIR, "pop-%s.jpg" % key)
        im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        done[key] = os.path.getsize(out)
        os.remove(path)
    for k in sorted(done):
        print("  pop-%-11s %6.1f KB" % (k + ".jpg", done[k] / 1024))
    total = sum(done.values())
    print("converted %d images, total %.1f KB" % (len(done), total / 1024))


if __name__ == "__main__":
    main()
