import re
import requests


def getUrl(id): # id = 'https://cloud.mail.ru/public/публичная/ссылка'
    first = re.compile(r"\"url\": \"[A-Za-z0-9\t\n:/.-]*\"")
    part = id.rpartition('public/')[-1]
    temp = requests.get(id)
    temp = temp.text
    magic = temp.rpartition('"weblink_get"')[2]
    res = first.findall(magic)[0]
    res = re.findall(r"\"[A-Za-z0-9\t\n:/.-]*\"", res)[1][1:-1]
    url = f"{res}/{part}"
    return url