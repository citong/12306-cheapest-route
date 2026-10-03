"""把生成的景点 PNG 压缩成网页用的小 JPEG 并按 spot-<城市>-<n>.jpg 命名。"""
import os, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(os.path.dirname(HERE), "images")

# 生成文件名特征片段 -> 目标名
MAP = {
    "Badaling_Great": "spot-beijing-2",
    "Summer_Pal":     "spot-beijing-3",
    "Yu_Garden":      "spot-shanghai-2",
    "Nanjing_Road":   "spot-shanghai-3",
    "Kuanzhai":       "spot-chengdu-2",
    "Dujiangyan":     "spot-chengdu-3",
    "Xi_an_ancient":  "spot-xian-2",
    "Giant_Wild":     "spot-xian-3",
    "Lingyin":        "spot-hangzhou-2",
    "Xixi":           "spot-hangzhou-3",
    "Ciqikou":        "spot-chongqing-2",
    "Chongqing_Yang": "spot-chongqing-3",
    "Chen_Clan":      "spot-guangzhou-2",
    "Shamian":        "spot-guangzhou-3",
    "Tianya":         "spot-sanya-2",
    "108_meter":      "spot-sanya-3",
    "Dianchi":        "spot-kunming-2",
    "Daguan":         "spot-kunming-3",
    "Xiamen_Univers": "spot-xiamen-2",
    "Xiamen_Huandao": "spot-xiamen-3",
    "Yangshuo":       "spot-guilin-2",
    "Elephant_Trunk": "spot-guilin-3",
    "Jade_Dragon":    "spot-lijiang-2",
    "Shuhe":          "spot-lijiang-3",
}
MAX = 520
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
        w, h = im.size
        im = im.crop((0, 0, w, int(h * 0.92)))   # 去底部水印
        out = os.path.join(IMG_DIR, key + ".jpg")
        im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        done[key] = os.path.getsize(out)
        os.remove(path)
    for k in sorted(done):
        print("  %-18s %6.1f KB" % (k + ".jpg", done[k] / 1024))
    print("converted %d images, total %.1f KB" % (len(done), sum(done.values()) / 1024))


if __name__ == "__main__":
    main()
