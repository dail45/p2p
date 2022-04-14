import socket, os

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("", int(os.environ.get("PORT", 8000))))
sock.listen(16)
conn, addr = sock.accept()
print(int(os.environ.get("PORT", 8000)))
while True:
    ln = int.from_bytes(conn.recv(8), "big")
    if ln == 0:
        continue
    msg = conn.recv(ln)
    print(f"msg: {msg}")
