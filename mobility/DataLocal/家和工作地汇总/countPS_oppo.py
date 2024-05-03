# 为应用机会模型公式，计算HW附近的p和s。
# 之后会根据采集到的P和S的值,拟合公式中的指标

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

# f=open('../Tencent/uid2staypoi.txt')
# line = f.readline().strip() #读取第一行
# okids = []
# for iiii in tqdm(range(8598)):
#     line = f.readline().strip()  # 读取一行文件，包括换行符
#     re = line.split('\t')
#     id = re[0]
#     id = id.strip()
#     okids.append(id)
# with open('okids.pkl', 'wb') as f:
#     pickle.dump(okids, f)
# sys.exit(0)

file = open('okids.pkl','rb') 
okids = pickle.load(file)
file.close()
    
'''
现在规定一下基本的参数
Pi = 家附近1km以内的POI数量,看成是在家附近就业的机会
Pj = 工作地所在圆环的POI数量,看成是属于这个工作地的机会
Sij = 以家为圆心,以距离为半径,整个圆内的POI数量
'''

f=open('../Tencent/user_hw.txt')
params = []


for iiii in tqdm(range(47000)):  # 上次跑到3305
    line = f.readline().strip()  # 读取一行文件，包括换行符
    hwDict = eval(line)
    
    if hwDict['user_id'] in okids:  # 不是这里边的不用
        homell = hwDict['home']
        workll = hwDict['work']
        homeLoc = m.lnglat2xy(homell[0], homell[1])
        workLoc = m.lnglat2xy(workll[0], workll[1])
        
        # 现在就是要根据经纬度匹配一个最近的POI
        pois_home = m.query_pois(
            center = homeLoc, 
            radius = 1000,
            category_prefix= "",  
            limit = 50000   # 1000米为半径的圆内,最多能有多少个POI啊
        )  #
        Pi = len(pois_home)
        if Pi>50000:
            print('>5W!')

        dis = np.linalg.norm(np.array(homeLoc)-np.array(workLoc))
        
        poiInCircle = m.query_pois(
            center = homeLoc, 
            radius = dis,
            category_prefix= "",  
            limit = 500000
        )
        Sij = len(poiInCircle)
        if Sij>500000:
            print('>50W!')
        
        ringRadius1 = (dis//1000)*1000
        ringRadius2 = (dis//1000 + 1)*1000
        poiRing1 = m.query_pois(
            center = homeLoc, 
            radius = ringRadius1,
            category_prefix= "",  
            limit = 500000
        )
        poiRing2 = m.query_pois(
            center = homeLoc, 
            radius = ringRadius2,
            category_prefix= "",  
            limit = 500000
        )
        Pj = len(poiRing2)-len(poiRing1)
        
        # print('\n')
        # print(Pi)
        # print(Pj)
        # print(Sij)   
        # index = index +1
        # if index % 1000 == 0:
        #     print(index)
        params.append((Pi, Pj, Sij))
    
    if iiii%20 == 0 and iiii>0:
        with open('params.pkl', 'wb') as fff:
            pickle.dump(params, fff)
        fff.close()
        print(iiii)


with open('params.pkl', 'wb') as f:
    pickle.dump(params, f)




