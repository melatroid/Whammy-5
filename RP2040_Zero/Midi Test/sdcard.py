# sdcard.py

from micropython import const
import time
import os
import json

_CMD_TIMEOUT = const(100)

_R1_IDLE_STATE = const(1 << 0)
_TOKEN_DATA = const(0xFE)

_CMD0 = const(0)
_CMD8 = const(8)
_CMD9 = const(9)
_CMD10 = const(10)
_CMD12 = const(12)
_CMD16 = const(16)
_CMD17 = const(17)
_CMD18 = const(18)
_CMD23 = const(23)
_CMD24 = const(24)
_CMD25 = const(25)
_CMD55 = const(55)
_CMD58 = const(58)

_ACMD41 = const(41)


class SDCard:
    def __init__(self, spi, cs, baudrate=10_000_000):
        self.spi = spi
        self.cs = cs
        self.cs.init(self.cs.OUT, value=1)

        self.cmdbuf = bytearray(6)
        self.tokenbuf = bytearray(1)
        self.dummybuf = bytearray(512)
        self.dummybufmv = memoryview(self.dummybuf)

        self.sectors = 0
        self.cdv = 512  # sector size divisor (1 for SDHC/SDXC, 512 for SDSC)

        self.init_card(baudrate)

    def init_card(self, baudrate):
        self.spi.init(baudrate=100_000, polarity=0, phase=0)
        self.cs.value(1)

        for _ in range(16):
            self.spi.write(b"\xFF")

        for _ in range(5):
            if self.cmd(_CMD0, 0, 0x95) == _R1_IDLE_STATE:
                break
        else:
            raise OSError("SD init failed: CMD0")

        r = self.cmd(_CMD8, 0x1AA, 0x87, release=False)
        r7 = bytearray(4)
        self.spi.readinto(r7, 0xFF)
        self.cs.value(1)
        self.spi.write(b"\xFF")

        sd_v2 = (r == _R1_IDLE_STATE and r7[2] == 0x01 and r7[3] == 0xAA)

        for _ in range(1000):
            self.cmd(_CMD55, 0, 0x01)
            r = self.cmd(_ACMD41, 0x40000000 if sd_v2 else 0, 0x01)
            if r == 0:
                break
            time.sleep_ms(10)
        else:
            raise OSError("SD init failed: ACMD41 timeout")

        r = self.cmd(_CMD58, 0, 0x01, release=False)
        ocr = bytearray(4)
        self.spi.readinto(ocr, 0xFF)
        self.cs.value(1)
        self.spi.write(b"\xFF")

        if r != 0:
            raise OSError("SD init failed: CMD58")

        if sd_v2 and (ocr[0] & 0x40):
            self.cdv = 1
        else:
            self.cdv = 512

        if self.cdv != 1:
            if self.cmd(_CMD16, 512, 0x01) != 0:
                raise OSError("SD init failed: CMD16")

        self.spi.init(baudrate=baudrate, polarity=0, phase=0)

        try:
            self.sectors = self._read_sectors_count()
        except:
            self.sectors = 0

    def _wait_ready(self):
        for _ in range(_CMD_TIMEOUT * 100):
            if self.spi.read(1, 0xFF)[0] == 0xFF:
                return True
        return False

    def cmd(self, cmd, arg, crc, release=True):
        self.cs.value(0)
        self.spi.write(b"\xFF")

        if not self._wait_ready():
            self.cs.value(1)
            self.spi.write(b"\xFF")
            return 0xFF

        self.cmdbuf[0] = 0x40 | cmd
        self.cmdbuf[1] = (arg >> 24) & 0xFF
        self.cmdbuf[2] = (arg >> 16) & 0xFF
        self.cmdbuf[3] = (arg >> 8) & 0xFF
        self.cmdbuf[4] = arg & 0xFF
        self.cmdbuf[5] = crc

        self.spi.write(self.cmdbuf)

        for _ in range(_CMD_TIMEOUT):
            r = self.spi.read(1, 0xFF)[0]
            if r & 0x80 == 0:
                break
        else:
            r = 0xFF

        if release:
            self.cs.value(1)
            self.spi.write(b"\xFF")

        return r

    def _readinto(self, buf):
        for _ in range(_CMD_TIMEOUT * 100):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == _TOKEN_DATA:
                break
        else:
            raise OSError("SD read timeout")

        self.spi.readinto(buf, 0xFF)
        self.spi.write(b"\xFF\xFF")

    def _write(self, buf):
        self.spi.write(b"\xFE")
        self.spi.write(buf)
        self.spi.write(b"\xFF\xFF")

        resp = self.spi.read(1, 0xFF)[0]
        if (resp & 0x1F) != 0x05:
            raise OSError("SD write rejected")

        while self.spi.read(1, 0xFF)[0] == 0:
            pass

    def _read_csd(self):
        csd = bytearray(16)
        if self.cmd(_CMD9, 0, 0x01, release=False) != 0:
            self.cs.value(1)
            self.spi.write(b"\xFF")
            raise OSError("CMD9 failed")
        self._readinto(csd)
        self.cs.value(1)
        self.spi.write(b"\xFF")
        return csd

    def _read_sectors_count(self):
        csd = self._read_csd()
        csd_structure = (csd[0] >> 6) & 0x03

        if csd_structure == 1:
            c_size = ((csd[7] & 0x3F) << 16) | (csd[8] << 8) | csd[9]
            return (c_size + 1) * 1024
        else:
            c_size = ((csd[6] & 0x03) << 10) | (csd[7] << 2) | ((csd[8] >> 6) & 0x03)
            c_size_mult = ((csd[9] & 0x03) << 1) | ((csd[10] >> 7) & 0x01)
            read_bl_len = csd[5] & 0x0F
            block_len = 1 << read_bl_len
            mult = 1 << (c_size_mult + 2)
            capacity = (c_size + 1) * mult * block_len
            return capacity // 512

    # --- block device API for VfsFat ---
    def readblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        addr = block_num * self.cdv

        self.cs.value(0)
        self.spi.write(b"\xFF")

        if nblocks == 1:
            if self.cmd(_CMD17, addr, 0x01, release=False) != 0:
                self.cs.value(1)
                self.spi.write(b"\xFF")
                raise OSError("CMD17 failed")
            self._readinto(buf)
            self.cs.value(1)
            self.spi.write(b"\xFF")
        else:
            if self.cmd(_CMD18, addr, 0x01, release=False) != 0:
                self.cs.value(1)
                self.spi.write(b"\xFF")
                raise OSError("CMD18 failed")

            mv = memoryview(buf)
            offset = 0
            for _ in range(nblocks):
                self._readinto(mv[offset:offset + 512])
                offset += 512

            self.cmd(_CMD12, 0, 0x01)
            self.cs.value(1)
            self.spi.write(b"\xFF")

    def writeblocks(self, block_num, buf):
        nblocks = len(buf) // 512
        addr = block_num * self.cdv

        self.cs.value(0)
        self.spi.write(b"\xFF")

        if nblocks == 1:
            if self.cmd(_CMD24, addr, 0x01, release=False) != 0:
                self.cs.value(1)
                self.spi.write(b"\xFF")
                raise OSError("CMD24 failed")
            self._write(buf)
            self.cs.value(1)
            self.spi.write(b"\xFF")
        else:
            self.cmd(_CMD55, 0, 0x01)
            self.cmd(_CMD23, nblocks, 0x01)

            if self.cmd(_CMD25, addr, 0x01, release=False) != 0:
                self.cs.value(1)
                self.spi.write(b"\xFF")
                raise OSError("CMD25 failed")

            mv = memoryview(buf)
            offset = 0
            for _ in range(nblocks):
                self.spi.write(b"\xFC")
                self.spi.write(mv[offset:offset + 512])
                self.spi.write(b"\xFF\xFF")

                resp = self.spi.read(1, 0xFF)[0]
                if (resp & 0x1F) != 0x05:
                    raise OSError("SD multiblock write rejected")
                while self.spi.read(1, 0xFF)[0] == 0:
                    pass
                offset += 512

            self.spi.write(b"\xFD")
            while self.spi.read(1, 0xFF)[0] == 0:
                pass

            self.cs.value(1)
            self.spi.write(b"\xFF")

    def ioctl(self, op, arg):
        if op == 4:
            return 0
        if op == 5:
            self.cs.value(1)
            return 0
        if op == 6:
            return 0
        if op == 7:
            return self.sectors if self.sectors else 0
        if op == 8:
            return 512
        if op == 9:
            return 0
        return 0


