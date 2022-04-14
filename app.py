import socket, os

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("", int(os.environ.get("PORT", 8000))))
sock.listen(16)
conn, addr = sock.accept()
while True:
    ln = conn.recv(8)
    print(f"msg len: {int.from_bytes(ln, 'big')}")
    msg = conn.recv(int.from_bytes(ln, "big"))
    print(f"msg: {msg}")
