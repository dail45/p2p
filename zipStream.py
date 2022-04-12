import ctypes
import datetime
import hashlib
import math
import time
from copy import deepcopy
from ctypes import *
from pprint import pprint

EOCDR_BASE_SZ = 22
EOCDR_SIGNATURE = c_uint32(0x06054b50)


class EndOfCentralDirectory(Structure):
    _fields_ = [
        ("disk_nbr", c_uint16),         # Number of this disk.
        ("cd_start_disk", c_uint16),    # Nbr. of disk with start of the CD.
        ("disk_cd_entries", c_uint16),  # Nbr. of CD entries on this disk.
        ("cd_entries", c_uint16),       # Nbr. of Central Directory entries.
        ("cd_size", c_uint32),          # Central Directory size in bytes.
        ("cd_offset", c_uint32),        # Central Directory file offset.
        ("comment_len", c_uint16),      # Archive comment length.
        ("comment", c_uint8)            # Archive comment. (Pointer)
    ]


def write_eocdr(eocdr: EndOfCentralDirectory):
    res = b""
    res += EOCDR_SIGNATURE
    res += c_uint16(eocdr.disk_nbr)
    res += c_uint16(eocdr.cd_start_disk)
    res += c_uint16(eocdr.disk_cd_entries)
    res += c_uint16(eocdr.cd_entries)
    res += c_uint32(eocdr.cd_size)
    res += c_uint32(eocdr.cd_offset)
    res += c_uint16(eocdr.comment_len)
    return res


CFH_BASE_SZ = 46
CFH_SIGNATURE = c_uint32(0x02014b50)


class CentalFileHeader(Structure):
    _fields_ = [
        ("made_by_ver", c_uint16),     # Version made by.
        ("extract_ver", c_uint16),     # Version needed to extract.
        ("gp_flag", c_uint16),         # General purpose bit flag.
        ("method", c_uint16),          # Compression method.
        ("mod_time", c_uint16),        # Modification time.
        ("mod_date", c_uint16),        # Modification date.
        ("crc32", c_uint32),           # CRC-32 checksum.
        ("comp_size", c_uint32),       # Compressed size.
        ("uncomp_size", c_uint32),     # Uncompressed size.
        ("name_len", c_uint16),        # Filename length.
        ("extra_len", c_uint16),       # Extra data length.
        ("comment_len", c_uint16),     # Comment length.
        ("disk_nbr_start", c_uint16),  # Disk nbr. where file begins.
        ("int_attrs", c_uint16),       # Internal file attributes.
        ("ext_attrs", c_uint32),       # External file attributes.
        ("lfh_offset", c_uint32),      # Local File Header offset.
        ("name", c_uint8),             # Filename. (Pointer)
        ("extra", c_uint8),            # Extra data. (Pointer)
        ("comment", c_uint8)           # File comment. (Pointer)
    ]


def write_cfh(cfh: CentalFileHeader, zipStream):
    res = b""
    res += CFH_SIGNATURE
    res += c_uint16(cfh.made_by_ver)
    res += c_uint16(cfh.extract_ver)
    res += c_uint16(cfh.gp_flag)
    res += c_uint16(cfh.method)
    res += c_uint16(cfh.mod_time)
    res += cfh.mod_data.to_bytes(2, "little")
    res += c_uint32(cfh.crc32)
    res += c_uint32(cfh.comp_size)
    res += c_uint32(cfh.uncomp_size)
    res += c_uint16(cfh.name_len)
    res += c_uint16(cfh.extra_len)
    res += c_uint16(cfh.comment_len)
    res += c_uint16(cfh.disk_nbr_start)
    res += c_uint16(cfh.int_attrs)
    res += c_uint32(cfh.ext_attrs)
    res += c_uint32(cfh.lfh_offset)
    res += zipStream.parent.filenames[cfh.index].encode("UTF-8")
    return res


LFH_BASE_SZ = 30
LFH_SIGNATURE = c_uint32(0x04034b50)


