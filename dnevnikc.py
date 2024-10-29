import requests
import json
from fake_useragent import UserAgent
ua = UserAgent().random
year = '2024'
week = None


class dnevnik:
    def __init__(self, tokens):
        self.studentID = None
        self.classID = None
        self.periodsID = []
        self.token, self.refreshtoken = tokens
        print(f'<{self.token}>\n<{self.refreshtoken}>')

    def refresh(self):
        r = requests.post('https://dnevnik.egov66.ru/api/auth/Token/Refresh',
                          headers=self.headers(), data=json.dumps({'refreshToken': self.refreshtoken}))

        if r.status_code != 200:
            return False
        else:
            res = json.loads(r.text)
            self.token = res['accessToken']
            self.refreshtoken = res['refreshToken']

            return (self.token, self.refreshtoken)

    def headers(self):
        return {'content-type': 'application/json', "authorization": "Bearer"+" "+self.token,  'accept': 'application/json', 'user-agent': ua}

    def ids(self):
        r = requests.get(
            'https://dnevnik.egov66.ru/api/students',   headers=self.headers())
        print(r, '\n\n\n')
        id = json.loads(r.text)

        self.studentID = id['students'][0]['id']

        url = 'https://dnevnik.egov66.ru/api/classes?studentId=' + \
            self.studentID+'&schoolYear='+year
        r = requests.get(url, headers=self.headers())
        classID = json.loads(r.text)
        self.classID = classID['currentClass']['value']

        url = 'https://dnevnik.egov66.ru/api/estimate/periods?schoolYear=' + \
            year+'&classId='+self.classID+'&studentId='+self.studentID
        r = requests.get(url, headers=self.headers())
        periodsID = json.loads(r.text)
        self.periodsID = [periodsID['periods'][i]['id'] for i in range(6)]

    def schedule(self, day):
        self.ids()
        if week == None:
            url = 'https://dnevnik.egov66.ru/api/schedule?studentId='+self.studentID
        else:
            url = 'https://dnevnik.egov66.ru/api/schedule?pageNumber=' + \
                week+'&studentId='+self.studentID
        r = requests.get(url, headers=self.headers())
        schedule = json.loads(r.text)
        res = []
        num = 1
        for i in range(len(schedule["scheduleModel"]["days"][day]["scheduleDayLessonModels"])):
            res.append({'num': str(num), 'name': schedule["scheduleModel"]["days"][day]["scheduleDayLessonModels"][i]["lessonName"],
                        'room': schedule["scheduleModel"]["days"][day]["scheduleDayLessonModels"][i]["room"]})
            num += 1
        return res

    def profile(self):
        self.ids()
        url = 'https://dnevnik.egov66.ru/api/myprofile?studentId='+self.studentID
        r = requests.get(url, headers=self.headers())
        profile = json.loads(r.text)
        return profile

    def grades_period(self, period):
        self.ids()
        url = 'https://dnevnik.egov66.ru/api/estimate?schoolYear='+year+'&classId='+self.classID+'&periodId=' + \
            self.periodsID[period+2] + \
            '&subjectId=00000000-0000-0000-0000-000000000000&studentId='+self.studentID
        r = requests.get(url, headers=self.headers())
        grades = json.loads(r.text)
        res = []
        for i in grades['periodGradesTable']['disciplines']:
            gr = []
            for j in i['grades']:
                if j['grades'] != []:
                    for m in j['grades']:
                        gr.append(m)
            res.append({'name': i['name'], 'average': i['averageGrade'],
                       'averagew': i['averageWeightedGrade'], 'grades': gr})
        return res

    def grades_week(self):
        self.ids()
        if week == None:
            url = 'https://dnevnik.egov66.ru/api/estimate?schoolYear='+year+'&classId='+self.classID+'&periodId=' + \
                self.periodsID[0] + \
                '&subjectId=00000000-0000-0000-0000-000000000000&studentId='+self.studentID
        else:
            url = 'https://dnevnik.egov66.ru/api/estimate?schoolYear='+year+'&classId='+self.classID+'&periodId=' + \
                self.periodsID[0]+'&subjectId=00000000-0000-0000-0000-000000000000&studentId=' + \
                self.studentID+'&weekNumber='+week
        r = requests.get(url, headers=self.headers())
        grades = json.loads(r.text)
        res = {}
        for i in grades['weekGradesTable']['days']:
            for j in i['lessonGrades']:
                if j['name'] in res:
                    res[j['name']].append(j['grades'][0])
                else:
                    res[j['name']] = j['grades']
        return res

    def grades_year(self):
        self.ids()
        url = 'https://dnevnik.egov66.ru/api/estimate?schoolYear='+year+'&classId='+self.classID+'&periodId=' + \
            self.periodsID[1] + \
            '&subjectId=00000000-0000-0000-0000-000000000000&studentId='+self.studentID
        r = requests.get(url, headers=self.headers())
        grades = json.loads(r.text)
        res = []
        for i in grades['yearGradesTable']['lessonGrades']:
            gr = []
            for j in i['grades']:
                gr.append(j['finallygrade'])
            res.append({'name': i['lesson']['name'],
                       'grades': gr, 'yeargrade': i['yearGrade']})
        return res
