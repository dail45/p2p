#
# pieces - An experimental BitTorrent client
#
# Copyright 2016 markus.eliasson@gmail.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import errno
import hashlib
import struct
import time

import aiohttp
import random
import logging
import socket
from struct import unpack
from urllib.parse import urlencode, urlparse

import requests

from p2ptorrent.UDPmessage import UdpTrackerConnection, UdpTrackerAnnounce, UdpTrackerAnnounceOutput
import ipaddress
import p2ptorrent.bencoding


class TrackerResponse:
    """
    The response from the tracker after a successful connection to the
    trackers announce URL.

    Even though the connection was successful from a network point of view,
    the tracker might have returned an error (stated in the `failure`
    property).
    """

    def __init__(self, response: dict):
        self.response = response

    @property
    def failure(self):
        """
        If this response was a failed response, this is the error message to
        why the tracker request failed.

        If no error occurred this will be None
        """
        if b'failure reason' in self.response:
            return self.response[b'failure reason'].decode('utf-8')
        return None

    @property
    def interval(self) -> int:
        """
        Interval in seconds that the client should wait between sending
        periodic requests to the tracker.
        """
        return self.response.get(b'interval', 0)

    @property
    def complete(self) -> int:
        """
        Number of peers with the entire file, i.e. seeders.
        """
        return self.response.get(b'complete', 0)

    @property
    def incomplete(self) -> int:
        """
        Number of non-seeder peers, aka "leechers".
        """
        return self.response.get(b'incomplete', 0)

    @property
    def peers(self):
        """
        A list of tuples for each peer structured as (ip, port)
        """
        # The BitTorrent specification specifies two types of responses. One
        # where the peers field is a list of dictionaries and one where all
        # the peers are encoded in a single string
        peers = self.response[b'peers']
        if type(peers) == list:
            # TODO Implement support for dictionary peer list
            logging.debug('Dictionary model peers are returned by tracker')
            raise NotImplementedError()
        else:
            logging.debug('Binary model peers are returned by tracker')

            # Split the string in pieces of length 6 bytes, where the first
            # 4 characters is the IP the last 2 is the TCP port.
            peers = [peers[i:i+6] for i in range(0, len(peers), 6)]

            # Convert the encoded address to a list of tuples
            return [(socket.inet_ntoa(p[:4]), _decode_port(p[4:]))
                    for p in peers]

    def __str__(self):
        return "incomplete: {incomplete}\n" \
               "complete: {complete}\n" \
               "interval: {interval}\n" \
               "peers: {peers}\n".format(
                   incomplete=self.incomplete,
                   complete=self.complete,
                   interval=self.interval,
                   peers=", ".join([x for (x, _) in self.peers]))


