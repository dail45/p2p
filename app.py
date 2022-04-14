import socket, os, flask


app = flask.Flask(__name__)


@app.route("/")
def about():
    return str(os.environ.get("PORT", 8000))


@app.route("/cs")
def create_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", int(os.environ.get("PORT", 8000))))
    sock.listen(16)
    conn, addr = sock.accept()
    while True:
        ln = int.from_bytes(conn.recv(8), "big")
        if ln == 0:
            continue
        msg = conn.recv(ln)
        print(f"msg: {msg}")


app.run("0.0.0.0", port=int(os.environ.get("PORT", 8000)))
