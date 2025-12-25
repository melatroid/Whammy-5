# ssd1306.py
# SSD1306 I2C driver + self-analyzing startup debugger + persistent auto-config

import framebuf

try:
    import ujson as json
except Exception:
    import json  # fallback

try:
    from machine import I2C, Pin
except Exception:
    I2C = None
    Pin = None

CFG_FILE = "oled_cfg.json"

# Common Pico pin pairs (bus, SDA, SCL)
DEFAULT_I2C_CANDIDATES = [
    # I2C0
    (0, 0, 1),
    (0, 4, 5),
    (0, 8, 9),
    (0, 12, 13),
    (0, 16, 17),
    (0, 20, 21),
    # I2C1
    (1, 2, 3),
    (1, 6, 7),
    (1, 10, 11),
    (1, 14, 15),
    (1, 18, 19),
    (1, 26, 27),
]

DEFAULT_ADDRS = (0x3C, 0x3D)


def _safe_print(debug: bool, *args):
    if debug:
        print(*args)


def load_oled_cfg():
    try:
        with open(CFG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_oled_cfg(cfg: dict):
    out = {
        "bus": int(cfg["bus"]),
        "sda": int(cfg["sda"]),
        "scl": int(cfg["scl"]),
        "addr": int(cfg["addr"]),
        "freq": int(cfg.get("freq", 400000)),
        "width": int(cfg.get("width", 128)),
        "height": int(cfg.get("height", 64)),
    }
    with open(CFG_FILE, "w") as f:
        json.dump(out, f)


def _mk_i2c(bus: int, sda: int, scl: int, freq: int):
    if I2C is None or Pin is None:
        raise RuntimeError("machine.I2C/Pin not available on this platform.")
    return I2C(bus, sda=Pin(sda), scl=Pin(scl), freq=freq)


def _probe_addr(i2c, addr: int):
    # Minimal write probe: 0x80=command prefix, 0xAE=display off
    i2c.writeto(addr, bytes([0x80, 0xAE]))


def detect_and_persist_oled(
    *,
    width=128,
    height=64,
    freq=100000,
    debug=True,
    candidates=None,
    addrs=None,
):
    candidates = candidates or DEFAULT_I2C_CANDIDATES
    addrs = addrs or DEFAULT_ADDRS

    # 1) Try saved config
    saved = load_oled_cfg()
    if saved:
        try:
            i2c = _mk_i2c(saved["bus"], saved["sda"], saved["scl"], int(saved.get("freq", freq)))
            found = i2c.scan()
            _safe_print(debug, "[OLED] saved cfg:", saved, "scan:", [hex(a) for a in found])
            if int(saved["addr"]) in found:
                _probe_addr(i2c, int(saved["addr"]))
                saved["width"] = int(saved.get("width", width))
                saved["height"] = int(saved.get("height", height))
                saved["freq"] = int(saved.get("freq", freq))
                return saved
            _safe_print(debug, "[OLED] saved cfg invalid -> autodetect")
        except Exception as e:
            _safe_print(debug, "[OLED] saved cfg failed -> autodetect:", repr(e))

    # 2) Autodetect (always overwrites cfg file)
    best_hint = None
    for (bus, sda, scl) in candidates:
        try:
            i2c = _mk_i2c(bus, sda, scl, freq)
            found = i2c.scan()
            if found:
                _safe_print(debug, f"[OLED] I2C{bus} SDA=GP{sda} SCL=GP{scl}:", [hex(a) for a in found])

            for addr in addrs:
                if addr in found:
                    try:
                        _probe_addr(i2c, addr)
                        cfg = {
                            "bus": bus,
                            "sda": sda,
                            "scl": scl,
                            "addr": addr,
                            "freq": freq,
                            "width": width,
                            "height": height,
                        }
                        save_oled_cfg(cfg)
                        _safe_print(debug, "[OLED] DETECTED + SAVED:", cfg)
                        return cfg
                    except Exception as e:
                        best_hint = ("probe_failed", bus, sda, scl, addr, repr(e))
        except Exception as e:
            best_hint = ("i2c_failed", bus, sda, scl, repr(e))
            continue

    _safe_print(debug, "[OLED] no OLED detected.")
    if best_hint:
        _safe_print(debug, "[OLED] last hint:", best_hint)
    return None


def init_oled(
    *,
    width=128,
    height=64,
    freq=100000,
    debug=True,
    strict=False,
):
    cfg = detect_and_persist_oled(width=width, height=height, freq=freq, debug=debug)
    if not cfg:
        return None, None

    i2c = _mk_i2c(cfg["bus"], cfg["sda"], cfg["scl"], int(cfg.get("freq", freq)))
    oled = SSD1306_I2C(width, height, i2c, addr=int(cfg["addr"]), debug=debug, strict=strict, probe=True)
    if not oled.available:
        return None, cfg
    return oled, cfg


class SSD1306_I2C(framebuf.FrameBuffer):
    """
    SSD1306 I2C driver with startup self-diagnostics.

    - strict=False: no crash if OLED missing (oled.available = False)
    - strict=True : raise exception after diagnostics
    """

    def __init__(self, width, height, i2c, addr=0x3C, *, debug=True, strict=False, probe=True):
        self.width = width
        self.height = height
        self.i2c = i2c
        self.addr = addr
        self.debug = debug
        self.strict = strict
        self.available = False

        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)

        if probe and not self._startup_diagnostics():
            if self.strict:
                raise OSError("SSD1306 not available.")
            return

        try:
            self.init_display()
            self.available = True
        except Exception as e:
            self._print_diag("INIT FAILED", extra=str(e))
            if self.strict:
                raise

    def _startup_diagnostics(self):
        try:
            addrs = self.i2c.scan()
        except Exception as e:
            self._print_diag("I2C SCAN FAILED", extra=repr(e))
            return False

        if self.debug:
            print("OLED I2C scan:", [hex(a) for a in addrs])

        if self.addr not in addrs:
            self._print_diag(
                "OLED ADDRESS NOT FOUND",
                extra=f"addr={hex(self.addr)} found={list(map(hex, addrs))}",
            )
            return False

        try:
            self.i2c.writeto(self.addr, bytes([0x80, 0xAE]))
            return True
        except Exception as e:
            self._print_diag("I2C WRITE FAILED", extra=repr(e))
            return False

    def _print_diag(self, title, *, extra=None):
        if not self.debug:
            return
        print(f"\n[SSD1306 DEBUG] {title}")
        if extra:
            print("  info:", extra)
        print()

    def write_cmd(self, cmd):
        if not self.available and not self.strict:
            return
        self.i2c.writeto(self.addr, bytes([0x80, cmd]))

    def write_data(self, buf):
        if not self.available and not self.strict:
            return
        self.i2c.writeto(self.addr, b"\x40" + buf)

    def init_display(self):
        for cmd in (
            0xAE, 0x20, 0x00, 0x40, 0xA1,
            0xA8, self.height - 1,
            0xC8, 0xD3, 0x00,
            0xDA, 0x12 if self.height == 64 else 0x02,
            0xD5, 0x80,
            0xD9, 0xF1,
            0xDB, 0x30,
            0x81, 0x8F,
            0xA4, 0xA6,
            0x8D, 0x14,
            0xAF,
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def show(self):
        if not self.available and not self.strict:
            return
        self.write_cmd(0x21)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)
        self.write_cmd(0x22)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)