# =========================================================
# Convenience helpers (so your main module stays clean)
# =========================================================

_mounted_path = None


def mount(spi, cs_pin, mount_point="/sd", baudrate=10_000_000, force_remount=True):
    """
    Mount SD card at mount_point.
    Returns True if mounted, False if failed.
    """
    global _mounted_path
    try:
        if force_remount:
            try:
                os.umount(mount_point)
            except:
                pass

        sd = SDCard(spi, cs_pin, baudrate=baudrate)
        vfs = os.VfsFat(sd)
        os.mount(vfs, mount_point)
        _mounted_path = mount_point
        return True
    except Exception as e:
        _mounted_path = None
        return False


def umount(mount_point="/sd"):
    global _mounted_path
    try:
        os.umount(mount_point)
    except:
        pass
    if _mounted_path == mount_point:
        _mounted_path = None


def is_mounted():
    return _mounted_path is not None


def ensure_dir(path):
    """
    Ensure directory exists (mkdir -p style for one level).
    """
    try:
        os.stat(path)
        return True
    except:
        try:
            os.mkdir(path)
            return True
        except:
            return False


def load_json(path, default=None):
    """
    Load JSON from SD (or anywhere). Returns default if missing/broken.
    """
    if default is None:
        default = {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default


def save_json(path, obj):
    """
    Save JSON safely (write tmp then rename).
    Returns True on success.
    """
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(obj, f)
        try:
            os.remove(path)
        except:
            pass
        os.rename(tmp, path)
        return True
    except:
        try:
            os.remove(tmp)
        except:
            pass
        return False
