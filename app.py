import ast
import hashlib
import logging
import os
import time
import math
import io
import random
from pathlib import Path
import requests
import threading
from flask import Flask, request, render_template, Response, redirect

from mailru import getUrl
from zipStream import *


app = Flask(__name__)
rnums = {}
dnums = {}
Kb = 2 ** 10
Mb = 2 ** 20
Total_RAM = 480 * Mb


REVISION = "2"
VERSION = "27.1"
GitHubLink = "https://raw.githubusercontent.com/dail45/Updates/main/P2P.json"


@app.route("/")
def about():
    return f"p2p-tunnel{REVISION} v{VERSION}"


@app.route("/p2p.exe")
def get_p2p_exe():
    res = requests.get(GitHubLink, verify=False).json()
    url = getUrl(res["URL"])
    data = requests.get(url, verify=False).content
    res = Response(data)
    res.headers["Content-Disposition"] = f"attachment; %20filename=p2p.exe"
    res.headers["Content-Length"] = str(len(data))
    res.headers["Content-Type"] = "multipart/form-data"
    return res


class Tunnel:
    def __init__(self):
        """DOWNLOADED: from S or P >>> STORAGE"""
        """UPLOADED: from STORAGE >>> P"""
        self.uploadtoken = "00000000"
        self.downloadtoken = "00000000"

        self.total_length = 0
        self.total_chunks = 0
        self.STORAGE = {}
        self.STORAGELIST = []
        self.Hashes = {}
        self.HashErrors = []
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
        self.SecureRemoveChunks = False
        self.SecureDownloading = False
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
        if "file_name" in json:
            return self.androidInitAdapter(json)
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
        if self.filename and "/" in self.filename:
            self.filename = self.filename.split("/")[-1]
        if self.filenames:
            self.filenames = list(map(lambda s: s.split("/")[-1] if "/" in s else s, ast.literal_eval(self.filenames)))
        self.multifileFlag = int(json.get("multifile", 0))
        self.total_length = int(json.get("totallength", -1))
        self.total_lengths = json.get("totallengths", [-1])
        if self.total_lengths != [-1]:
            self.total_lengths = list(map(lambda x: int(x), ast.literal_eval(self.total_lengths)))
        if self.total_length and self.total_length > 0:
            self.total_chunks = math.ceil(self.total_length / self.chunksize)
        if self.total_lengths != -1:
            self.totals_chunks = list(map(lambda x: math.ceil(x / self.chunksize), self.total_lengths))
        else:
            self.totals_chunks = 0
        self.start()
        self.zipStream = None
        if self.multifileFlag == 1:
            self.zipStream = ZipStream(self)
            self.zipStream.updateFileHeaders(json)
        return self.log("start")

    def androidInitAdapter(self, json):
        self.url = json.get("url", None)
        self.type = "S2P" if self.url else "P2P"
        self.RAMErrorIgnore = int(json.get("ignoreRamError", 0))
        RAM = int(json.get("ram", 64 * Mb))
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
        self.chunksize = int(json.get("chunk_size", 4 * Mb))
        self.filename = json.get("file_name", None)
        self.filenames = json.get("file_names", None)
        if self.filename and "/" in self.filename:
            self.filename = self.filename.split("/")[-1]
        if self.filenames:
            self.filenames = list(map(lambda s: s.split("/")[-1] if "/" in s else s, ast.literal_eval(self.filenames)))
        self.multifileFlag = int(json.get("multifile", 0))
        self.total_length = int(json.get("file_size", -1))
        self.total_lengths = json.get("file_sizes", [-1])
        if self.total_lengths != [-1]:
            self.total_lengths = list(map(lambda x: int(x), ast.literal_eval(self.total_lengths)))
        if self.total_length and self.total_length > 0:
            self.total_chunks = math.ceil(self.total_length / self.chunksize)
        if self.total_lengths != -1:
            self.totals_chunks = list(map(lambda x: math.ceil(x / self.chunksize), self.total_lengths))
        else:
            self.totals_chunks = 0
        self.start()
        self.zipStream = None
        if self.multifileFlag == 1:
            self.zipStream = ZipStream(self)
            self.zipStream.updateFileHeaders(json)
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

    def isUploaded(self):
        return self.checkDead()

    def isDownloadable(self):
        if self.zipStream:
            self.filename = "untitled.zip"
        if self.UPLOADED > 0:
            return False
        return True if (self.zipStream and self.zipStream.getTotalLength() <= self.RAM) or (
                self.multifileFlag == 0 and self.total_length <= self.RAM) else False

    def directDownload(self):
        if self.zipStream:
            data = b"".join([self.zipStream.getChunk(i) for i in range(len(self.zipStream.storage))])
        else:
            data = b"".join([self.STORAGE[i + 1] for i in range(len(self.STORAGE))])
        # totallength = self.zipStream.getTotalLength() if self.zipStream else self.total_length
        # if totallength == len(data):
        #     return data
        # else:
        #     return False
        return data

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
        if self.UPLOADED < self.total_chunks and self.multifileFlag == 0:
            return "alive"
        elif self.multifileFlag == 1:
            if self.getMultifile is True:
                if self.UPLOADED <= sum(self.totals_chunks):
                    return "alive"
            elif self.getMultifile is False:
                if self.zipStream.is_alive():
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
        print("status:", status)
        if status == "dead":
            return {"status": "dead",
                    "cnum": -1}
        start = time.time()
        while (self.total_chunks > self.UPLOADED and self.multifileFlag == 0) or (
                (self.multifileFlag == 1) and (
                (self.getMultifile is True and self.UPLOADED <= sum(self.totals_chunks)
                ) or (
                self.getMultifile is False and self.zipStream.is_alive()))):
            if self.DOWNLOADED > self.UPLOADED or (self.multifileFlag == 1 and self.getMultifile is False and
                                                   self.zipStream.is_alive()):
                if time.time() - start > 25:
                    return {"status": "alive-timeout",
                            "cnum": -1}
                if len(self.STORAGELIST) > 0 or (self.multifileFlag == 1 and self.getMultifile is False and
                                                 self.zipStream.is_alive() and (len(self.zipStream.storage) > 0 or
                                                 len(self.zipStream.STORAGE) > 0)):
                    self.lock.acquire()
                    if self.multifileFlag == 0:
                        num = self.STORAGELIST.pop(0) - 1
                        self.UPLOADED += 1
                        self.lock.release()
                        return {"status": "alive",
                                "cnum": num,
                                "Hash": self.getHash(-1, num)}
                    else:
                        if not self.getMultifile:
                            cindex = self.zipStream.awaitChunk()
                            # print("zipIndex:", cindex)
                            # print(self.zipStream.storage)
                            if cindex < 0:
                                self.lock.release()
                                continue
                            self.lock.release()
                            return {"status": "alive",
                                    "cnum": cindex,
                                    "Hash": self.getHash(-1, cindex)}
                        else:
                            findex, cindex = self.STORAGELIST.pop(0)
                            self.UPLOADED += 1
                            self.lock.release()
                            return {"status": "alive",
                                    "findex": findex,
                                    "cnum": cindex,
                                    "Hash": self.getHash(findex, cindex)}
                time.sleep(0.005)
        return {"status": "dead-timeout",
                "cnum": -1}

    def getHash(self, findex, index):
        if self.SecureDownloading:
            if self.getMultifile is True or not self.multifileFlag:
                return f"{self.Hashes[(findex, index)]}"
            else:
                return f"{self.zipStream.getHash(index)}"
        return None

    def removechunk(self, findex, index, forced=False):
        if self.SecureRemoveChunks is False or forced is True:
            if self.multifileFlag == 1:
                if not self.getMultifile:
                    self.zipStream.removeChunk(index)
                else:
                    del self.STORAGE[findex][index + 1]
            else:
                del self.STORAGE[index + 1]

    def upload(self, args) -> bytes:
        """
        Отдаёт чанк информации по номеру чанка и удаляет его из хранилища
        """
        if self.multifileFlag == 1:
            if not self.getMultifile:
                res = self.zipStream.getChunk(int(args["index"]))
                self.removechunk(-2, int(args["index"]))
            else:
                res = self.STORAGE[int(args["findex"])][int(args["index"]) + 1]
                self.removechunk(int(args["findex"]), int(args["index"]))
        else:
            res = self.STORAGE[int(args["index"]) + 1]
            self.removechunk(-1, int(args["index"]))
        return res

    def checkDead(self):
        if not self.multifileFlag:
            # print("check: ", self.DOWNLOADED >= self.total_chunks)
            # logging.warning(f"check: {self.DOWNLOADED, self.total_chunks}")
            if self.DOWNLOADED >= self.total_chunks:
                return True
            return False
        else:
            if self.DOWNLOADED >= sum(self.totals_chunks):
                return True
            return False

    "P2P Часть"
    def downloadawait(self, json):
        """
        Проверяет количество доступной ОЗУ и возвращает различные статусы:
        alive -> Всё ок
        ram-error -> что-то пошло не так
        alive-timeout -> всё ещё живо, но время запроса истекает
        dead -> загрузка завершена
        """
        findex, index = int(json.get("findex", -1)), int(json.get("index", -1))
        if (findex, index) in self.HashErrors and (findex, index) != (-1, -1):
            self.HashErrors.remove((findex, index))
            return {"status": "again"}
        if self.checkDead():
            return {"status": "dead"}
        start = time.time()
        while (len(self.STORAGELIST) + len(self.RESERVED) + 1) * self.chunksize > self.RAM:
            if time.time() - start > 25:
                return {"status": "alive-timeout", "data": [(len(self.STORAGELIST) + len(self.RESERVED) + 1) * self.chunksize, self.RAM]}
            if self.checkDead():
                return {"status": "dead"}
            time.sleep(0.005)
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
        in_hash = str(hashlib.sha1(data).hexdigest())
        hash = str(json.get("Hash", in_hash))
        if in_hash != hash:
            self.HashErrors.append(
                (int(json["findex"], -1),
                 int(json.get("index", -1)))
            )
            return {"status": "again"}
        index = int(json.get("index", -1))
        if self.multifileFlag == 0:
            findex = -1
            self.DOWNLOADED += 1
            self.STORAGE[self.DOWNLOADED if index == -1 else int(index) + 1] = data
            self.STORAGELIST.append(self.DOWNLOADED if index == -1 else int(index) + 1)
            self.RESERVED.pop()
        else:
            findex = int(json["findex"])
            self.DOWNLOADED += 1
            if findex in self.STORAGE:
                self.STORAGE[findex][index + 1] = data
            else:
                self.STORAGE[findex] = {index + 1: data}
            self.STORAGELIST.append((findex, index))
            self.RESERVED.pop()
        self.Hashes[(findex, index)] = hash
        return {"status": "ok"}

    def getInfo(self, args):
        "Если api = 1, то getInfo. Если api = 0, то androidAdapter"
        api = int(args.get("api", 1))
        if api == 0:
            return self.androidGetInfoAdapter(args)
        if self.multifileFlag:
            if "multifile" in args:
                if int(args["multifile"]) == 1:
                    self.getMultifile = True
            else:
                self.filename = self.zipStream.getFileName()
                self.total_length = self.zipStream.getTotalLength()
        if "SecureRemoveChunks" in args:
            self.SecureRemoveChunks = True if int(args["SecureRemoveChunks"]) == 1 else False
        if "SecureDownloading" in args:
            self.SecureDownloading = True if int(args["SecureDownloading"]) == 1 else False
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

    def androidGetInfoAdapter(self, args):
        if self.multifileFlag:
            if "multifile" in args:
                if int(args["multifile"]) == 1:
                    self.getMultifile = True
            else:
                self.filename = self.zipStream.getFileName()
                self.total_length = self.zipStream.getTotalLength()
        if "SecureRemoveChunks" in args:  # ToDo rename
            self.SecureRemoveChunks = True if int(args["SecureRemoveChunks"]) == 1 else False
        if "SecureDownloading" in args:  # ToDo rename
            self.SecureDownloading = True if int(args["SecureDownloading"]) == 1 else False
        return {
            "chunk_size": self.chunksize,
            "threads": self.threads,
            "ram": self.RAM,
            "file_name": self.filename,
            "file_names": self.filenames,
            "file_size": self.total_length,
            "file_sizes": self.total_lengths,
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


def checkToken(rnum, typeCheck="Up", token="00000000"):
    logging.warning(f"=====: {[(i, type(i)) for i in rnums.keys()]}")
    logging.warning((rnum, type(rnum)))
    if typeCheck == "Up":
        return token == rnums[rnum].uploadtoken
    elif typeCheck == "Down":
        return token == rnums[rnum].downloadtoken


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
    logging.warning(f"=====: {rnums.keys()}")
    time.sleep(0.05)
    return str(rnum)



@app.route("/start/<int:rnum>", methods=['GET', 'POST'])
def start(rnum):
    try:
        json = ast.literal_eval(request.data.decode("UTF-8"))
    except Exception:
        json = {}
    args = dict(request.args)
    args.update(json)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Up", token):
        log = rnums[rnum].init(args)
    else:
        log = {"status": "Access denied"}
    return log


@app.route("/awaitChunk/<int:rnum>")
def await_chunk(rnum):
    json = request.args
    token = "00000000" if "token" not in json else json["token"]
    if checkToken(rnum, "Down", token):
        return rnums[rnum].uploadawait()
    else:
        return {"status": "Access denied"}


@app.route("/downloadChunk/<int:rnum>")
def download_chunk(rnum):
    args = request.args
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Down", token):
        return rnums[rnum].upload(args)
    else:
        return {"status": "Access denied"}


@app.route("/removeChunk/<int:rnum>")
def remove_chunk(rnum):
    args = request.args
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Down", token):
        findex = int(args.get("findex", -1))
        index = int(args["index"])
        rnums[rnum].removechunk(findex, index, True)
        return {"status": "Ok"}
    else:
        return {"status": "Access denied"}

@app.route("/uploadawait/<int:rnum>")
def upload_await(rnum):
    json = request.args
    token = "00000000" if "token" not in json else json["token"]
    if checkToken(rnum, "Up", token):
        return rnums[rnum].downloadawait(json)
    else:
        return {"status": "Access denied"}


@app.route("/uploadChunk/<int:rnum>", methods=['GET', 'POST'])
def upload_chunk(rnum):
    json = request.args
    token = "00000000" if "token" not in json else json["token"]
    if checkToken(rnum, "Up", token):
        data = request.data
        return rnums[rnum].downloadchunk(data, json)
    else:
        return {"status": "Access denied"}


@app.route("/directlink/<int:rnum>")
def direct_download(rnum):
    tunnel = rnums[rnum]
    if tunnel.downloadtoken == "00000000":
        if tunnel.isUploaded():
            if tunnel.isDownloadable():
                return redirect(f"/directlink/{rnum}/{tunnel.filename}")
            else:
                return "Access denied: file is too big"
        else:
            return "Access denied: file is not full"
    else:
        return {"status": "Access denied"}


@app.route("/directlink/<int:rnum>/<string:filename>")
def direct_download2(rnum, filename):
    tunnel = rnums[rnum]
    data = tunnel.directDownload()
    res = Response(data)
    res.headers["Content-Disposition"] = f"attachment; %20filename={filename}"
    res.headers["Content-Length"] = str(len(data))
    res.headers["Content-Type"] = "multipart/form-data"
    kill(rnum)
    return res

##################################################################
#####                       Service                         ######
##################################################################

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
    rnums.clear()


@app.route("/gtrns")
def getallrnums():
    if rnums:
        return {"rnums": [k for k, v in rnums.items()]}
    else:
        return {"rnums": None}


@app.route("/kill/<int:rnum>")
def kill(rnum):
    del rnums[rnum]
    return {"status": "ok"}

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
#####                     Token verivy                      ######
##################################################################
@app.route("/gettoken")
def tokenregistration():
    nums = list(map(str, range(10)))
    token = int("".join(random.sample(nums, 8)))
    while str(token)[0] == "0":
        token = int("".join(random.sample(nums, 8)))
    return str(token)


@app.route("/setuploadtoken")
def setUploadToken():
    rnum, token = int(request.args["rnum"]), request.args["token"]
    logging.warning(f"=====: {[(i, type(i)) for i in rnums.keys()]}")
    logging.warning((rnum, type(rnum)))
    if rnums[rnum].uploadtoken != "00000000":
        return {"status": "Access denied"}
    rnums[rnum].uploadtoken = token
    return {"status": "Ok"}


@app.route("/setdownloadtoken")
def setDownloadToken():
    rnum, token = int(request.args["rnum"]), request.args["token"]
    if rnums[rnum].downloadtoken != "00000000":
        return {"status": "Access denied"}
    rnums[rnum].downloadtoken = token
    return {"status": "Ok"}

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
