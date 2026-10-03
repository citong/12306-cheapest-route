#!/usr/bin/env python3
"""为行程攻略（trip.html）补齐热门城市的真实景点数据。
与既有 data/attractions/{北京,成都,杭州,西安}.json 同 schema：
{city, py, center:[lat,lng], days_suggest, spots:[{n,lat,lng,dur(分钟),tags,open,ticket,note}]}
坐标取景点真实经纬度（地理就近分组/排程才准）。幂等，可重复运行。"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data", "attractions")
os.makedirs(OUT, exist_ok=True)

CITIES = {
"上海": {"py":"shanghai","center":[31.23,121.47],"days_suggest":3,"spots":[
 {"n":"外滩","lat":31.240,"lng":121.490,"dur":90,"tags":["历史","免费","夜游","必去"],"open":"全天","ticket":0,"note":"万国建筑群对望陆家嘴，夜景最出片"},
 {"n":"豫园","lat":31.227,"lng":121.492,"dur":120,"tags":["历史"],"open":"08:30-17:00","ticket":40,"note":"毗邻城隍庙小吃街"},
 {"n":"东方明珠","lat":31.240,"lng":121.500,"dur":120,"tags":["必去"],"open":"08:30-21:30","ticket":199,"note":"登塔看浦东天际线"},
 {"n":"南京路步行街","lat":31.235,"lng":121.475,"dur":90,"tags":["购物","免费","夜游"],"open":"全天","ticket":0,"note":"老字号与霓虹橱窗"},
 {"n":"上海博物馆","lat":31.230,"lng":121.475,"dur":150,"tags":["历史","免费"],"open":"09:00-17:00(周一闭)","ticket":0,"note":"青铜陶瓷馆藏丰富，需预约"},
 {"n":"田子坊","lat":31.209,"lng":121.466,"dur":90,"tags":["购物","美食"],"open":"全天","ticket":0,"note":"弄堂文创与咖啡"},
 {"n":"陆家嘴环路","lat":31.235,"lng":121.505,"dur":60,"tags":["免费","夜游"],"open":"全天","ticket":0,"note":"三件套天际线摄影点"},
 {"n":"朱家角古镇","lat":31.108,"lng":121.052,"dur":180,"tags":["历史","自然"],"open":"全天","ticket":0,"note":"江南水乡，距市区约1小时"}]},
"重庆": {"py":"chongqing","center":[29.56,106.55],"days_suggest":3,"spots":[
 {"n":"洪崖洞","lat":29.562,"lng":106.578,"dur":90,"tags":["夜游","免费","必去"],"open":"全天","ticket":0,"note":"千厮门大桥回望最出片"},
 {"n":"长江索道","lat":29.558,"lng":106.585,"dur":60,"tags":["必去"],"open":"07:30-22:30","ticket":30,"note":"空中俯瞰两江四岸"},
 {"n":"解放碑","lat":29.557,"lng":106.577,"dur":60,"tags":["购物","免费"],"open":"全天","ticket":0,"note":"市中心地标商圈"},
 {"n":"磁器口古镇","lat":29.581,"lng":106.449,"dur":150,"tags":["历史","美食"],"open":"全天","ticket":0,"note":"陈麻花与川剧"},
 {"n":"李子坝轻轨站","lat":29.535,"lng":106.538,"dur":30,"tags":["免费"],"open":"全天","ticket":0,"note":"轻轨穿楼奇观"},
 {"n":"鹅岭二厂","lat":29.552,"lng":106.531,"dur":90,"tags":["购物"],"open":"全天","ticket":0,"note":"文创园区看江景"},
 {"n":"南山一棵树","lat":29.520,"lng":106.600,"dur":60,"tags":["自然","夜游"],"open":"09:00-22:30","ticket":30,"note":"看渝中半岛夜景"},
 {"n":"武隆天生三桥","lat":29.350,"lng":107.800,"dur":300,"tags":["自然","必去"],"open":"08:00-17:00","ticket":135,"note":"距市区约2.5小时，单独留一天"}]},
"广州": {"py":"guangzhou","center":[23.13,113.26],"days_suggest":3,"spots":[
 {"n":"广州塔","lat":23.106,"lng":113.324,"dur":90,"tags":["必去","夜游"],"open":"09:30-22:30","ticket":150,"note":"小蛮腰，花城广场看夜景"},
 {"n":"陈家祠","lat":23.127,"lng":113.245,"dur":90,"tags":["历史"],"open":"08:30-17:30","ticket":10,"note":"岭南建筑雕刻精华"},
 {"n":"沙面岛","lat":23.108,"lng":113.240,"dur":90,"tags":["历史","免费"],"open":"全天","ticket":0,"note":"欧陆风情租界建筑"},
 {"n":"北京路步行街","lat":23.122,"lng":113.270,"dur":90,"tags":["购物","美食","免费"],"open":"全天","ticket":0,"note":"千年古道遗址"},
 {"n":"越秀公园","lat":23.140,"lng":113.262,"dur":120,"tags":["自然","免费"],"open":"06:00-21:00","ticket":0,"note":"五羊雕像与镇海楼"},
 {"n":"上下九步行街","lat":23.116,"lng":113.248,"dur":90,"tags":["美食","购物","免费"],"open":"全天","ticket":0,"note":"骑楼老街喝早茶"},
 {"n":"珠江夜游","lat":23.110,"lng":113.290,"dur":90,"tags":["夜游"],"open":"19:00-22:00","ticket":88,"note":"船上看两岸灯火"},
 {"n":"圣心大教堂","lat":23.116,"lng":113.255,"dur":60,"tags":["历史","宗教","免费"],"open":"08:30-17:00","ticket":0,"note":"石室哥特式建筑"}]},
"三亚": {"py":"sanya","center":[18.25,109.51],"days_suggest":4,"spots":[
 {"n":"亚龙湾","lat":18.215,"lng":109.650,"dur":240,"tags":["自然","亲子","必去"],"open":"全天","ticket":0,"note":"天下第一湾，白沙碧水"},
 {"n":"天涯海角","lat":18.295,"lng":109.350,"dur":150,"tags":["自然","必去"],"open":"07:30-18:30","ticket":68,"note":"刻字巨石经典地标"},
 {"n":"南山文化旅游区","lat":18.300,"lng":109.190,"dur":240,"tags":["宗教","自然"],"open":"08:00-17:30","ticket":108,"note":"108米海上观音"},
 {"n":"蜈支洲岛","lat":18.310,"lng":109.760,"dur":300,"tags":["自然","亲子"],"open":"08:00-17:30","ticket":144,"note":"潜水胜地，单独留一天"},
 {"n":"大东海","lat":18.220,"lng":109.520,"dur":120,"tags":["自然","免费"],"open":"全天","ticket":0,"note":"市区最近的海湾"},
 {"n":"椰梦长廊","lat":18.240,"lng":109.480,"dur":90,"tags":["自然","免费"],"open":"全天","ticket":0,"note":"三亚湾日落骑行"},
 {"n":"鹿回头","lat":18.230,"lng":109.490,"dur":90,"tags":["自然","夜游"],"open":"07:30-22:00","ticket":45,"note":"俯瞰三亚全景"},
 {"n":"第一市场","lat":18.240,"lng":109.500,"dur":90,"tags":["美食"],"open":"全天","ticket":0,"note":"海鲜现买现加工"}]},
"昆明": {"py":"kunming","center":[25.04,102.71],"days_suggest":3,"spots":[
 {"n":"石林","lat":24.810,"lng":103.320,"dur":240,"tags":["自然","必去"],"open":"08:00-18:00","ticket":130,"note":"距市区约1.5小时，单独留一天"},
 {"n":"滇池海埂大坝","lat":24.980,"lng":102.660,"dur":120,"tags":["自然","免费"],"open":"全天","ticket":0,"note":"冬季喂红嘴鸥"},
 {"n":"云南民族村","lat":24.970,"lng":102.670,"dur":180,"tags":["历史","亲子"],"open":"09:00-18:00","ticket":90,"note":"26个民族风情"},
 {"n":"翠湖公园","lat":25.050,"lng":102.700,"dur":90,"tags":["自然","免费"],"open":"全天","ticket":0,"note":"城中绿肺"},
 {"n":"西山龙门","lat":24.960,"lng":102.620,"dur":180,"tags":["自然"],"open":"08:30-17:30","ticket":40,"note":"俯瞰滇池全景"},
 {"n":"大观楼","lat":24.980,"lng":102.680,"dur":90,"tags":["历史"],"open":"08:00-19:00","ticket":20,"note":"天下第一长联"},
 {"n":"金马碧鸡坊","lat":25.040,"lng":102.710,"dur":60,"tags":["历史","美食","免费"],"open":"全天","ticket":0,"note":"市中心地标夜市"},
 {"n":"官渡古镇","lat":24.950,"lng":102.750,"dur":120,"tags":["历史","美食"],"open":"全天","ticket":0,"note":"滇味小吃云集"}]},
"厦门": {"py":"xiamen","center":[24.48,118.09],"days_suggest":3,"spots":[
 {"n":"鼓浪屿","lat":24.447,"lng":118.067,"dur":300,"tags":["历史","必去"],"open":"全天","ticket":0,"note":"船票约¥35需预约，登日光岩"},
 {"n":"厦门大学","lat":24.438,"lng":118.090,"dur":150,"tags":["历史","免费"],"open":"全天(需预约)","ticket":0,"note":"芙蓉隧道涂鸦"},
 {"n":"环岛路","lat":24.430,"lng":118.130,"dur":150,"tags":["自然","免费"],"open":"全天","ticket":0,"note":"骑行观海黄金海岸"},
 {"n":"曾厝垵","lat":24.435,"lng":118.115,"dur":120,"tags":["美食","免费"],"open":"全天","ticket":0,"note":"文艺渔村小吃"},
 {"n":"南普陀寺","lat":24.442,"lng":118.087,"dur":90,"tags":["宗教","免费"],"open":"08:00-17:00","ticket":0,"note":"紧邻厦大"},
 {"n":"沙坡尾","lat":24.440,"lng":118.080,"dur":90,"tags":["美食","购物"],"open":"全天","ticket":0,"note":"避风坞文创"},
 {"n":"胡里山炮台","lat":24.428,"lng":118.100,"dur":90,"tags":["历史"],"open":"08:00-18:00","ticket":25,"note":"克虏伯大炮"},
 {"n":"集美学村","lat":24.580,"lng":118.090,"dur":150,"tags":["历史"],"open":"全天","ticket":0,"note":"嘉庚建筑与龙舟池"}]},
"桂林": {"py":"guilin","center":[25.27,110.29],"days_suggest":3,"spots":[
 {"n":"漓江竹筏(杨堤-兴坪)","lat":25.000,"lng":110.500,"dur":240,"tags":["自然","必去"],"open":"08:00-17:00","ticket":118,"note":"二十里画廊精华段"},
 {"n":"象鼻山","lat":25.270,"lng":110.290,"dur":90,"tags":["自然","必去"],"open":"07:00-18:30","ticket":55,"note":"桂林城徽"},
 {"n":"阳朔西街","lat":24.778,"lng":110.496,"dur":120,"tags":["美食","夜游","免费"],"open":"全天","ticket":0,"note":"洋人街与啤酒鱼"},
 {"n":"遇龙河漂流","lat":24.790,"lng":110.420,"dur":180,"tags":["自然"],"open":"08:00-17:00","ticket":160,"note":"人称小漓江"},
 {"n":"两江四湖","lat":25.280,"lng":110.290,"dur":90,"tags":["自然","夜游"],"open":"全天","ticket":0,"note":"环城水系夜景"},
 {"n":"龙脊梯田","lat":25.750,"lng":110.100,"dur":300,"tags":["自然"],"open":"全天","ticket":80,"note":"距市区约2小时，单独留一天"},
 {"n":"银子岩","lat":24.850,"lng":110.450,"dur":120,"tags":["自然"],"open":"08:00-17:30","ticket":65,"note":"喀斯特溶洞奇观"},
 {"n":"东西巷","lat":25.285,"lng":110.295,"dur":90,"tags":["历史","美食","免费"],"open":"全天","ticket":0,"note":"明清街巷"}]},
"丽江": {"py":"lijiang","center":[26.87,100.23],"days_suggest":4,"spots":[
 {"n":"丽江古城(大研)","lat":26.877,"lng":100.233,"dur":240,"tags":["历史","夜游","必去","免费"],"open":"全天","ticket":0,"note":"四方街与木府，夜景迷人"},
 {"n":"玉龙雪山","lat":27.100,"lng":100.180,"dur":360,"tags":["自然","必去"],"open":"07:00-16:00","ticket":100,"note":"冰川公园+蓝月谷，单独留一天"},
 {"n":"束河古镇","lat":26.920,"lng":100.200,"dur":150,"tags":["历史","免费"],"open":"全天","ticket":0,"note":"比大研更安静"},
 {"n":"黑龙潭公园","lat":26.890,"lng":100.230,"dur":90,"tags":["自然","免费"],"open":"07:00-19:00","ticket":0,"note":"拍玉龙雪山倒影"},
 {"n":"木府","lat":26.875,"lng":100.232,"dur":90,"tags":["历史"],"open":"08:30-17:30","ticket":60,"note":"纳西土司府邸"},
 {"n":"白沙古镇","lat":26.940,"lng":100.180,"dur":120,"tags":["历史","免费"],"open":"全天","ticket":0,"note":"白沙壁画"},
 {"n":"拉市海","lat":26.820,"lng":100.130,"dur":150,"tags":["自然","亲子"],"open":"08:00-18:00","ticket":30,"note":"湿地骑马划船"},
 {"n":"狮子山万古楼","lat":26.880,"lng":100.230,"dur":60,"tags":["自然"],"open":"08:00-18:30","ticket":35,"note":"俯瞰古城全景"}]},
}

def main():
    # 城市简介取自主站景点数据（attractions.json），避免两处各写一份
    attr_path = os.path.join(os.path.dirname(HERE), "attractions.json")
    intros = {}
    if os.path.exists(attr_path):
        with open(attr_path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                if v.get("intro"):
                    intros[k] = v["intro"]
                    if v.get("tip"):
                        intros[k] += " " + v["tip"]

    n=0
    for name,d in CITIES.items():
        obj={"city":name,"py":d["py"],"center":d["center"],"days_suggest":d["days_suggest"],
             "intro":intros.get(name,""),"spots":d["spots"]}
        p=os.path.join(OUT,name+".json")
        with open(p,"w",encoding="utf-8") as f:
            json.dump(obj,f,ensure_ascii=False,indent=2)
        n+=1
        print("  ✓",name,"（%d 个景点）"%len(d["spots"]))
    print("共写入 %d 个城市到 %s"%(n,OUT))

if __name__=="__main__":
    main()
