import ast
import logging
import os
import time
import math
import random
import requests
import threading
from flask import Flask, request, render_template

app = Flask(__name__)
rnums = {}
dnums = {}
Kb = 2 ** 10
Mb = 2 ** 20
Total_RAM = 480 * Mb


@app.route("/")
def about():
    return "p2p-tunnel2 v12"


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
        self.getMultifile = False
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
        self.filenames = json.get("filenames", None)
        if "/" in self.filename:
            self.filename = self.filename.split("/")[-1]
        if self.filenames:
            self.filenames = list(map(lambda s: s.split("/")[-1] if "/" in s else s, self.filenames))
        self.multifileFlag = int(json.get("multifile", 0))
        self.total_length = int(json.get("totallength", -1))
        self.total_lengths = list(map(lambda x: int(x), json.get("totallengths", [-1])))
        if self.total_length > 0:
            self.total_chunks = math.ceil(self.total_length / self.chunksize)
        if self.total_lengths:
            self.totals_chunks = list(map(lambda x: math.ceil(x / self.chunksize), self.total_lengths))
        self.start()
        return self.log("start")

    def log(self, state):
        if state == "start":
            return {"rnum": self.id,
                    "url": self.url,
                    "RAM": self.RAM,
                    "threads": self.threads,
                    "chunksize": self.chunksize,
                    "totallength": self.total_length,
                    "totalchunks": self.total_chunks if self.total_chunks else 0,
                    "filename": self.filename,
                    "startheaders": self.sheaders,
                    "filenames": self.filenames,
                    "totallengths": self.total_lengths,
                    "totalschunks": self.totals_chunks}

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
        logging.warning(f"{[{'Uploaded': self.UPLOADED, 'total_chunks': self.total_chunks, 'multifileFlag': self.multifileFlag, 'sum(total_chunks)': sum(self.totals_chunks)}]}")
        if self.UPLOADED < self.total_chunks and self.multifileFlag == 0:
            return "alive"
        elif self.multifileFlag == 1:
            if self.getMultifile is True:
                if self.UPLOADED <= sum(self.totals_chunks):
                    return "alive"
            elif self.getMultifile is False:
                if self.UPLOADED <= self.totals_chunks[0]:
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
                        if not self.multifileFlag:
                            num = self.STORAGELIST.pop(0) - 1
                            self.UPLOADED += 1
                            self.lock.release()
                            return {"status": "alive",
                                    "cnum": num}
                        else:
                            findex, cindex = self.STORAGELIST.pop(0)
                            if not self.getMultifile:
                                if int(findex) != 0:
                                    return {"status": "alive-timeout",
                                            "cnum": -1}
                                return {"status": "alive",
                                        "cnum": cindex}
                            else:
                                return {"status": "alive",
                                        "findex": findex,
                                        "cnum": cindex}
                except Exception:
                    pass
                time.sleep(0.05)
        return {"status": "dead-timeout",
                "cnum": -1}

    def upload(self, args):
        """
        Отдаёт чанк информации по номеру чанка и удаляет его из хранилища
        """
        if not self.getMultifile:
            res = self.STORAGE[int(args["index"]) + 1]
            del self.STORAGE[int(args["index"]) + 1]
        else:
            res = self.STORAGE[int(args["findex"])][int(args["index"]) + 1]
            del self.STORAGE[int(args["findex"])][int(args["index"]) + 1]
        return res

    def checkDead(self):
        if not self.multifileFlag:
            print("check: ", self.DOWNLOADED >= self.total_chunks)
            logging.warning(f"check: {self.DOWNLOADED, self.total_chunks}")
            if self.DOWNLOADED >= self.total_chunks:
                return True
            return False
        else:
            if not self.getMultifile:
                if self.DOWNLOADED >= self.totals_chunks[0]:
                    return True
                return False
            else:
                if self.DOWNLOADED >= sum(self.totals_chunks):
                    return True
                return False

    "P2P Часть"
    def downloadawait(self):

        """
        Проверяет количество доступной ОЗУ и возвращает различные статусы:
        alive -> Всё ок
        ram-error -> что-то пошло не так
        alive-timeout -> всё ещё живо, но время запроса истекает
        dead -> загрузка завершена
        """
        if self.checkDead():
            return {"status": "dead"}
        start = time.time()
        while (len(self.STORAGELIST) + len(self.RESERVED) + 1) * self.chunksize > self.RAM:
            if time.time() - start > 25:
                return {"status": "alive-timeout", "data": [(len(self.STORAGELIST) + len(self.RESERVED) + 1) * self.chunksize, self.RAM]}
            if self.checkDead():
                return {"status": "dead"}
            time.sleep(0.05)
        self.lock2.acquire()
        if (len(self.STORAGELIST) + len(self.RESERVED) + 1) * self.chunksize > self.RAM:
            return {"status": "ram-error"}
        self.RESERVED.append(self.DOWNLOADED + 1 if len(self.RESERVED) == 0 else self.RESERVED[-1] + 1)
        self.lock2.release()
        return {"status": "alive"}

    def downloadchunk(self, data, json):
        """
        Сохраняет data в памяти, json хранит информацию о индексе чанка и индексе файла.
        """
        index = json.get("index", -1)
        if self.multifileFlag == 0:
            self.DOWNLOADED += 1
            self.STORAGE[self.DOWNLOADED if index == -1 else int(index) + 1] = data
            self.STORAGELIST.append(self.DOWNLOADED if index == -1 else int(index) + 1)
            self.RESERVED.pop()
        else:
            findex = json["findex"]
            self.DOWNLOADED += 1
            if findex in self.STORAGE:
                self.STORAGE[findex][index + 1] = data
            else:
                self.STORAGE[findex] = {index + 1: data}
            self.STORAGELIST.append((findex, index))
            self.RESERVED.pop()
        return {"status": "ok"}

    def getInfo(self, args):
        if self.multifileFlag:
            if "multifile" in args:
                if args["multifile"] == 1:
                    self.getMultifile = True
        return {
            "chunksize": self.chunksize,
            "threads": self.threads,
            "RAM": self.RAM,
            "filename": self.filename,
            "filenames": self.filenames,
            "totallength": self.total_length,
            "totallengths": self.total_lengths,
            "multifile": 1 if self.multifileFlag else 0
        }