class LocalFileHeader(Structure):
    _fields_ = [
        ("extract_ver", c_uint16),     # Version needed to extract.
        ("gp_flag", c_uint16),         # General purpose bit flag.
        ("method", c_uint16),          # Compression method.
        ("mod_time", c_uint16),        # Modification time.
        ("mod_date", c_uint16),        # Modification date.
        ("crc32", c_uint32),           # CRC-32 checksum.
        ("comp_size", c_uint32),       # Compressed size.
        ("uncomp_size", c_uint32),     # Uncompressed size.
        ("name_len", c_uint16),        # Filename length.
        ("extra_len", c_uint16),       # Extra data length.
        ("name", c_uint8),             # Filename. (Pointer)
        ("extra", c_uint8)             # Extra data. (Pointer)
    ]


def write_lfh(lfh: LocalFileHeader, zipStream):
    res = b""
    res += LFH_SIGNATURE
    res += c_uint16(lfh.extract_ver)
    res += c_uint16(lfh.gp_flag)
    res += c_uint16(lfh.method)
    res += c_uint16(lfh.mod_time)
    res += lfh.mod_data.to_bytes(2, "little")
    res += c_uint32(lfh.crc32)
    res += c_uint32(lfh.comp_size)
    res += c_uint32(lfh.uncomp_size)
    res += c_uint16(lfh.name_len)
    res += c_uint16(lfh.extra_len)
    res += zipStream.parent.filenames[lfh.index].encode("UTF-8")
    return res


def convert_secs_to_dos(t):
    lt = time.localtime(t)
    dos_time = 0
    dos_data = 0
    dos_time |= math.ceil(lt.tm_sec / 2)
    dos_time |= lt.tm_min << 5
    dos_time |= lt.tm_hour << 11

    dos_data |= lt.tm_mday << (16 - 16)
    dos_data |= lt.tm_mon << (21 - 16)
    dos_data |= (lt.tm_year - 1980) << (25 - 16)

    return dos_time, dos_data


def getStructureSizeFromCountOfFiles(count):
    return (LFH_BASE_SZ + CFH_BASE_SZ) * count + EOCDR_BASE_SZ


