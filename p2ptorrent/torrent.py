from collections import namedtuple
from hashlib import sha1
import bencoding
import random
import socket
import struct


TorrentFile = namedtuple('TorrentFile', ['name', 'length'])


class SendDNSPkt:
    def __init__(self, url, serverIP, port=53):
        self.url = url
        self.serverIP = serverIP
        self.port = port

    def sendPkt(self):
        pkt = self._build_packet()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        sock.sendto(bytes(pkt), (self.serverIP, self.port))
        data, addr = sock.recvfrom(1024)
        sock.close()
        return data

    def _build_packet(self):
        randint = random.randint(0, 65535)
        packet = struct.pack(">H", randint)  # Query Ids (Just 1 for now)
        packet += struct.pack(">H", 0x0100)  # Flags
        packet += struct.pack(">H", 1)  # Questions
        packet += struct.pack(">H", 0)  # Answers
        packet += struct.pack(">H", 0)  # Authorities
        packet += struct.pack(">H", 0)  # Additional
        split_url = self.url.split(".")
        for part in split_url:
            packet += struct.pack("B", len(part))
            for s in part:
                packet += struct.pack('c',s.encode())
        packet += struct.pack("B", 0)  # End of String
        packet += struct.pack(">H", 1)  # Query Type
        packet += struct.pack(">H", 1)  # Query Class
        return packet


def checkDNSPortOpen(url):
    # replace 8.8.8.8 with your server IP!
    s = SendDNSPkt('www.google.com', )
    portOpen = False
    for _ in range(5): # udp is unreliable.Packet loss may occur
        try:
            s.sendPkt()
            portOpen = True
            break
        except socket.timeout:
            pass
    if portOpen:
        print('port open!')
    else:
        print('port closed!')


class Torrent:
    """
    Represent the p2ptorrent meta-data that is kept within a .p2ptorrent file. It is
    basically just a wrapper around the bencoded data with utility functions.

    This class does not contain any session state as part of the download.
    """
    def __init__(self, data):
        self.files = []

        meta_info = data
        self.meta_info = bencoding.Decoder(meta_info).decode()
        info = bencoding.Encoder(self.meta_info[b'info']).encode()
        self.info_hash = sha1(info).digest()
        self._identify_files()

    def _identify_files(self):
        """
        Identifies the files included in this p2ptorrent
        """
        if self.multi_file:
            for file in self.meta_info[b'info'][b'files']:
                self.files.append(
                    TorrentFile(
                        file[b'path'][0].decode("utf-8"),
                        file[b'length']))
            # TODO Add support for multi-file torrents
            #raise RuntimeError('Multi-file torrents is not supported!')
        else:
            self.files.append(
                TorrentFile(
                    self.meta_info[b'info'][b'name'].decode('utf-8'),
                    self.meta_info[b'info'][b'length']))

    @property
    def announce(self) -> str:
        """
        The announce URL to the tracker.
        """
        if b'announce-list' in self.meta_info:
            return [[i[0].decode('utf-8')] for i in self.meta_info[b'announce-list']]
        return [self.meta_info[b'announce'].decode('utf-8')]

    @property
    def multi_file(self) -> bool:
        """
        Does this p2ptorrent contain multiple files?
        """
        # If the info dict contains a files element then it is a multi-file
        return b'files' in self.meta_info[b'info']

    @property
    def piece_length(self) -> int:
        """
        Get the length in bytes for each piece
        """
        return self.meta_info[b'info'][b'piece length']

    @property
    def total_size(self) -> int:
        """
        The total size (in bytes) for all the files in this p2ptorrent. For a
        single file p2ptorrent this is the only file, for a multi-file p2ptorrent
        this is the sum of all files.

        :return: The total size (in bytes) for this p2ptorrent's data.
        """
        #if self.multi_file:
        #    raise RuntimeError('Multi-file torrents is not supported!')
        #return self.files[0].length
        return sum([i.length for i in self.files])

    @property
    def pieces(self):
        # The info pieces is a string representing all pieces SHA1 hashes
        # (each 20 bytes long). Read that data and slice it up into the
        # actual pieces
        data = self.meta_info[b'info'][b'pieces']
        pieces = []
        offset = 0
        length = len(data)

        while offset < length:
            pieces.append(data[offset:offset + 20])
            offset += 20
        return pieces

    @property
    def output_file(self):
        return self.meta_info[b'info'][b'name'].decode('utf-8')

    def __str__(self):
        return 'Filename: {0}\n' \
               'File length: {1}\n' \
               'Announce URL: {2}\n' \
               'Hash: {3}'.format(self.meta_info[b'info'][b'name'],
                                  self.meta_info[b'info'][b'length'],
                                  self.meta_info[b'announce'],
                                  self.info_hash)
