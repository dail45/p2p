import time

from flask import Flask, request
import requests
import os

app = Flask(__name__)

flagUpLoad = True
flagDownLoad = False
countfiles = 0
file = b""

@app.route("/")
def fun():
    return "Вроде работает."

@app.route('/upload', methods=['POST'])
def upload():
    global file, flagDownLoad
    file = request.data
    flagDownLoad = True
    return "1"

@app.route('/download')
def download():
    return file

@app.route('/accessupload/<int:count>', methods=['GET'])
def get_access_upload(count):
    global countfiles, flagUpLoad
    if flagUpLoad:
        countfiles = count
        flagUpLoad = not flagUpLoad
        return "1"
    return "0"

@app.route('/accessdownload')
def get_access_download():
    global flagDownLoad, flagUpLoad
    if flagDownLoad:
        flagDownLoad = not flagDownLoad
        return {"status": 1, "count": countfiles}
    else:
        flagUpLoad = True
        return {"status": 0}


@app.route("/restart")
def restart():
    global flagDownLoad, flagUpLoad, countfiles, file
    flagUpLoad = True
    flagDownLoad = False
    countfiles = 0
    file = b""
    return "restart done"


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