def memoryCheck(RAM):
    sum_RAM = 0
    for k, v in rnums.items():
        sum_RAM += v.RAM
    if RAM <= Total_RAM - sum_RAM:
        return True
    else:
        return (Total_RAM - sum_RAM) - RAM


##################################################################
#####                   RNUM REGISTR                        ######
##################################################################


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
    return {"status": "ok"}


@app.route("/gtrns")
def getallrnums():
    if rnums:
        return {"rnums": [k for k, v in rnums.items()]}
    else:
        return {"rnums": None}


@app.route("/start/<int:rnum>", methods=['GET', 'POST'])
def start(rnum):
    body = request.data
    json = request.args
    if body:
        json = ast.literal_eval(body.decode("UTF-8"))
    log = rnums[rnum].init(json)
    return log


@app.route("/awaitChunk/<int:rnum>")
def await_chunk(rnum):
    return rnums[rnum].uploadawait()


@app.route("/downloadChunk/<int:rnum>")
def download_chunk(rnum):
    args = request.args
    return rnums[rnum].upload(args)


@app.route("/uploadawait/<int:rnum>")
def upload_await(rnum):
    return rnums[rnum].downloadawait()


@app.route("/uploadChunk/<int:rnum>", methods=['GET', 'POST'])
def upload_chunk(rnum):
    data = request.data
    json = request.args
    rnums[rnum].downloadchunk(data, json)
    return {"status": "ok"}


@app.route("/info/<int:rnum>")
def info(rnum):
    args = request.args
    info = rnums[rnum].getInfo(args)
    return info


@app.route("/json/<int:rnum>")
def json(rnum):
    return rnums[rnum].json()


@app.route("/clear")
def clear():
    rnums = getallrnums()
    for rnum in rnums:
        del rnum
    for k, v in rnums.items():
        del k[v]


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


##################################################################
#####                        VISUAL                         ######
##################################################################
@app.route("/p2p")
def mainpage():
    return render_template("p2p.html", title="p2p")


@app.route("/download")
def download():
    return render_template("download.html", title="Download")


@app.route("/upload")
def upload():
    return render_template("upload.html", title="Upload")


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
