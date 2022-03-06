import hashlib
import os
import re
import time
import math
import string
import random
import asyncio
from logging import log

import requests
import threading
from flask import Flask, request

app = Flask(__name__)
rnums = {}
dnums = {}
Kb = 2 ** 10
Mb = 2 ** 20
Total_RAM = 480 * Mb


@app.route("/")
def about():
    return "p2p-tunnel2 v8"


class Tunnel:
    def __init__(self):
        """DOWNLOADED: from S or P >>> STORAGE"""
        """UPLOADED: from STORAGE >>> P"""
        self.total_length = 0
        self.total_chunks = 0
        self.STORAGE = {}
        self.STORAGELIST = []
        self.RESERVED = []
        self.DOWNLOADED = 0
        self.UPLOADED = 0
        self.LOGS = []
        self.id = None
        self.url = None
        self.RAM = 0
        self.threads = 0
        self.chunksize = 0
        self.filename = None
        self.type = None
        self.sheaders = None
        self.S2PThread = None
        self.r = None
        self.lock = threading.Lock()
        self.lock2 = threading.Lock()
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"}

    def json(self):
        return {"total_length": self.total_length, "DOWNLOADED": self.DOWNLOADED, "UPLOADED": self.UPLOADED,
                "id": self.id, "url": self.url, "chunksize": self.chunksize, "threads": self.threads,
                "RAM": self.RAM, "type": self.type, "STORAGELIST": self.STORAGELIST}

    def setrnum(self, rnum):
        """
        Устанавливает id для туннеля.
        """
        self.id = rnum

    def init(self, json):
        """
        Принимает json, на его основе настраивает туннель.
        """
        self.url = json.get("url", None)
        self.type = "S2P" if self.url else "P2P"
        self.RAMErrorIgnore = int(json.get("RAMErrorIgnore", 0))
        RAM = int(json.get("RAM", 64 * Mb))
        if not self.RAMErrorIgnore:
            mcheck = memoryCheck(RAM)
            if mcheck is True:
                self.RAM = RAM
            else:
                rnums[self.id] = None
                del rnums[self.id]
                return {"RamMemoryError": mcheck}
        else:
            self.RAM = RAM
        self.threads = int(json.get("threads", 16))
        self.chunksize = int(json.get("chunksize", 4 * Mb))
        self.filename = json.get("filename", None)
        if "/" in self.filename:
            self.filename = self.filename.split("/")[-1]
        self.total_length = int(json.get("totallength", -1))
        if self.total_length > 0:
            self.total_chunks = math.ceil(self.total_length / self.chunksize)
        self.start()

        return self.log("start")

    def log(self, state):
        if state == "start":
            return {"rnum": self.id,
                    "url": self.url,
                    "RAM": self.RAM,
                    "threads": self.threads,
                    "chunksize": self.chunksize,
                    "filename": self.filename,
                    "startheaders": self.sheaders}

    def start(self):
        """
        Запускает процесс скачивания файла с сервера.
        """
        if self.type == "S2P":
            self.session = requests.Session()
            self.req = self.session.get(self.url, verify=False, stream=True, headers=self.headers)
            self.sheaders = self.req.headers
            try:
                self.total_length = int(self.sheaders["Content-Length"])
                self.total_chunks = math.ceil(self.total_length / self.chunksize)
            except Exception:
                pass
            self.r = self.req.iter_content(self.chunksize)
            self.S2PThread = threading.Thread(target=self.S2Pdownloadgenerator)
            self.S2PThread.start()
        elif self.type == "P2P":
            pass

    "S2P Часть"
    def S2Pdownloadgenerator(self):
        """
        Работает в потоке.
        Скачивает данные из iter_content.
        Следит за переполнением заданного кол-ва ОЗУ.
        """
        if self.url and self.type == "S2P":
            while self.total_length > self.UPLOADED:
                if len(self.STORAGE) * self.chunksize < self.RAM:
                    try:
                        self.STORAGE[self.DOWNLOADED + 1] = next(self.r)
                        self.STORAGELIST.append(self.DOWNLOADED + 1)
                        self.DOWNLOADED += 1
                    except StopIteration:
                        break
                else:
                    time.sleep(0.01)

    def uploadstatus(self):
        """
        Определяет, следует ли туннелю продолжать работу.
        Продолжает работу если кол-во отданный чанков меньше общего кол-ва чанков
        (полученных в прошлом/настоящем/будущем)
        """
        if self.UPLOADED < self.total_chunks:
            return "alive"
        elif len(self.STORAGELIST) > 0:  # Ненужен
            return "alive"
        elif self.DOWNLOADED > self.UPLOADED:  # Ненужен
            return "alive"
        else:
            return "dead"

    def uploadawait(self):
        """
        Определяет какой чанк нужно отдать,
        некий аналог лонгпула,
        определяет статус туннеля и возвращает пользователю:
        alive: работает
        dead: не работает
        alive-timeout: работает, но истекло время ожидания
        dead-timeout: не работает + истекло время ожидания
        """
        status = self.uploadstatus()
        if status == "dead":
            return {"status": "dead",
                    "cnum": -1}
        start = time.time()
        while self.total_chunks > self.UPLOADED:
            if self.DOWNLOADED > self.UPLOADED:
                if time.time() - start > 25:
                    return {"status": "alive-timeout",
                            "cnum": -1}
                try:
                    if len(self.STORAGELIST) > 0:
                        self.lock.acquire()
                        num = self.STORAGELIST.pop(0)
                        self.UPLOADED += 1
                        self.lock.release()
                        return {"status": "alive",
                                "cnum": num}
                except Exception:
                    pass
                time.sleep(0.05)
        return {"status": "dead-timeout",
                "cnum": -1}

    def upload(self, cnum):
        """
        Отдаёт чанк информации по номеру чанка и удаляет его из хранилища
        """
        res = self.STORAGE[cnum]
        del self.STORAGE[cnum]
        return res

    "P2P Часть"
    def downloadawait(self):
        if self.DOWNLOADED >= self.total_chunks:
            return {"status": "dead"}
        start = time.time()
        while not((len(self.STORAGELIST) + len(self.RESERVED)) * self.chunksize < self.RAM):
            if time.time() - start > 25:
                return {"status": "alive-timeout", "data": [(len(self.STORAGELIST) + len(self.RESERVED)) * self.chunksize, self.RAM]}
            if self.DOWNLOADED >= self.total_chunks:
                return {"status": "dead"}
            time.sleep(0.05)
        self.lock2.acquire()
        self.RESERVED.append(self.DOWNLOADED + 1)
        self.lock2.release()
        return {"status": "alive"}

    def downloadchunk(self, data, json):
        self.DOWNLOADED += 1
        index = json.get("index", -1)
        self.RESERVED.pop()
        self.STORAGE[self.DOWNLOADED if index == -1 else int(index) + 1] = data
        self.STORAGELIST.append(self.DOWNLOADED if index == -1 else int(index) + 1)
        return {"status": "ok"}

    def getInfo(self):
        return {
            "chunksize": self.chunksize,
            "threads": self.threads,
            "RAM": self.RAM,
            "filename": self.filename,
            "totallength": self.total_length
        }


