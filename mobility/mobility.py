import asyncio
import pickle
import random
import sys
import time

import pycityagent
import yaml
from pycityagent.ac.action import *
from pycityagent.ac.hub_actions import *
from pycityagent.ac.sim_actions import *
from pycityagent.brain.memory import (LTMemory, MemoryPersistence,
                                      MemoryReason, MemoryRetrive)
from pycityagent.urbanllm import LLMConfig, UrbanLLM
from pycityagent import GroupAgent

from utils import *

async def intention_query(wk):
    
    wk.Reason['intentIndex'] += 1
    
    soul = wk._agent.Soul 
    history = wk.Reason['history']
    globalInfo = wk.Reason['globalInfo']
    nowTime = wk.Reason['nowTime']
    
    Q = [{"role": "user", "content": wk.Reason['intent_question']}]
    nowQ = globalInfo + Q
    
    # 下面开始问时间
    genOK = False
    try_count = 10
    if wk.Reason['show_prompts']:
        print(f"Q1: {nowQ}")
    while not genOK:
        try:
            answer = await soul.atext_request(nowQ)
            answer = eval(answer)
            reason = answer[1]
            answer = answer[0]
            if answer in ["go to work", "go home", "eat", "do shopping", "do sports", "excursion", "leisure or entertainment", "go to sleep", "medical treatment", "handle the trivialities of life", "banking and financial services", "cultural institutions and events"]: 
                genOK = True
        except:
            try_count -= 1
            if try_count < 0:
                raise Exception("Error when using LLM")
        
    wk.Reason['intention_ask'] = answer
    
    nowQ = nowQ + [{"role": "assistant", "content": answer}]
    Q2 = [{"role": "user", "content": wk.Reason['time_question']}]
    nowQ = nowQ + Q2

    genOK = False
    try_count = 10
    if wk.Reason['show_prompts']:
        print(f"Q2: {nowQ}")
    while not genOK:
        try:
            increment_minutes = await soul.atext_request(nowQ)
            increment_minutes = eval(increment_minutes)
            minutes = int(increment_minutes[0])
            seconds = int(increment_minutes[1])
            genOK = True
        except:
            try_count -= 1
            if try_count < 0:
                raise Exception("Error when using LLM")
    increment_minutes = 60*minutes+seconds
    noiseTime = sampleNoiseTime()
    if increment_minutes + noiseTime > 0:  # 防止变成负数
        increment_minutes = increment_minutes + noiseTime  # 转化成分钟数量
    
    end_time, cross_day = add_time(nowTime, increment_minutes)
    
    # 一旦时间跨天就提前终止生成过程,说明生成满1天
    if cross_day or end_time == "23:59":
        seTime = "("+ nowTime+", 23:59)"
        history.append([answer, seTime])
        wk.Reason['break'] = True
    else:
        seTime = "("+ nowTime+", "+end_time+")"
        history.append([answer, seTime])
        
        # print(history)
        gapTime = sampleGapTime()
        tmpnowTime, cross_day = add_time(end_time, gapTime)  
        if cross_day:
            nowTime = end_time
        else:
            nowTime = tmpnowTime
        wk.Reason['break'] = False
    
    wk.Reason['nowTime'] = nowTime  # 及时更新当前时间
    print([answer, seTime])
    return history


async def intent2position(wk):
    # 将intent对应到位置
    trajectory = wk.Reason['trajectory']
    print('before query-nowPlace: {}'.format(wk.Reason['nowPlace']))
    
    nextIntention = wk.Reason['intention_ask']
    nextIntention = nextIntention.lower()
    
    if nextIntention == 'go to work':
        nextPlace = wk.Reason['Workplace']
        
    elif nextIntention == 'go home':
        nextPlace = wk.Reason['Homeplace']
        
    elif nextIntention == 'go to sleep':
        nextPlace = wk.Reason['Homeplace']
    
    # 根据数据自动判断是否有二级分类
    elif nextIntention in ['eat', 'have breakfast', 'have lunch', 'have dinner', 'do shopping', 'do sports', 'excursion', 'leisure or entertainment', 'medical treatment', 'handle the trivialities of life', 'banking and financial services', 'government and political services', 'cultural institutions and events']: 
        eventId = getDirectEventID(nextIntention)
        POIs = event2poi_gravity(wk._agent._simulator.map, eventId, wk.Reason['nowPlace']) 
        options = list(range(len(POIs)))
        probabilities = [item[2] for item in POIs]
        sample = np.random.choice(options, size=1, p=probabilities)  # 根据计算出来的概率值进行采样
        nextPlace = POIs[sample[0]]
        nextPlace = (nextPlace[0], nextPlace[1])
    
    intent, setime = wk.Reason['history'][-1]
    thisThing = [intent, setime, nextPlace]
    trajectory.append(thisThing)
    wk.Reason['nowPlace'] = nextPlace
    
    print('after query-nowPlace: {}\n'.format(wk.Reason['nowPlace']))
    
    return trajectory


