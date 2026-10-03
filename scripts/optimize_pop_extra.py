"""把第二批 40 张随机城市横幅 PNG 压缩并命名为 pop-<拼音>.jpg（不覆盖已有 12 张）。"""
import os, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(os.path.dirname(HERE), "images")

MAP = {
 "Tianjin_Eye":"tianjin","Mukden_Palace":"shenyang","Dalian_Xinghai":"dalian",
 "Jingyuetan":"changchun","Saint_Sophia":"haerbin","Confucius_Temple":"nanjing",
 "Humble_Administrator":"suzhou","Turtle_Head_Isle":"wuxi","Ningbo_Old_Bund":"ningbo",
 "Three_Lanes":"fuzhou","Baotu_Spring":"jinan","Zhanqiao_Pier":"qingdao",
 "Penglai_Pavilion":"yantai","Weihai_coastal":"weihai","Shaolin_Temple":"zhengzhou",
 "Longmen_Grottoes":"luoyang","Kaifeng_Millennium":"kaifeng","Yellow_Crane":"wuhan",
 "Orange_Isle":"changsha","Shenzhen_skyline":"shenzhen","Zhuhai_Fisher":"zhuhai",
 "Haikou_Qilou":"haikou","Leshan_Giant":"leshan","Dali_Erhai":"dali",
 "Xishuangbanna":"xishuangbanna","Potala_Palace":"lasa","Yanan_Pagoda":"yanan",
 "Lanzhou_Zhongshan":"lanzhou","Qinghai_Lake":"xining","Heavenly_Lake":"wulumuqi",
 "Chengde_Mountain":"chengde","Shanhaiguan":"qinhuangdao","Mount_Taishan":"taian",
 "Slender_West_Lake":"yangzhou","Quanzhou_Kaiyuan":"quanzhou","Yandang_Mountain":"wenzhou",
 "Huangshan_Yellow":"huangshan","Zhangjiajie":"zhangjiajie","Jingdezhen":"jingdezhen",
 "Pingtan_island":"pingtan",
}
MAX = 480
QUALITY = 68


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
        im = im.crop((0, 0, w, int(h * 0.92)))
        out = os.path.join(IMG_DIR, "pop-%s.jpg" % key)
        im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        done[key] = os.path.getsize(out)
        os.remove(path)
    print("converted %d, total %.1f KB" % (len(done), sum(done.values()) / 1024))
    missing = [v for v in MAP.values() if v not in done]
    if missing:
        print("MISSING:", missing)


if __name__ == "__main__":
    main()