def memoryCheck(RAM):
    sum_RAM = 0
    for k, v in rnums.items():
        sum_RAM += v.RAM
    if RAM <= Total_RAM - sum_RAM:
        return True
    else:
        return (Total_RAM - sum_RAM) - RAM


@app.route("/reg")
def registration():
    nums = list(map(str, range(10)))
    rnum = int("".join(random.sample(nums, 4)))
    while rnum in rnums:
        rnum = int("".join(random.sample(nums, 4)))
    rnums[rnum] = Tunnel()
    rnums[rnum].setrnum(rnum)
    return str(rnum)


@app.route("/kill/<int:rnum>")
def kill(rnum):
    del rnums[rnum]


@app.route("/gtrns")
def getallrnums():
    if rnums:
        return {"rnums": [k for k, v in rnums.items()]}
    else:
        return {"rnums": None}


@app.route("/start/<int:rnum>")
def start(rnum):
    json = request.args
    log = rnums[rnum].init(json)
    return log


@app.route("/awaitChunk/<int:rnum>")
def await_chunk(rnum):
    return rnums[rnum].uploadawait()


@app.route("/downloadChunk/<int:rnum>/<int:cnum>")
def download_chunk(rnum, cnum):
    return rnums[rnum].upload(cnum)


@app.route("/uploadawait/<int:rnum>")
def upload_await(rnum):
    return rnums[rnum].downloadawait()


@app.route("/uploadChunk/<int:rnum>", methods=['GET', 'POST'])
def upload_chunk(rnum):
    data = request.data
    json = request.args
    rnums[rnum].downloadchunk(data, json)
    import sys
    sys.stdout.write(str(json["index"]) + str([i for i in data[:16]]) + "\n")

    # print(hashlib.sha256(data).hexdigest())
    return {"status": "ok"}


@app.route("/info/<int:rnum>")
def info(rnum):
    info = rnums[rnum].getInfo()
    return info


@app.route("/json/<int:rnum>")
def json(rnum):
    return rnums[rnum].json()


@app.route("/clear")
def clear():
    rnums = getallrnums()
    for rnum in rnums:
        kill(rnum)

##################################################################
#####                   DNUM REGISTR                        ######
##################################################################


@app.route("/dreg")
def dregistration():
    nums = list(map(str, range(10)))
    dnum = int("".join(random.sample(nums, 4)))
    while dnum in dnums:
        dnum = int("".join(random.sample(nums, 4)))
    dnums[dnum] = {}
    return str(dnum)


@app.route("/sendRnum/<int:dnum>")
def sendRnum(dnum):
    data = request.args
    data2 = {"rnum": data["rnum"],
            "server": data["server"]}
    dnums[dnum] = data2
    return {"status": "ok"}


@app.route("/awaitRnum/<int:dnum>")
def awaitRnum(dnum):
    start = time.time()
    while True:
        if time.time() - start > 25:
            return {"status": "timeout"}
        if dnums[dnum]:
            data = dnums[dnum]
            del dnums[dnum]
            return {"status": "ok",
                    "data": data}
        time.sleep(0.05)



if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
