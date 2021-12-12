import hashlib
import random
import socket
import time
from struct import pack, unpack


class Message:
    def to_bytes(self):
        raise NotImplementedError()

    @classmethod
    def from_bytes(cls, payload):
        raise NotImplementedError()


"""
UDP Tracker
"""


class UdpTrackerConnection(Message):
    """
        connect = <connection_id><action><transaction_id>
            - connection_id = 64-bit integer
            - action = 32-bit integer
            - transaction_id = 32-bit integer

        Total length = 64 + 32 + 32 = 128 bytes
    """

    def __init__(self):
        super(UdpTrackerConnection, self).__init__()
        self.conn_id = pack('>Q', 0x41727101980)
        self.action = pack('>I', 0)
        self.trans_id = pack('>I', random.randint(0, 100000))

    def to_bytes(self):
        return self.conn_id + self.action + self.trans_id

    def from_bytes(self, payload):
        self.action, = unpack('>I', payload[:4])
        self.trans_id, = unpack('>I', payload[4:8])
        self.conn_id, = unpack('>Q', payload[8:])


class UdpTrackerAnnounce(Message):
    """
        connect = <connection_id><action><transaction_id>

        0	64-bit integer	connection_id
8	32-bit integer	action	1
12	32-bit integer	transaction_id
16	20-byte string	info_hash
36	20-byte string	peer_id
56	64-bit integer	downloaded
64	64-bit integer	left
72	64-bit integer	uploaded
80	32-bit integer	event
84	32-bit integer	IP address	0
88	32-bit integer	key
92	32-bit integer	num_want	-1
96	16-bit integer	port

            - connection_id = 64-bit integer
            - action = 32-bit integer
            - transaction_id = 32-bit integer

        Total length = 64 + 32 + 32 = 128 bytes
    """

    def __init__(self, info_hash, conn_id, peer_id):
        super(UdpTrackerAnnounce, self).__init__()
        self.peer_id = peer_id
        self.conn_id = conn_id
        self.info_hash = info_hash
        self.trans_id = pack('>I', random.randint(0, 100000))
        self.action = pack('>I', 1)

    def to_bytes(self):
        conn_id = pack('>Q', self.conn_id)
        action = self.action
        trans_id = self.trans_id
        downloaded = pack('>Q', 0)
        left = pack('>Q', 0)
        uploaded = pack('>Q', 0)

        event = pack('>I', 0)
        ip = pack('>I', 0)
        key = pack('>I', 0)
        num_want = pack('>i', -1)
        port = pack('>h', 8000)

        #for i in (conn_id, action, trans_id, self.info_hash, self.peer_id, downloaded,
        #       left, uploaded, event, ip, key, num_want, port):
        #    print(i, type(i))

        msg = (conn_id + action + trans_id + self.info_hash + self.peer_id + downloaded +
               left + uploaded + event + ip + key + num_want + port)

        return msg


class UdpTrackerAnnounceOutput:
    """
        connect = <connection_id><action><transaction_id>

0	32-bit integer	action	1
4	32-bit integer	transaction_id
8	32-bit integer	interval
12	32-bit integer	leechers
16	32-bit integer	seeders
20 + 6 * n	32-bit integer	IP address
24 + 6 * n	16-bit integer	TCP port
20 + 6 * N

    """

    def __init__(self):
        self.action = None
        self.transaction_id = None
        self.interval = None
        self.leechers = None
        self.seeders = None
        self.list_sock_addr = []

    def from_bytes(self, payload):
        self.action, = unpack('>I', payload[:4])
        self.transaction_id, = unpack('>I', payload[4:8])
        self.interval, = unpack('>I', payload[8:12])
        self.leechers, = unpack('>I', payload[12:16])
        self.seeders, = unpack('>I', payload[16:20])
        self.list_sock_addr = self._parse_sock_addr(payload[20:])

    def _parse_sock_addr(self, raw_bytes):
        socks_addr = []

        # socket address : <IP(4 bytes)><Port(2 bytes)>
        # len(socket addr) == 6 bytes
        for i in range(int(len(raw_bytes) / 6)):
            start = i * 6
            end = start + 6
            ip = socket.inet_ntoa(raw_bytes[start:(end - 2)])
            raw_port = raw_bytes[(end - 2):end]
            port = raw_port[1] + raw_port[0] * 256

            socks_addr.append((ip, port))

        return socks_addr