class Tracker:
    """
    Представляет подключение к трекеру для данного торрента,
     который находится в состоянии загрузки или заполнения.
    """


    def __init__(self, torrent):
        self.torrent = torrent
        self.result = []
        self.peer_id = _calculate_peer_id()

    def connect(self,
                first,
                uploaded,
                downloaded):
        """
        Makes the announce call to the tracker to update with our statistics
        as well as get a list of available peers to connect to.

        If the call was successful, the list of peers will be updated as a
        result of calling this function.

        :param first: Whether or not this is the first announce call
        :param uploaded: The total number of bytes uploaded
        :param downloaded: The total number of bytes downloaded
        :param result: return mainpeers without thread
        """
        mainpeers = []
        for tracker in self.torrent.announce:
            trackerUrl = tracker[0]
            print(f"Connecting to ({trackerUrl})")
            if str.startswith(trackerUrl, "http"):
                try:
                    peers = self.http_scraper(trackerUrl)
                    if not peers:
                        logging.error(f" Connection to tracker ({trackerUrl}) was failed")
                        continue
                    counter = 0
                    for peer in peers:
                        if peer not in mainpeers:
                            counter += 1
                            mainpeers.append(peer)
                    print(f"was connected {counter} new peers")
                except Exception as e:
                    logging.error("HTTP scraping to {trackerUrl} failed: %s " % e.__str__())

            elif str.startswith(trackerUrl, "udp"):
                try:
                    peers = self.udp_scrapper(trackerUrl)
                    if not peers:
                        logging.error(f" Connection to tracker ({trackerUrl}) was failed")
                        continue
                    counter = 0
                    for peer in peers:
                        if peer not in mainpeers:
                            counter +=1
                            mainpeers.append(peer)
                    print(f"was connected {counter} new peers")
                except Exception as e:
                    logging.error(f"UDP scraping to {trackerUrl} failed: %s " % e.__str__())
        self.result.extend(mainpeers)  # = return mainpeers without thread
        """
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.total_size}
        if first:
            params['event'] = 'started'

        url = self.torrent.announce + '?' + urlencode(params)
        #logging.info('Connecting to tracker at: ' + url)

        async with self.http_client.get(url) as response:
            if not response.status == 200:
                raise ConnectionError('Unable to connect to tracker: status code {}'.format(response.status))
            data = await response.read()
            self.raise_for_error(data)
            TR = TrackerResponse(bencoding.Decoder(data).decode())
            return TR
        """

    def http_scraper(self, url): # url: http tracker url
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'uploaded': 0,
            'downloaded': 0,
            'port': 6889,
            'left': self.torrent.total_size,
            'event': 'started'
        }

        try:
            # print(f"url: {url}")
            response = requests.get(url, timeout=3)
            if not response.status_code == 200:
                raise ConnectionError('Unable to connect to tracker: status code {}'.format(response.status_code))
            data = response.content
            try:
                self.raise_for_error(data)
            except ConnectionError:
                return None
            dictans = bencoding.Decoder(data).decode()
            offset = 0
            peers = []
            if not isinstance(dictans['peers'], dict):
                for _ in range(len(dictans['peers']) // 6):
                    ip = struct.unpack_from("!i", dictans['peers'], offset)[0]
                    ip = socket.inet_ntoa(struct.pack("!i", ip))
                    offset += 4
                    port = struct.unpack_from("!H", dictans['peers'], offset)[0]
                    offset += 2
                    peers.append({'ip': ip,
                                  'port': port})
            else:
                for peer in dictans['peers']:
                    peers.append({'ip': peer[0],
                                  'port': peer[1]})
            return peers

        except Exception as e:
            return
            #logging.exception("HTTP scraping failed: %s" % e.__str__())

    def udp_scrapper(self, announce):
        torrent = self.torrent
        parsed = urlparse(announce)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(4)
        ip, port = socket.gethostbyname(parsed.hostname), parsed.port

        if ipaddress.ip_address(ip).is_private:
            return

        tracker_connection_input = UdpTrackerConnection()
        response = self.send_message((ip, port), sock, tracker_connection_input)

        if not response:
            return
            #raise Exception("No response for UdpTrackerConnection")

        tracker_connection_output = UdpTrackerConnection()
        tracker_connection_output.from_bytes(response)

        tracker_announce_input = UdpTrackerAnnounce(self.torrent.info_hash, tracker_connection_output.conn_id,
                                                    self.peer_id.encode("utf-8"))
        response = self.send_message((ip, port), sock, tracker_announce_input)

        if not response:
            return
            #raise Exception("No response for UdpTrackerAnnounce")

        tracker_announce_output = UdpTrackerAnnounceOutput()
        tracker_announce_output.from_bytes(response)

        peers = []
        for ip, port in tracker_announce_output.list_sock_addr:
            peer = {'ip': ip,
                    'port': port}

            peers.append(peer)
        return peers

    def send_message(self, conn, sock, tracker_message):
        def _read_from_socket(sock):
            data = b''

            while True:
                try:
                    buff = sock.recv(4096)
                    if len(buff) <= 0:
                        break

                    data += buff
                except socket.error as e:
                    err = e.args[0]
                    if err != errno.EAGAIN or err != errno.EWOULDBLOCK:
                        logging.debug("Wrong errno {}".format(err))
                    break
                except Exception:
                    logging.exception("Recv failed")
                    break

            return data

        message = tracker_message.to_bytes()
        trans_id = tracker_message.trans_id
        action = tracker_message.action
        size = len(message)

        sock.sendto(message, conn)

        try:
            response = _read_from_socket(sock)
        except socket.timeout as e:
            logging.debug("Timeout : %s" % e)
            return
        except Exception as e:
            logging.exception("Unexpected error when sending message : %s" % e.__str__())
            return

        if len(response) < size:
            logging.debug("Did not get full message.")

        if action != response[0:4] or trans_id != response[4:8]:
            logging.debug("Transaction or Action ID did not match")

        return response

    def close(self):
        self.http_client.close()

    def raise_for_error(self, tracker_response):
        """
        A (hacky) fix to detect errors by tracker even when the response has a status code of 200  
        """
        try:
            # a tracker response containing an error will have a utf-8 message only.
            # see: https://wiki.theory.org/index.php/BitTorrentSpecification#Tracker_Response
            message = tracker_response.decode("utf-8")
            if "failure" in message:
                raise ConnectionError('Unable to connect to tracker: {}'.format(message))

        # a successful tracker response will have non-uncicode data, so it's a safe to bet ignore this exception.
        except UnicodeDecodeError:
            pass

    def _construct_tracker_parameters(self):
        """
        Constructs the URL parameters used when issuing the announce call
        to the tracker.
        """
        return {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6889,
            # TODO Update stats when communicating with tracker
            'uploaded': 0,
            'downloaded': 0,
            'left': 0,
            'compact': 1}


def _calculate_peer_id():
    """
    Calculate and return a unique Peer ID.

    The `peer id` is a 20 byte long identifier. This implementation use the
    Azureus style `-PC1000-<random-characters>`.

    Read more:
        https://wiki.theory.org/BitTorrentSpecification#peer_id
    """
    # return hashlib.sha1(str(time.time()).encode("utf-8")).digest()
    return '-UT0185-' + ''.join([str(random.randint(0, 9)) for _ in range(12)])


def _decode_port(port):
    """
    Converts a 32-bit packed binary port number to int
    """
    # Convert from C style big-endian encoded as unsigned short
    return unpack(">H", port)[0]


if __name__ == '__main__':
    from p2ptorrent import torrent
    with open("4.torrent", "rb") as f:
        data = f.read()
    torrent1 = torrent.Torrent(data)
    tracker = Tracker(torrent1)

    for i in tracker.torrent.announce:
        try:
            tracker.udp_scrapper(i[0])
        except Exception as f:
            print(f"ERROR: {f}")


