import pickle
import sys

import matplotlib.pyplot as plt

file = open('profileRankWord.pkl', 'rb')
data = pickle.load(file)  # 经过检验总数确实是10W人

# Bachelor's degree-man-slightly high-Teacher

"""统计职业分布"""
# occupationDict = {}
# for item in data:
#     plist = item[0].split('-')
#     occu = plist[-1]
#     if occu in occupationDict.keys():
#         occupationDict[occu] += item[1]
#     else:
#         occupationDict[occu] = item[1]

# plt.figure(figsize=(10, 12))
# plt.title("occupation list")
# plt.bar(occupationDict.keys(), occupationDict.values())
# plt.xticks(rotation = 90)
# plt.savefig('occupation.png')
# sys.exit(0)

"""统计性别分布"""
genderDict = {}
for item in data:
    plist = item[0].split('-')
    occu = plist[1]
    if occu in genderDict.keys():
        genderDict[occu] += item[1]
    else:
        genderDict[occu] = item[1]

plt.figure(figsize=(8, 6))
plt.title("gender list")
plt.bar(genderDict.keys(), genderDict.values())
plt.xticks(rotation = 90)
plt.savefig('gender.png')
sys.exit(0)

    
# print(len(data))
# print(data[400])
# topk = 40
# data = data[:topk]

# # xlist = [item[0] for item in data]
# xlist = list(range(topk))
# ylist = [item[1] for item in data]

# plt.title("all profiles")
# plt.bar(xlist, ylist)
# plt.savefig('profiles.png')


