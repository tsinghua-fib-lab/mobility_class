# 其实可以根据识别出的经纬度信息来匹配到家和工作地的环境

import pickle
import sys

import matplotlib.pyplot as plt
import numpy as np
from pywolong.map import Map
from tqdm import tqdm


def arr_to_distribution(arr, min, max, bins):
        """
        convert an array to a probability distribution
        :param arr: np.array, input array
        :param min: float, minimum of converted value
        :param max: float, maximum of converted value
        :param bins: int, number of bins between min and max
        :return: np.array, output distribution array
        """
        distribution, base = np.histogram(
            arr, np.arange(
                min, max, float(
                    max - min) / bins))
        return distribution, base[:-1]

m = Map(
    mongo_uri="mongodb://sim:FiblabSim1001@mgo.db.fiblab.tech:8635/",
    mongo_db="llmsim",
    mongo_coll="map_beijing5ring_withpoi_0424",
    cache_dir="F:\Coding\cache",  # 記得指定cache的具體位置
)

# {'user_id': '5', 'home': [116.36, 39.93], 'work': [116.32, 39.945]}

f=open('../Tencent/uid2staypoi.txt')
line = f.readline().strip() #读取第一行
okids = []
for iiii in tqdm(range(8598)):
    line = f.readline().strip()  # 读取一行文件，包括换行符
    re = line.split('\t')
    id = re[0]
    id = id.strip()
    okids.append(id)
    
# print(okids)
# sys.exit(0)

f=open('../Tencent/user_hw.txt')
# line = f.readline().strip() #读取第一行

homes = []
works = []
hws = []
index = 0
hwDis = []
hwAbnormal = 0

for iiii in tqdm(range(47000)):
    line = f.readline().strip()  # 读取一行文件，包括换行符
    hwDict = eval(line)
    
    if hwDict['user_id'] in okids:  # 不是这里边的我不用
        homell = hwDict['home']
        workll = hwDict['work']
        
        try:
            homeLoc = m.lnglat2xy(homell[0], homell[1])
            workLoc = m.lnglat2xy(workll[0], workll[1])
            # print(homeLoc)
            # print(workLoc)
            dis = np.linalg.norm(np.array(homeLoc)-np.array(workLoc))
            if dis > 40000:
                # print(line)
                hwAbnormal += 1
            else:
                hwDis.append(dis)
                continue
        except:
            continue
    
    
    # try:
    #     # 现在就是要根据经纬度匹配一个最近的POI
    #     pois_home = m.query_pois(
    #         center = m.lnglat2xy(homell[0], homell[1]), 
    #         radius = 500,
    #         category_prefix= "",  
    #         limit = 5 # 500个才到3667m
    #     )  # 得到的pois是全部的信息.
    #     home = pois_home[0][0]
    #     lltuple = (home['shapely_lnglat'].xy[0][0]), (home['shapely_lnglat'].xy[1][0])
    #     home = (home['name'], home['id'], lltuple) 

    #     pois_work = m.query_pois(
    #         center = m.lnglat2xy(workll[0], workll[1]), 
    #         radius = 500,
    #         category_prefix= "",  
    #         limit = 5 # 500个才到3667m
    #     )  # 得到的pois是全部的信息.
    #     work = pois_work[0][0]
    #     lltuple = (work['shapely_lnglat'].xy[0][0]), (work['shapely_lnglat'].xy[1][0])
    #     work = (work['name'], work['id'], lltuple)

    #     homes.append(home)
    #     works.append(work)
    #     hws.append((home, work))  # 这里面都是一个个的hw对
        
    #     # index = index +1
    #     # if index % 1000 == 0:
    #     #     print(index)
    # except:
    #     # index = index +1
    #     # if index % 1000 == 0:
    #     #     print(index)
    #     pass
    
    
print("abnormal distance between HW", hwAbnormal)
print("ok distance between HW", len(hwDis))
bins = 100
d1_dist, _ = arr_to_distribution(
    hwDis, 0, 30000, bins)
values1 = d1_dist / np.sum(d1_dist)
x = np.arange(len(values1))


print(x)
print(values1)
with open('hwdis.pkl', 'wb') as f:
    pickle.dump([x[3:], values1[3:]], f)

plt.bar(x, values1, width=0.3, label='Bar 1', color='blue')
plt.savefig('hwdis.png')
sys.exit(0)


print(index)
print(len(homes))
print(len(works))
print(len(hws))

with open('homes.pkl', 'wb') as f:
    pickle.dump(homes, f)
    
with open('works.pkl', 'wb') as f:
    pickle.dump(works, f)
    
with open('hws.pkl', 'wb') as f:
    pickle.dump(hws, f)