async def get_position(wk):
    sence = wk.sence
    positions = sence['positions']
    longlat = positions[0]['longlat']
    return [longlat[0], longlat[1]]

class MobilityAgent:
    def __init__(self, config_file_path:str, agent_id:int, agent_name:str) -> None:
        with open(config_file_path, 'r') as file:
            self.config = yaml.safe_load(file)
        print("---构建模拟器对象")
        self.sim = pycityagent.Simulator(self.config['citysim_request'])
        print("---构建LLM代理")
        self.llm_config = LLMConfig(self.config['llm_request'])
        self.soul = UrbanLLM(self.llm_config)
        self.reasons = []
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent = None
        self.reasons.append(MemoryReason("history", intention_query, "stage1: 出行意图生成"))
        self.reasons.append(MemoryReason("trajectory", intent2position, "stage2: 出行目标位置生成——轨迹生成"))

        profileIds, profiles, personNum, genIdList, loopStart, loopEnd = setIO(modeChoice='labeld',  keyid = 0)
        index = random.randint(0, 50)
        personBasicInfo = profiles[index]
        self.personal_info = personBasicInfo
        education, gender, consumption, occupation = personBasicInfo.split('-')
        self.genderDescription = "" if gender == 'uncertain' else "Gender: {}; ".format(gender)
        self.educationDescription = "" if education == 'uncertain' else "Education: {}; ".format(education)
        self.consumptionDescription = "" if consumption == 'uncertain' else "Consumption level: {}; ".format(consumption)
        self.occupationDescription = "" if occupation == 'uncertain' else "Occupation or Job Content: {};".format(occupation)
        
        # * prompt
        # personDescription
        self.person_des_prompt = {
            'f_string': """You are a person and your basic information is as follows:
{}{}{}{}""",
            'vars': ['genderDescription', 'educationDescription', 'consumptionDescription', 'occupationDescription']
        }

        # day
        self.day_prompt = {}
        self.day_prompt['weekend'] = {
            'f_string': "{}. It is important to note that people generally do not work on weekends and prefer entertainment, sports and leisure activities. There will also be more freedom in the allocation of time.",
            'vars': ['day']
        }
        self.day_prompt['workday'] = {
            'f_string': "{}",
            'vars': ['day']
        }

        # system
        self.system_prompt = {
            'f_string': """{}

Now I want you to generate your own schedule for today.(today is {}).
The specific requirements of the task are as follows:
1. You need to consider how your character attributes relate to your behavior.
2. I want to limit your total number of events in a day to {}. I hope you can make every decision based on this limit.
3. I want you to answer the reasons for each event.

Note that: 
1. All times are in 24-hour format.
2. The generated schedule must start at 0:00 and end at 24:00. Don't let your schedule spill over into the next day.
3. Must remember that events can only be choosed from [go to work, go home, eat, do shopping, do sports, excursion, leisure or entertainment, go to sleep, medical treatment, handle the trivialities of life, banking and financial services, cultural institutions and events].
4. I'll ask you step by step what to do, and you just have to decide what to do next each time.

Here are some examples for reference. For each example I will give a portrait of the corresponding character and the reasons for each arrangement.

Example 1:
This is the schedule of a day for a coder who works at an Internet company.
[
["go to sleep", "(00:00, 11:11)"], (Reason: Sleep is the first thing every day.)
["go to work", "(12:08, 12:24)"], (Reason: Work for a while after sleep. This person's working hours are relatively free, there is no fixed start and finish time.) 
["eat", "(12:35, 13:01)"], (Reason: It's noon after work. Go get something to eat.)
["go to work", "(13:15, 20:07)"],   (Reason: After lunch, the afternoon and evening are the main working hours. And he works so little in the morning that he need to work more in the afternoon and evening. So this period of work can be very long.)
["go to sleep", "(21:03, 23:59)"]  (Reason: It was already 9pm when he got off work, and it is time to go home and rest.)
]

Example 2:
This is the schedule of a day for a salesperson at a shopping mall.
[
["go to sleep", "(00:00, 08:25)"], (Reason: Of course the first thing of the day is to go to bed.)
["go to work", "(09:01, 19:18)"], (Reason: Generally, the business hours of shopping malls are from 9 am to 7 pm, so she works in the mall during this time and will not go anywhere else.)
["go home", "(20:54, 23:59)"], (Reason: It's almost 9pm after getting off work. Just go home and rest at home.)
]

Example 3:
This is the schedule of a day for a manager who is about to retire.
[
["go to sleep", "(00:00, 06:04)"], (Reason: He is used to getting up early, so he got up around 6 o'clock in the morning.)
["eat", "(08:11, 10:28)"], (Reason: He has the habit of having morning tea after getting up and enjoys the time of slowly enjoying delicious food in the morning.)
["go home", "(12:26, 13:06)"], (Reason: After breakfast outside, take a walk for a while, and then go home at noon.)
["excursion", "(13:34, 13:53)"], (Reason: He stays at home most of the morning, so he decides to go out for a while in the afternoon.)
["go to work", "(14:46, 16:19)"], (Reason: Although life is already relatively leisurely, he still has work to do, so he has to go to the company to work for a while in the afternoon.)
]

Example 4:
This is the schedule of a day for a lawyer who suffers a medical emergency in the morning.
[
["go to sleep", "(00:00, 09:36)"], (Reason: Sleep until 9:30 in the morning. Lawyers' working hours are generally around 10 o'clock.)
["medical treatment", "(11:44, 12:03)"], (Reason: He suddenly felt unwell at noon, so he went to the hospital for treatment.)
["go to work", "(12:27, 14:56)"], (Reason: After seeing the doctor, the doctor said there was nothing serious, so he continued to return to the company to work for a while.)
["go to sleep", "(17:05, 23:59)"], (Reason: Since he was not feeling well, he got off work relatively early and went home to rest at 5 p.m.)
]

Example 5:
This is an architect's schedule on a Sunday.
[
["go to sleep", "(00:00, 06:20)"], (Reason: The first thing is of course to sleep.)
["handle the trivialities of life", "(07:18, 07:32)"], (Reason: After getting up, he first dealt with the trivial matters in life that had not been resolved during the week.)
["leisure or entertainment", "(07:38, 17:27)"], (Reason: Since today was Sunday, he didn't have to work, so he decided to go out and have fun.)
["handle the trivialities of life", "(18:22, 19:11)"], (Reason: After coming back in the evening, he would take care of some chores again.)
 ["go to sleep", "(20:51, 23:59)"] (Reason: Since tomorrow is Monday, go to bed early to better prepare for the new week.)
]

Example 6:
This is the schedule of a day for a customer service specialist.
[
[go to work, (9:21, 16:56)], (Reason: Work dominated the day and was the main event of the day.)
[go home, (20:00, 23:59)], (Reason: After a day's work and some proper relaxation, he finally got home at 8 o 'clock.)
]

Example 7:
This is the schedule of a day for a wedding event planner.
[
[go to work, (11:21, 20:56)], (Reason: As a wedding planner, her main working hours are from noon to evening.)
[go home, (23:10, 23:30)], (Reason: After finishing the evening's work, she went home to rest.)
[handle the trivialities of life, (23:30, 23:59)], (Reason: Before she goes to bed, she takes care of the trivial things in her life.)
]

Example 8:
This is the schedule of a day for a high school teacher in Saturday.
[
[eat, (06:11, 7:28)], (Reason: He has a good habit: have breakfast first after getting up in the morning.)
[handle the trivialities of life, (07:48, 08:32)],  (Reason: After breakfast, he usually goes out to deal with some life matters.)
[go home, (9:00, 11:00)], (Reason: After finishing all the things, go home.)
[medical treatment, (13:44, 17:03)], (Reason: Today is Saturday and he doesn't have to work, so he decides to go to the hospital to check on his body and some recent ailments.)
[go home, (19:00, 23:59)], (Reason: After seeing the doctor in the afternoon, he goes home in the evening.)
]

As shown in the example, a day's planning always starts with "go to sleep" and ends with "go to sleep" or "go home".
""",
            'vars': ['personDescription', 'dayDescription', 'intentTotal']
        }

        # intention generation
        self.intention_prompt = {}
        self.intention_prompt['last'] = {
            'f_string': "The arrangement of the previous {} things is as follows: {}. What's the last arrangement today? Please output the event name and explain your thought process or reasons for your choice. Answer format:[\"event name\", \"reasons\"]",
            'vars': ['intentIndex', 'history']
        }
        self.intention_prompt['first'] = {
            'f_string': "What's the first arrangement today? Please output the event name and explain your thought process or reasons for your choice. Answer format:[\"event name\", \"reasons\"]",
            'vars': []
        }
        self.intention_prompt['normal'] = {
            'f_string': "The arrangement of the previous {} things is as follows: {}. What's the next arrangement today? Please output the event name and explain your thought process or reasons for your choice. Answer format:[\"event name\", \"reasons\"]",
            'vars': ['intentIndex', 'history']
        }
        self.intention_result_set = {
            'format': "[\"event name\", \"reasons\"]",
            'answer_set': ["go to work", "go home", "eat", "do shopping", "do sports", "excursion", "leisure or entertainment", "go to sleep", "medical treatment", "handle the trivialities of life", "banking and financial services", "cultural institutions and events"]
        }

        # time generation
        self.time_prompt = {
            'f_string': """How long will you spend on this arrangement?
You must consider some fragmented time, such as 3 hours plus 47 minute, and 7 hours and 13 minutes.
Please answer as a list: [x,y]. Which means x hours and y minutes.""",
            'vars': []
        }

        print("完成")

    def print_prompts(self):
        print("Prompts:")
        print ("1. System prompt:")
        print(f"""f_string: {self.system_prompt['f_string']},
variables: {self.system_prompt['vars']},
function: 用于为LLM提供system role的描述
""")
        print("2. Person description prompt: ")
        print(f"""f_string: {self.person_des_prompt['f_string']},
variables: {self.person_des_prompt['vars']},
function: 用于生成个人描述信息
""")
        
        print("3. Day description prompt: ")
        print("3.1 Weekend")
        print(f"""f_string: {self.day_prompt['weekend']['f_string']},
variables: {self.day_prompt['weekend']['vars']},
function: 用于描述周日
""")
        print("3.2 Workday")
        print(f"""f_string: {self.day_prompt['workday']['f_string']},
variables: {self.day_prompt['workday']['vars']},
function: 用于描述工作日
""")
        
        print("4. Intention genration prompt:")
        print("4.1 First Intention:")
        print(f"""f_string: {self.intention_prompt['first']['f_string']},
variables: {self.intention_prompt['first']['vars']},
function: 用于生成一天中的第一个intention
""")
        print("4.2 Last Intention:")
        print(f"""f_string: {self.intention_prompt['last']['f_string']},
variables: {self.intention_prompt['last']['vars']},
function: 用于生成一天中最后一个intention
""")
        print("4.3 Nornal Intention:")
        print(f"""f_string: {self.intention_prompt['normal']['f_string']},
variables: {self.intention_prompt['normal']['vars']},
function: 用于生成常规的intention
""")
        
        print("5. Time generation prompt:")
        print(f"""f_string: {self.time_prompt['f_string']},
variables: {self.time_prompt['vars']},
function: 用于生成intention对应的时间
""")

    def set_prompt(self, target:str, prompt:str, vars:list[str]=[]):
        if len(vars) > 0:
            for var in vars:
                if var not in ['genderDescription', 'educationDescription', 'consumptionDescription', 'occupationDescription', 'day', 'dayDescription', 'personDescription', 'intentTotal', 'intentIndex', 'history']:
                    print("Wrong variable name, only ['genderDescription', 'educationDescription', 'consumptionDescription', 'occupationDescription', 'day', 'personDescription', 'intentTotal', 'intentIndex', 'history'] are available")
        if target == 'system':
            self.system_prompt['f_string'] = prompt
            self.system_prompt['vars'] = vars
        elif target == 'person':
            self.person_des_prompt['f_string'] = prompt
            self.person_des_prompt['vars'] = vars
        elif target == 'day-weekend':
            self.day_prompt['weekend']['f_string'] = prompt
            self.day_prompt['weekend']['vars'] = vars
        elif target == 'day-workday':
            self.day_prompt['workday']['f_string'] = prompt
            self.day_prompt['workday']['vars'] = vars
        elif target == 'intent-first':
            self.intention_prompt['first']['f_string'] = prompt
            self.intention_prompt['first']['vars'] = vars
        elif target == 'intent-last':
            self.intention_prompt['last']['f_string'] = prompt
            self.intention_prompt['last']['vars'] = vars
        elif target == 'intent-normal':
            self.intention_prompt['normal']['f_string'] = prompt
            self.intention_prompt['normal']['vars'] = vars
        elif target == 'time':
            self.time_prompt['f_string'] = prompt
            self.time_prompt['vars'] = vars
        else:
            print("Wrong target, only ['system', 'person', 'day-weekend', 'day-workday', 'intent-first', 'intent-last', 'intent-normal', 'time'] are available")

    def _generation_prompt_content(self, target:str):
        if target == 'personDescription':
            num_vars = 0 if 'vars' not in self.person_des_prompt.keys() else len(self.person_des_prompt['vars'])
            if num_vars == 0:
                return f"{self.person_des_prompt['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.person_des_prompt['vars'][i]])
                return f"{self.person_des_prompt['f_string'].format(*vars)}"
        elif target == 'day':
            if self.agent.Brain.Memory.Working.Reason['day'] in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
                num_vars = 0 if 'vars' not in self.day_prompt['workday'].keys() else len(self.day_prompt['workday']['vars'])
                if num_vars == 0:
                    return f"{self.day_prompt['workday']['f_string']}"
                else:
                    vars = []
                    for i in range(num_vars):
                        vars.append(self.agent.Brain.Memory.Working.Reason[self.day_prompt['workday']['vars'][i]])
                    return f"{self.day_prompt['workday']['f_string'].format(*vars)}"
            else:
                num_vars = 0 if 'vars' not in self.day_prompt['weekend'].keys() else len(self.day_prompt['weekend']['vars'])
                if num_vars == 0:
                    return f"{self.day_prompt['weekend']['f_string']}"
                else:
                    vars = []
                    for i in range(num_vars):
                        vars.append(self.agent.Brain.Memory.Working.Reason[self.day_prompt['weekend']['vars'][i]])
                    return f"{self.day_prompt['weekend']['f_string'].format(*vars)}"
        elif target == 'globalInfo':
            num_vars = 0 if 'vars' not in self.system_prompt.keys() else len(self.system_prompt['vars'])
            if num_vars == 0:
                return f"{self.system_prompt['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.system_prompt['vars'][i]])
                return f"{self.system_prompt['f_string'].format(*vars)}"
        elif target == 'firstQuestion':
            num_vars = 0 if 'vars' not in self.intention_prompt['first'].keys() else len(self.intention_prompt['first']['vars'])
            if num_vars == 0:
                return f"{self.intention_prompt['first']['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.intention_prompt['first']['vars'][i]])
                return f"{self.intention_prompt['first']['f_string'].format(*vars)}"
        elif target == 'lastQuestion':
            num_vars = 0 if 'vars' not in self.intention_prompt['last'].keys() else len(self.intention_prompt['last']['vars'])
            if num_vars == 0:
                return f"{self.intention_prompt['last']['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.intention_prompt['last']['vars'][i]])
                return f"{self.intention_prompt['last']['f_string'].format(*vars)}"
        elif target == 'normalQuestion':
            num_vars = 0 if 'vars' not in self.intention_prompt['normal'].keys() else len(self.intention_prompt['normal']['vars'])
            if num_vars == 0:
                return f"{self.intention_prompt['normal']['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.intention_prompt['last']['vars'][i]])
                return f"{self.intention_prompt['normal']['f_string'].format(*vars)}"
        elif target == 'timeQuestion':
            num_vars = 0 if 'vars' not in self.time_prompt.keys() else len(self.time_prompt['vars'])
            if num_vars == 0:
                return f"{self.time_prompt['f_string']}"
            else:
                vars = []
                for i in range(num_vars):
                    vars.append(self.agent.Brain.Memory.Working.Reason[self.time_prompt['vars'][i]])
                return f"{self.time_prompt['f_string'].format(*vars)}"
        

    async def run(self, intent_number:int, day:str, show_prompts:bool=False, hub:bool=False):
        N = intent_number
        if day not in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            print("错误的日期，仅支持 ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']")
            return
        
        if self.agent == None:
            self.agent = await self.sim.GetFuncAgent(self.agent_id, self.agent_name)
            self.agent.StateTransformer.reset_state_transformer(['Mobility'], 'Mobility')
            self.agent.StateTransformer.add_transition(trigger='start', source='*', dest='Mobility')
        if hub:
            self.agent.ConnectToHub(self.config['apphub_request'])
            self.agent.Bind()

        self.agent.add_soul(self.soul)
        self.agent.Brain.Memory.Working.reset_reason()
        self.agent.Brain.Memory.Working.Reason = {}
        self.agent.Brain.Memory.Working.Reason['genderDescription'] = self.genderDescription
        self.agent.Brain.Memory.Working.Reason['educationDescription'] = self.educationDescription
        self.agent.Brain.Memory.Working.Reason['consumptionDescription'] = self.consumptionDescription
        self.agent.Brain.Memory.Working.Reason['occupationDescription'] = self.occupationDescription
        self.agent.Brain.Memory.Working.Reason['day'] = day
        self.agent.Brain.Memory.Working.Reason['dayDescription'] = self._generation_prompt_content('day')
        self.agent.Brain.Memory.Working.Reason['personDescription'] = self._generation_prompt_content('personDescription')
        self.agent.Brain.Memory.Working.Reason['intentTotal'] = N
        self.agent.Brain.Memory.Working.Reason['intentIndex'] = 0
        self.agent.Brain.Memory.Working.Reason['history'] = []
        globalInfo_content = self._generation_prompt_content('globalInfo')
        globalInfo = [{'role': 'system', 'content': globalInfo_content}]
        self.agent.Brain.Memory.Working.Reason['globalInfo'] = globalInfo  # 临时传参方式[捂脸]
        self.agent.Brain.Memory.Working.Reason['nowTime'] = '00:00'
        self.agent.Brain.Memory.Working.Reason['trajectory'] = []
        self.agent.Brain.Memory.Working.Reason['show_prompts'] = show_prompts

        (home, work) = choiceHW()
        Homeplace = (home[0], home[1])
        Workplace = (work[0], work[1])
        nowPlace = Homeplace  # 0是POI的name,1是POI的id,而且是int类型的
        if hub:
            await self.agent.set_position_poi(nowPlace[1])

        self.agent.Brain.Memory.Working.Reason['nowPlace'] = nowPlace  # 名称和地点
        self.agent.Brain.Memory.Working.Reason['Homeplace'] = Homeplace  # 名称和地点
        self.agent.Brain.Memory.Working.Reason['Workplace'] = Workplace  # 名称和地点
        
        self.agent.Brain.Memory.Working.add_reason('Mobility', self.reasons[0])
        self.agent.Brain.Memory.Working.add_reason('Mobility', self.reasons[1])

        for i in range(N):
            if i == N-1:
                self.agent.Brain.Memory.Working.Reason['intent_question'] = self._generation_prompt_content('lastQuestion')
            elif i == 0:
                self.agent.Brain.Memory.Working.Reason['intent_question'] = self._generation_prompt_content('firstQuestion')
            else:
                self.agent.Brain.Memory.Working.Reason['intent_question'] = self._generation_prompt_content('normalQuestion')
            self.agent.Brain.Memory.Working.Reason['time_question'] = self._generation_prompt_content('timeQuestion')
            await self.agent.Brain.Memory.Working.runReason()
            if hub:
                await self.agent.set_position_poi(self.agent.Brain.Memory.Working.Reason['nowPlace'][1])
            
            if self.agent.Brain.Memory.Working.Reason['break']:  # 跨天就提前结束生成
                break
        
        # print(agent.Brain.Memory.Working.Reason['history'])  # history里存的是时间模板
        print(self.agent.Brain.Memory.Working.Reason['trajectory'])