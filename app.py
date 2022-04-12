import ast
import hashlib
import logging
import os
import time
import math
import random
from pathlib import Path
import requests
import threading
# from flask import Flask, request, render_template, Response, redirect
from fastapi import FastAPI, Response, Request, responses
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from zipStream import *

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(Path(BASE_DIR, 'templates')))
app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR, 'static'))), name="static")

rnums = {}
dnums = {}
Kb = 2 ** 10
Mb = 2 ** 20
Total_RAM = 480 * Mb

REVISION = "3"
VERSION = "4.1"


@app.get("/")
def about():
    return f"p2p-tunnel{REVISION} v{VERSION}"


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
            print("DEBUG:", self.getMultifile, self.multifileFlag)
            if self.getMultifile is True or not self.multifileFlag:
                return f"{self.Hashes[(findex, index)]}"
            else:
                return f"{self.zipStream.getHash(index)}"
        return None

    def removechunk(self, findex, index, forced=False):
        print(f"Удаление... {self.SecureRemoveChunks} | {forced}")
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
        self.Hashes[(findex, index)] = hashlib.sha1(data).hexdigest()
        return {"status": "ok"}

    def getInfo(self, args):
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


def memoryCheck(RAM):
    sum_RAM = 0
    for k, v in rnums.items():
        sum_RAM += v.RAM
    if RAM <= Total_RAM - sum_RAM:
        return True
    else:
        return (Total_RAM - sum_RAM) - RAM


def checkToken(rnum, type="Up", token="00000000"):
    if type == "Up":
        return token == rnums[rnum].uploadtoken
    elif type == "Down":
        return token == rnums[rnum].downloadtoken


##################################################################
#####                   RNUM REGISTR                        ######
##################################################################


@app.get("/reg")
def registration():
    nums = list(map(str, range(10)))
    rnum = int("".join(random.sample(nums, 4)))
    while rnum in rnums:
        rnum = int("".join(random.sample(nums, 4)))
    rnums[rnum] = Tunnel()
    rnums[rnum].setrnum(rnum)
    return rnum


@app.get("/start/{rnum}")
def start(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Up", token):
        log = rnums[rnum].init(args)
    else:
        log = {"status": "Access denied"}
    return log


@app.post("/start/{rnum}")
async def start_post(rnum: int, req: Request):
    body = await req.body()
    args = ast.literal_eval(body.decode("UTF-8"))
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Up", token):
        log = rnums[rnum].init(args)
    else:
        log = {"status": "Access denied"}
    return log


@app.get("/awaitChunk/{rnum}")
def await_chunk(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Down", token):
        return rnums[rnum].uploadawait()
    else:
        return {"status": "Access denied"}


@app.get("/downloadChunk/{rnum}")
def download_chunk(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Down", token):
        return Response(content=rnums[rnum].upload(args))
    else:
        return {"status": "Access denied"}


@app.get("/removeChunk/{rnum}")
def remove_chunk(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Down", token):
        findex = int(args.get("findex", -1))
        index = int(args["index"])
        rnums[rnum].removechunk(findex, index, True)
        return {"status": "Ok"}
    else:
        return {"status": "Access denied"}


@app.get("/uploadawait/{rnum}")
def upload_await(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Up", token):
        return rnums[rnum].downloadawait()
    else:
        return {"status": "Access denied"}


@app.post("/uploadChunk/{rnum}")
async def upload_chunk(rnum: int, req: Request):
    args = dict(req.query_params)
    token = "00000000" if "token" not in args else args["token"]
    if checkToken(rnum, "Up", token):
        data = await req.body()
        return rnums[rnum].downloadchunk(data, args)
    else:
        return {"status": "Access denied"}


@app.get("/directlink/{rnum}")
def direct_download(rnum):
    tunnel = rnums[rnum]
    if tunnel.downloadtoken == "00000000":
        if tunnel.isUploaded():
            if tunnel.isDownloadable():
                return responses.RedirectResponse(f"/directlink/{rnum}/{tunnel.filename}")
            else:
                return "Access denied: file is too big"
        else:
            return "Access denied: file is not full"
    else:
        return {"status": "Access denied"}


@app.get("/directlink/{rnum}/{filename}}")
def direct_download2(rnum:int, filename:str):
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

@app.get("/info/{rnum}")
def info(rnum: int, req: Request):
    args = dict(req.query_params)
    info = rnums[rnum].getInfo(args)
    return info


@app.get("/json/{rnum}")
def json(rnum: int):
    return rnums[rnum].json()


@app.get("/clear")
def clear():
    rnums = getallrnums()
    for rnum in rnums:
        del rnums[rnum]
        del rnum


@app.get("/gtrns")
def getallrnums():
    if rnums:
        return {"rnums": [k for k, v in rnums.items()]}
    else:
        return {"rnums": None}


@app.get("/kill/{rnum}")
def kill(rnum: int):
    print(rnums[rnum].Hashes)
    del rnums[rnum]
    return {"status": "ok"}


##################################################################
#####                   DNUM REGISTR                        ######
##################################################################

@app.get("/dreg")
def dregistration():
    nums = list(map(str, range(10)))
    dnum = int("".join(random.sample(nums, 4)))
    while dnum in dnums:
        dnum = int("".join(random.sample(nums, 4)))
    dnums[dnum] = {}
    return dnum


@app.get("/sendRnum/{dnum}")
def sendRnum(dnum: int, req: Request):
    args = dict(req.query_params)
    data = {"rnum": args["rnum"],
            "server": args["server"]}
    dnums[dnum] = data
    return {"status": "ok"}


@app.get("/awaitRnum/{dnum}")
def awaitRnum(dnum: int):
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
@app.get("/gettoken")
def tokenregistration():
    nums = list(map(str, range(10)))
    token = int("".join(random.sample(nums, 8)))
    while str(token)[0] == "0":
        token = int("".join(random.sample(nums, 8)))
    return token


@app.get("/setuploadtoken")
def setUploadToken(req: Request):
    args = dict(req.query_params)
    rnum, token = int(args["rnum"]), args["token"]
    if rnums[rnum].uploadtoken != "00000000":
        return {"status": "Access denied"}
    rnums[rnum].uploadtoken = token
    return {"status": "Ok"}


@app.get("/setdownloadtoken")
def setDownloadToken(req: Request):
    args = dict(req.query_params)
    rnum, token = int(args["rnum"]), args["token"]
    if rnums[rnum].downloadtoken != "00000000":
        return {"status": "Access denied"}
    rnums[rnum].downloadtoken = token
    return {"status": "Ok"}


##################################################################
#####                        VISUAL                         ######
##################################################################


@app.get("/p2p", response_class=responses.HTMLResponse)
def mainpage(request: Request):
    return templates.TemplateResponse("p2p.html", {"request": request})


@app.get("/download", response_class=responses.HTMLResponse)
def download(request: Request):
    return templates.TemplateResponse("download.html", {"request": request})


@app.get("/upload", response_class=responses.HTMLResponse)
def upload(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/test")
def test(req: Request):
    return str(dict(req.query_params))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host='0.0.0.0', port=port, reload=False)