class ZipStream:
    def __init__(self, parent):
        self.parent = parent
        self.STORAGE = b""
        self.storage = {}
        self.Hashes = {}
        self.localstorage = b""  # delete this
        self.last = []
        self.filesEnd = False
        self.counter = -1
        self.filecounter = 0
        self.localcounter = 0
        self.written = {k: 0 for k in range(len(self.parent.total_lengths))}
        self.structures = self.createStructures()
        self.eocdr = EndOfCentralDirectory()
        self.total_length = 0

    def createStructures(self):
        res = {}
        for index in range(len(self.parent.total_lengths)):
            res[index] = [LocalFileHeader(), CentalFileHeader()]
        return res

    def getTotalLength(self):
        return self.total_length

    def getTotalChunks(self):
        return math.ceil(self.getTotalLength() / self.parent.chunksize)

    def getFileName(self):
        return "untitled.zip"

    def awaitChunk(self):
        if not self.last:
            copy = deepcopy(self.parent.STORAGELIST)
            copy = sorted(copy, key=lambda x: (x[0], x[1]))
            if copy[0] == (self.filecounter, self.localcounter):
                self.last = copy[0]
                self.parent.STORAGELIST.remove(copy[0])
            else:
                return -1
            self.STORAGE += write_lfh(self.structures[0][0], self)
            data = self.parent.STORAGE[self.last[0]].pop(self.last[1] + 1)
            self.STORAGE += data
            self.written[self.last[0]] += len(data)
            self.localcounter += 1
            counter = self.makeChunk()
            if counter == -1:
                return -2
            return counter
        else:
            if self.written[self.filecounter] == self.parent.total_lengths[self.filecounter]:
                if self.filecounter + 1 == len(self.parent.total_lengths):
                    if self.filesEnd is False:
                        for findex in range(len(self.parent.total_lengths)):
                            self.STORAGE += write_cfh(self.structures[findex][1], self)
                        self.STORAGE += write_eocdr(self.eocdr)
                    self.filesEnd = True
                    counter = self.makeChunk(forced=True)
                    if counter == -1:
                        return -3
                    return counter
                self.filecounter += 1
                self.localcounter = 0
                self.STORAGE += write_lfh(self.structures[self.filecounter][0], self)
            copy = deepcopy(self.parent.STORAGELIST)
            copy = sorted(copy, key=lambda x: (x[0], x[1]))
            if copy[0] == (self.filecounter, self.localcounter):
                self.last = copy[0]
                self.parent.STORAGELIST.remove(copy[0])
            else:
                return -4
            data = self.parent.STORAGE[self.last[0]].pop(self.last[1] + 1)
            self.STORAGE += data
            self.written[self.last[0]] += len(data)
            self.localcounter += 1
            counter = self.makeChunk()
            if counter == -1:
                return -5
            return counter

    def makeChunk(self, forced=False):
        if len(self.STORAGE) >= self.parent.chunksize or forced:
            if len(self.STORAGE) == 0:
                return -1
            self.counter += 1
            self.storage[self.counter] = self.STORAGE[:self.parent.chunksize]
            self.STORAGE = self.STORAGE[self.parent.chunksize:]
            self.Hashes[self.counter] = hashlib.sha1(self.storage[self.counter]).hexdigest()
            return self.counter
        return -1

    def removeChunk(self, index):
        self.storage.pop(index)

    def getChunk(self, counter):
        return self.storage[counter]

    def getHash(self, index):
        return self.Hashes[index]

    def is_alive(self):
        return len(self.STORAGE) > 0 or not self.filesEnd

    def updateFileHeaders(self, jsonin):
        cfh_size = 0
        cfh_offset = 0
        for index in range(len(self.structures)):
            structure = self.structures[index]
            structure[0].extract_ver = int(jsonin["extract_ver"])
            structure[0].gp_flag = int(jsonin["gp_flag"])
            structure[0].method = int(jsonin["method"])
            # pprint(jsonin["files"])
            # pprint(jsonin["files"][str(index)])
            # pprint(jsonin["files"][str(index)]["mktime"])
            dos_time, dos_data = convert_secs_to_dos(int(jsonin["files"][str(index)]["mktime"]))

            structure[0].mod_time = dos_time
            structure[0].mod_data = dos_data
            structure[0].crc32 = int(jsonin["files"][str(index)]["crc32"])
            structure[0].comp_size = int(jsonin["files"][str(index)]["comp_size"])
            structure[0].uncomp_size = int(jsonin["files"][str(index)]["uncomp_size"])
            structure[0].name_len = int(jsonin["files"][str(index)]["name_len"])
            structure[0].extra_len = 0
            structure[0].index = index

            structure[1].made_by_ver = int(jsonin["made_by_ver"])
            structure[1].extract_ver = int(jsonin["extract_ver"])
            structure[1].gp_flag = int(jsonin["gp_flag"])
            structure[1].method = int(jsonin["method"])
            dos_time, dos_data = convert_secs_to_dos(int(jsonin["files"][str(index)]["mktime"]))
            structure[1].mod_time = dos_time
            structure[1].mod_data = dos_data
            structure[1].crc32 = int(jsonin["files"][str(index)]["crc32"])
            structure[1].comp_size = int(jsonin["files"][str(index)]["comp_size"])
            structure[1].uncomp_size = int(jsonin["files"][str(index)]["uncomp_size"])
            structure[1].name_len = int(jsonin["files"][str(index)]["name_len"])
            structure[1].extra_len = 0
            structure[1].comment_len = 0
            structure[1].disk_nbr_start = 0
            structure[1].int_attrs = 0
            structure[1].ext_attrs = 0
            structure[1].lfh_offset = cfh_offset
            structure[1].index = index

            cfh_size += len(write_cfh(structure[1], self))
            cfh_offset += len(write_lfh(structure[0], self))
            cfh_offset += self.parent.total_lengths[index]

        self.eocdr.disk_nbr = 0
        self.eocdr.cd_start_disk = 0
        self.eocdr.disk_cd_entries = len(self.structures)
        self.eocdr.cd_entries = len(self.structures)

        self.eocdr.cd_size = cfh_size
        self.eocdr.cd_offset = cfh_offset
        self.eocdr.comment_len = 0

        self.total_length = cfh_offset + cfh_size + len(write_eocdr(self.eocdr))
