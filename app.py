import os
import time
import string
import random
import requests
import threading
from flask import Flask, request


app = Flask(__name__)


@app.route("/")
def about():
    return "p2p-tunnel v3"


class P2PTunnel:
    total_length = 0
    STORAGE = {}
    DOWNLOADED = 0
    UPLOADED = 0
    
    def json(self):
        return {"total_length": self.total_length, "DOWNLOADED": self.DOWNLOADED, "UPLOADED": self.UPLOADED,
                "id": self.id, "URL": self.URL, "CHUNKSIZE": self.CHUNKSIZE, "THREADS": self.THREADS,
                "RAM": self.RAM, "type": self.type}

    def __init__(self):
        pass

    def init(self, id, CHUNKSIZE=2**20*4, THREADS=16, RAM=2**20*64, URL=None):
        self.id = id
        self.URL = URL
        self.CHUNKSIZE = CHUNKSIZE
        self.THREADS = THREADS
        self.RAM = RAM
        self.numgeneratorg = self.numgenerator()
        self.statuskillflag = True
        self.type = "P2P"
        if self.URL:
            self.type = "S2P"
            self.req = requests.get(URL, verify=False, stream=True)
            headers = self.req.headers
            self.r = self.req.iter_content(self.CHUNKSIZE)
            self.total_length = int(headers["Content-Length"])
            self.th = threading.Thread(target=self.S2Pdownloadgenerator)
            self.th.start()
            return headers
        return {"id": self.id, "URL": self.URL, "chunksize": self.CHUNKSIZE, "threads": self.THREADS, "RAM": self.RAM}

    def numgenerator(self):
        counter = 0
        end = int(self.total_length) // self.CHUNKSIZE + 1
        while counter < end:
            if counter < self.DOWNLOADED:
                counter += 1
                yield counter
            else:
                yield -1

    def S2Pdownloadgenerator(self):
        if self.URL:
            while len(self.STORAGE) < self.RAM * self.CHUNKSIZE:
                try:
                    self.STORAGE[self.DOWNLOADED + 1] = next(self.r)
                    self.DOWNLOADED += 1
                except StopIteration:
                    break

    def uploadstatus(self):
        num = self.total_length // self.CHUNKSIZE
        if num > 0:
            num += 1
        if self.UPLOADED < num:
            if len(self.STORAGE) == 0 and self.type == "S2P" and not self.th.is_alive():
                if self.URL:
                    self.th = threading.Thread(target=self.S2Pdownloadgenerator)
                    self.th.start()
                else:
                    pass
            return "alive"
        return "dead"

    def upload_await(self):
        a = -1
        while a == -1:
            time.sleep(1)
            try:
                a = next(self.numgeneratorg)
            except StopIteration:
                return "0"
        return f"{a}"

    def upload(self, count):
        res = self.STORAGE[count]
        del self.STORAGE[count]
        self.UPLOADED += 1
        return res

    def download_status(self):
        while not (len(self.STORAGE) < self.RAM * self.CHUNKSIZE):
            time.sleep(1)
        return "1"

    def download_chunk(self, data):
        self.STORAGE[self.DOWNLOADED + 1] = data
        self.DOWNLOADED += 1

    def download_info(self, total_length):
        self.total_length = total_length


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


@app.route("/start/<int:rnum>")
def start(rnum):
    id = rnum
    CHUNKSIZE = 2 ** 20 * 4
    THREADS = 16
    RAM = 2 ** 20 * 64
    URL = None
    args = request.args
    if "CHUNSKSIZE" in args:
        CHUNKSIZE = int(args["CHUNKSIZE"])
    if "THREADS" in args:
        THREADS = int(args["THREADS"])
    if "RAM" in args:
        RAM = int(args["RAM"])
    if "URL" in args:
        URL = args["URL"]
    res = rnums[id].init(id, CHUNKSIZE, THREADS, RAM, URL)
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


@app.route("/logs/<int:rnum>")
def logs(rnum):
    return rnums[rnum].json()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
