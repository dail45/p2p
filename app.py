import os
import time
import math
import string
import random
import asyncio
import requests
import threading
import p2ptorrent
from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def about():
    return "p2p-tunnel v12"


class P2PTunnel:
    def __init__(self):
        """DOWNLOADED: from S or P >>> STORAGE"""
        """UPLOADED: from STORAGE >>> P"""
        self.total_length = 0
        self.STORAGE = {}
        self.STORAGELIST = []
        self.DOWNLOADED = 0
        self.UPLOADED = 0
        self.LOGS = []

    def init(self, id, CHUNKSIZE=2 ** 20 * 4, THREADS=16, RAM=2 ** 20 * 64, filename="", URL=None, TorrentData=None, pieces=None):
        self.id = id
        self.URL = URL
        self.CHUNKSIZE = CHUNKSIZE
        self.THREADS = THREADS
        self.RAM = RAM
        self.filename = ""
        self.statuskillflag = False
        self.TorrentData = TorrentData
        self.pieces = pieces
        self.type = "P2P"
        self.lock = threading.Lock()
        if self.URL:
            self.type = "S2P"
            self.req = requests.get(URL, verify=False, stream=True)
            headers = self.req.headers
            self.r = self.req.iter_content(self.CHUNKSIZE)
            self.total_length = int(headers["Content-Length"])
            self.th = threading.Thread(target=self.S2Pdownloadgenerator)
            self.th.start()
            return headers
        if self.TorrentData:
            self.type = "T2P"
            self.loop = asyncio.get_event_loop()
            self.client = p2ptorrent.client.TorrentClient(p2ptorrent.torrent.Torrent(self.TorrentData), self)
            self.task = self.loop.create_task(self.client.start())
            self.th = threading.Thread(target=self.torrentThread)
            self.th.start()
        return {"id": self.id, "URL": self.URL, "chunksize": self.CHUNKSIZE, "threads": self.THREADS, "RAM": self.RAM,
                "type": self.type}

    # T2P часть (Torrent to peer)
    def torrentThread(self):
        self.loop.run_until_complete(self.task)

    def get_pieces(self):
        return self.pieces

    def writeData(self, res):
        self.DOWNLOADED += 1
        self.STORAGE[self.DOWNLOADED] = res
        self.STORAGELIST.append(self.DOWNLOADED)

    # S2P и P2P часть (Server и Peer to peer)
    def S2Pdownloadgenerator(self):
        if self.URL:
            while len(self.STORAGE) < self.RAM * self.CHUNKSIZE:
                try:
                    self.STORAGE[self.DOWNLOADED + 1] = next(self.r)
                    self.STORAGELIST.append(self.DOWNLOADED + 1)
                    self.DOWNLOADED += 1
                except StopIteration:
                    break

    def uploadstatus(self):
        num = self.total_length // self.CHUNKSIZE
        if num > 0:
            num += 1
        if self.total_length > 0:
            num = 1
        if self.UPLOADED < num:
            if len(self.STORAGE) == 0 and self.type == "S2P" and not self.th.is_alive():
                if self.URL:
                    self.th = threading.Thread(target=self.S2Pdownloadgenerator)
                    self.th.start()
                else:
                    pass
            return "alive"
        elif len(self.STORAGELIST) > 0:
            return "alive"
        elif self.UPLOADED < self.DOWNLOADED:
            return "alive"
        elif math.ceil(self.total_length / self.CHUNKSIZE) > self.UPLOADED:
            return "alive"
        return "dead"

    def upload_await(self):
        status = self.uploadstatus()
        if status == "dead":
            return "-1"
        end = int(self.total_length) // self.CHUNKSIZE + 1
        start = time.time()
        while self.UPLOADED < end:
            if self.UPLOADED < self.DOWNLOADED:
                # num = max(self.UPLOADEDLIST) + 1
                # nums = [k for k in self.STORAGE.keys()]
                # num = min(nums)
                if time.time() - start > 20:
                    return "0"
                try:
                    if len(self.STORAGELIST) > 0:
                        self.lock.acquire()
                        num = self.STORAGELIST.pop(0)
                        self.UPLOADED += 1
                        self.lock.release()
                        return str(num)
                except Exception:
                    pass
        return "0"

    def upload(self, count):
        res = self.STORAGE[count]
        del self.STORAGE[count]
        if self.DOWNLOADED == self.UPLOADED:
            self.statuskillflag = True
        return res

    def download_status(self):
        while not (len(self.STORAGE) * self.CHUNKSIZE < self.RAM):
            time.sleep(1)
        return "1"

    def download_chunk(self, data, index):
        self.DOWNLOADED += 1
        self.STORAGE[self.DOWNLOADED if not index else index] = data
        self.STORAGELIST.append(self.DOWNLOADED if not index else index)

    def download_info(self, total_length):
        self.total_length = total_length

    def get_filename(self):
        return self.filename

    def json(self):
        return {"total_length": self.total_length, "DOWNLOADED": self.DOWNLOADED, "UPLOADED": self.UPLOADED,
                "id": self.id, "URL": self.URL, "CHUNKSIZE": self.CHUNKSIZE, "THREADS": self.THREADS,
                "RAM": self.RAM, "type": self.type, "STORAGELIST": self.STORAGELIST,
                "chunks": math.ceil(self.total_length / self.CHUNKSIZE)}


