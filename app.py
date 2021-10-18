import time
import threading
from flask import Flask, request
import requests
import os
import urllib3

app = Flask(__name__)


def generator_chunks_number():
    counter = 0
    end = int(total_length) // (chunk_size) + 1
    while counter < end:
        if counter < file_chunks["counter"]:
            counter += 1
            print(file_chunks.keys(), file_chunks["counter"])
            yield counter
        else:
            yield -1


download_link = ""
file_chunks = {"counter": 0, "counter_upload": 0}
total_length = 0
chunk_size = 4*1024*1024
THREADS = 16
file_chunks_number_gen = None


@app.route("/")
def fun():
    return "Ok."


@app.route("/download")
def download():
    global download_link, total_length, file_chunks_number_gen, chunk_size, THREADS
    if download_status() == "alive":
        return "0"
    restart()
    download_link = request.args["public_key"]
    if "Chunk-Size" in request.args:
        chunk_size = int(request.args["Chunk-Size"])
    else:
        chunk_size = 4*1024*1024
    if "Threads" in request.args:
        THREADS = int(request.args["Threads"])
    else:
        THREADS = 16
    data = requests.get(download_link, stream=True)
    ret = data.headers
    total_length = int(ret["Content-Length"])
    data.close()
    a = threading.Thread(target=generage_download_file_chunks)
    a.start()
    file_chunks_number_gen = generator_chunks_number()
    return str(ret)


def generage_download_file_chunks():
    global file_chunks
    #http = urllib3.PoolManager()
    #r = http.urlopen("GET", download_link, preload_content=False, verify=False)
    #r.auto_close = False
    time.sleep(5)
    r = requests.get(download_link, verify=False, stream=True)
    generator = r.iter_content(chunk_size)
    while True:
        if len(file_chunks) < ((THREADS * chunk_size) // chunk_size) + 2:
            try:
                file_chunks[file_chunks["counter"] + 1] = next(generator)
                file_chunks["counter"] += 1
            except StopIteration:
                break


@app.route("/await_chunk/<int:count>")
def await_chunk(count):
    global file_chunks
    a = next(file_chunks_number_gen)
    if a == -1:
        return "0"
    return f"{a}"


@app.route("/download_chunk/<int:count>")
def download_chunk(count):
    global file_chunks
    res = file_chunks[count]
    del file_chunks[count]
    file_chunks["counter_upload"] += 1
    return res


@app.route("/downloadStatus")
def download_status():
    num = total_length // chunk_size
    if num > 0:
        num += 1
    if file_chunks["counter_upload"] < num:
        return "alive"
    return "dead"


@app.route("/restart")
def restart():
    global download_link, file_chunks, total_length, file_chunks_number_gen
    download_link = ""
    file_chunks = {"counter": 0, "counter_upload": 0}
    total_length = 0
    file_chunks_number_gen = None
    chunk_size = 4 * 1024 * 1024
    return "restart done"


@app.route("/log")
def log():
    return str({"download_link": download_link,
            "file_chunks": file_chunks.keys(),
            "file_chunks['counter']": file_chunks["counter"],
            "total_length": total_length,
            "file_chunks_number_gen": file_chunks_number_gen})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