rnums = {}


@app.route("/reg")
def registration():
    nums = list(map(str, range(10)))
    rnum = int("".join(random.sample(nums, 4)))
    while rnum in rnums:
        rnum = int("".join(random.sample(nums, 4)))

    rnums[rnum] = P2PTunnel()
    return str(rnum)


@app.route("/kill/<int:rnum>")
def kill(rnum):
    del rnums[rnum]


@app.route("/gtrns")
def getallrnums():
    if rnums:
        return [k for k, v in rnums.items()]
    else:
        return "0"


@app.route("/start/<int:rnum>")
def start(rnum):
    id = rnum
    Mb = 2 ** 20
    CHUNKSIZE = 4 * Mb
    THREADS = 16
    RAM = 64 * Mb
    FILENAME = ""
    URL = None
    torrentData = None
    args = request.args
    if "CHUNKSIZE" in args:
        CHUNKSIZE = int(args["CHUNKSIZE"])
    if "THREADS" in args:
        THREADS = int(args["THREADS"])
    if "RAM" in args:
        RAM = int(args["RAM"])
    if "FILENAME" in args:
        FILENAME = args["FILENAME"]
    if "URL" in args:
        URL = args["URL"]
    if request.data:
        torrentData = request.data
    res = rnums[id].init(id, CHUNKSIZE, THREADS, RAM, FILENAME, URL, torrentData)
    return str(res)


@app.route("/downloadStatus/<int:rnum>")
def download_status(rnum):
    try:
        status = rnums[rnum].uploadstatus()
    except KeyError:
        return "dead"
    if status == "dead" and rnums[rnum].statuskillflag:
        rnums[rnum].statuskillflag = False
        time.sleep(5)
        kill(rnum)
    return status


@app.route("/awaitChunk/<int:rnum>")
def await_chunk(rnum):
    return rnums[rnum].upload_await()


@app.route("/downloadChunk/<int:rnum>/<int:count>")
def download_chunk(rnum, count):
    return rnums[rnum].upload(count)


@app.route("/uploadInfo/<int:rnum>", methods=['GET', 'POST'])
def upload_info(rnum):
    total_length = int(request.args["total_length"])
    rnums[rnum].download_info(total_length)
    return "0"


@app.route("/uploadChunk/<int:rnum>", methods=['GET', 'POST'])
def upload_chunk(rnum):
    data = request.data
    rnums[rnum].download_chunk(data)
    return "0"


@app.route("/uploadStatus/<int:rnum>")
def upload_status(rnum):
    return rnums[rnum].download_status()


@app.route("/getFilename/<int:rnum>")
def get_filename(rnum):
    return rnums[rnum].get_filename()


@app.route("/info/<int:rnum>")
def get_info(rnum):
    return rnums[rnum].json()


@app.route("/logs/<int:rnum>")
def logs(rnum):
    return rnums[rnum].json()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
