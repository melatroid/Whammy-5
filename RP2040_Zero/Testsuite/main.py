# Melatroid - Whammy 5 MIDI/BLUETOOTH/SDCARD TEST SUITE - 1.03
# -----------------------------
# PINS
# -----------------------------
PIN_FOOTSW = 7
PIN_LAYER_SWITCH = 8
PIN_POT = 29

OLED_I2C_ID = 1
OLED_SCL_PIN = 15
OLED_SDA_PIN = 14
OLED_W = 128
OLED_H = 64
OLED_FREQ = 400000
OLED_ADDR_FALLBACK = 0x3c


# OLED display on/off
OLED_ENABLED = True

# Bluetooth (HC-06) on/off
BT_ENABLED = False

# SD card (SPI) on/off
SD_ENABLED = False

# TEST mode: True = direct ON switching, False = ON + OFF/BYPASS
TEST_DIRECT_MIDI_SWITCH = False

from machine import Pin, ADC, UART, I2C, SPI
import time
import os

# =========================================================
# FAIL-SAFE / TIMEOUT HELPERS
# =========================================================

class TimeoutError(Exception):
    pass

def run_with_timeout(fn, timeout_ms, name="task", *args, **kwargs):
    """
    Runs fn(*args, **kwargs) with a soft timeout.
    IMPORTANT: If a driver blocks inside native code forever, MicroPython can't kill it.
               But for our own loops and common drivers, this prevents long blocking.
    """
    t0 = time.ticks_ms()

    def timeout_cb():
        return time.ticks_diff(time.ticks_ms(), t0) >= timeout_ms

    try:
        # If the function accepts a timeout callback (recommended), pass it:
        return fn(timeout_cb, *args, **kwargs)
    except TypeError:
        # Function doesn't accept timeout_cb; run it, but at least detect "already timed out"
        if timeout_cb():
            raise TimeoutError(f"{name} timeout before start")
        return fn(*args, **kwargs)

# =========================================================
# OPTIONAL MODULES
# =========================================================

try:
    import ssd1306
    SSD1306_AVAILABLE = True
except ImportError:
    ssd1306 = None
    SSD1306_AVAILABLE = False
    print("[WARN] ssd1306.py not found -> OLED disabled")

try:
    import sdcard
    SDCARD_AVAILABLE = True
except ImportError:
    sdcard = None
    SDCARD_AVAILABLE = False
    print("[WARN] sdcard.py not found -> SD disabled")

try:
    import display_ui
    DISPLAY_UI_AVAILABLE = True
except ImportError:
    display_ui = None
    DISPLAY_UI_AVAILABLE = False
    print("[WARN] display_ui.py not found -> UI helper disabled")

# =========================================================
# HARDWARE SELF-TEST STATUS (WITH REPORT)
# =========================================================

HW_STATUS = {
    "OLED":   {"ok": False, "weight": 20, "info": ""},
    "SD":     {"ok": False, "weight": 25, "info": ""},
    "BT":     {"ok": False, "weight": 20, "info": ""},
    "MIDI":   {"ok": False, "weight": 20, "info": ""},
    "INPUTS": {"ok": False, "weight": 15, "info": ""},
}

def hw_score_percent():
    return sum(v["weight"] for v in HW_STATUS.values() if v["ok"])

def print_hw_report():
    print("\n=== HARDWARE HEALTH REPORT ===")
    for name, v in HW_STATUS.items():
        state = "OK" if v["ok"] else "FAIL"
        print(f"{name:<7}: {state:<4} ({v['weight']:>2}%) - {v['info']}")
    print(f"\nTOTAL HARDWARE FUNCTIONALITY: {hw_score_percent()} / 100 %")
    print("=== END HARDWARE REPORT ===\n")

def oled_hw_report_brief():
    """Optional: show a short summary on the OLED."""
    if not oled:
        return
    ok = hw_score_percent()
    oled.fill(0)
    oled.text("HW REPORT", 0, 0)
    oled.text(f"SCORE: {ok:3d}%", 0, 12)
    oled.text(f"OLED:{'OK' if HW_STATUS['OLED']['ok'] else 'NO'}", 0, 24)
    oled.text(f"SD  :{'OK' if HW_STATUS['SD']['ok'] else 'NO'}", 0, 34)
    oled.text(f"BT  :{'OK' if HW_STATUS['BT']['ok'] else 'NO'}", 0, 44)
    oled.text(f"MIDI:{'OK' if HW_STATUS['MIDI']['ok'] else 'NO'}", 0, 54)
    oled.show()
    time.sleep_ms(1200)


# -----------------------------
# BLUETOOTH (HC-06) TEST CONFIG
# -----------------------------
BT_UART_ID = 1
BT_BAUD = 9600

# Default pins for UART1 (change if your wiring is different!)
BT_TX_PIN = 8   # RP2040 TX -> HC-06 RXD
BT_RX_PIN = 9   # RP2040 RX <- HC-06 TXD

# -----------------------------
# SD CARD (SPI) TEST CONFIG
# -----------------------------
SD_SPI_ID = 0

# According to your breakout image (1528-4682-ND):
SD_SCK_PIN  = 2   # CLK
SD_MOSI_PIN = 3   # DI
SD_MISO_PIN = 4   # DO
SD_CS_PIN   = 1   # CS
SD_MOUNT_PT = "/sd"

# -----------------------------
# MIDI CONFIG
# -----------------------------
MIDI_ENABLED = True
MIDI_UART_ID = 0
MIDI_BAUD = 31250
MIDI_TX_PIN = 0

TEST_CHANNEL = 0
PC_MINUS_ONE = False

# -----------------------------
# TEST TIMING
# -----------------------------
PC_STEP_DELAY_MS = 100
EFFECT_OFF_DELAY_MS = 100
BETWEEN_MODES_MS = 100

# Existing behavior switch (kept):
SEND_EFFECT_OFF_AFTER_ACTIVE = True

DEBOUNCE_MS = 30
POLL_MS = 5
PRINT_EVERY_MS = 1000

POT_SMOOTH_ALPHA_NUM = 1
POT_SMOOTH_ALPHA_DEN = 8
POT_PRINT_THRESHOLD_8BIT = 3

# Send CC11 when pot changes (live mode)
LIVE_SEND_CC11 = True
LIVE_CC11_CHANNEL = TEST_CHANNEL  # usually same channel as tests

# -----------------------------
# WHAMMY 5 - OFFICIAL NAMES (as shown in the mapping graphic)
# -----------------------------
WHAMMY_NAMES = [
    "▲ 2 OCT",
    "▲ OCT",
    "▲ 5TH",
    "▲ 4TH",
    "▼ 2ND",
    "▼ 4TH",
    "▼ 5TH",
    "▼ OCT",
    "▼ 2 OCT",
    "DIVE BOMB",
]

DETUNE_NAMES = ["SHALLOW", "DEEP"]

HARMONY_NAMES = [
    "2ND/3RD",
    "b3RD/3RD",
    "3RD/4TH",
    "4TH/5TH",
    "5TH/6TH",
    "5TH/7TH",
    "4TH/3RD",
    "5TH/4TH",
    "▲OCT/OCT▼",
]

# -----------------------------
# HARDWARE INIT
# -----------------------------
footsw = Pin(PIN_FOOTSW, Pin.IN, Pin.PULL_UP)
layer_sw = Pin(PIN_LAYER_SWITCH, Pin.IN, Pin.PULL_UP)
pot = ADC(Pin(PIN_POT))

# INPUTS TEST (status)
try:
    _ = footsw.value()
    _ = layer_sw.value()
    _ = pot.read_u16()
    HW_STATUS["INPUTS"]["ok"] = True
    HW_STATUS["INPUTS"]["info"] = "footsw + layer + pot OK"
except Exception as e:
    HW_STATUS["INPUTS"]["info"] = str(e)

# =========================================================
# MIDI (MUST START ASAP)
# =========================================================

midi = None
if MIDI_ENABLED:
    try:
        midi = UART(MIDI_UART_ID, baudrate=MIDI_BAUD, tx=Pin(MIDI_TX_PIN))
        HW_STATUS["MIDI"]["ok"] = True
        HW_STATUS["MIDI"]["info"] = f"UART{MIDI_UART_ID} TX GP{MIDI_TX_PIN} OK"
    except Exception as e:
        midi = None
        HW_STATUS["MIDI"]["info"] = f"init failed: {e}"
else:
    HW_STATUS["MIDI"]["info"] = "disabled"

def midi_write(data: bytes):
    if MIDI_ENABLED and midi is not None:
        midi.write(data)

def midi_cc(cc, val, ch0):
    midi_write(bytes([0xB0 | (ch0 & 0x0F), cc & 0x7F, val & 0x7F]))

def midi_pc(pc, ch0):
    send_pc = (pc - 1) if PC_MINUS_ONE else pc
    if send_pc < 0:
        send_pc = 0
    midi_write(bytes([0xC0 | (ch0 & 0x0F), send_pc & 0x7F]))

def midi_heartbeat():
    """
    Sends a short recognizable burst right after boot,
    so you can verify that MIDI TX is alive even if other tests fail.
    """
    if not (MIDI_ENABLED and midi is not None):
        print("[MIDI] Heartbeat skipped (MIDI not available).")
        return
    try:
        midi_pc(0, TEST_CHANNEL)
        time.sleep_ms(20)
        midi_cc(11, 64, TEST_CHANNEL)
        print("[MIDI] Heartbeat sent (PC0 + CC11=64).")
    except Exception as e:
        print("[MIDI] Heartbeat failed:", e)

# Bluetooth UART
bt = None
if BT_ENABLED:
    try:
        bt = UART(BT_UART_ID, baudrate=BT_BAUD, tx=Pin(BT_TX_PIN), rx=Pin(BT_RX_PIN))
        # mark as available; detailed status set in bluetooth_test()
        HW_STATUS["BT"]["info"] = f"UART{BT_UART_ID} init OK"
    except Exception as e:
        bt = None
        HW_STATUS["BT"]["info"] = f"init failed: {e}"
else:
    HW_STATUS["BT"]["info"] = "disabled"

# -----------------------------
# UNIFORM CONSOLE DEBUG + BT POLL
# -----------------------------
DBG_COL_MODE = 8
DBG_COL_STATE = 7
DBG_COL_PC = 4
DBG_COL_CH = 3
DBG_COL_NAME = 28
DBG_COL_BT = 26

bt_rx_buf = b""
bt_last_line = ""
bt_last_bytes = b""
bt_rx_count = 0

def bt_poll(max_bytes=64):
    """
    Non-blocking poll of Bluetooth UART.
    Stores last received chunk and tries to extract a 'last line'.
    """
    global bt_rx_buf, bt_last_line, bt_last_bytes, bt_rx_count

    if not (BT_ENABLED and bt is not None):
        return False

    if not bt.any():
        return False

    data = bt.read(max_bytes)
    if not data:
        return False

    bt_last_bytes = data
    bt_rx_count += len(data)
    bt_rx_buf += data

    # Keep buffer bounded
    if len(bt_rx_buf) > 512:
        bt_rx_buf = bt_rx_buf[-512:]

    # Extract last line (split by \n or \r)
    try:
        txt = bt_rx_buf.decode(errors="ignore")
        txt = txt.replace("\r", "\n")
        lines = [ln for ln in txt.split("\n") if ln.strip() != ""]
        if lines:
            bt_last_line = lines[-1][-DBG_COL_BT:]
    except:
        bt_last_line = repr(bt_last_bytes)[-DBG_COL_BT:]

    return True

def bt_status_str():
    """
    Short status string for debug column.
    """
    if not (BT_ENABLED and bt is not None):
        return "disabled"
    if bt_last_line:
        return bt_last_line
    if bt_rx_count > 0:
        return f"{bt_rx_count}B"
    return "-"

def fmt_dbg(mode, state, pc, ch1, name, bt_info=""):
    """
    Builds a fixed-width debug line.
    """
    mode_s = f"{str(mode):<{DBG_COL_MODE}}"
    state_s = f"{str(state):<{DBG_COL_STATE}}"
    pc_s = f"{int(pc):>{DBG_COL_PC}d}"
    ch_s = f"{int(ch1):>{DBG_COL_CH}d}"
    name_s = f"{str(name):<{DBG_COL_NAME}}"
    bt_s = f"{str(bt_info):<{DBG_COL_BT}}"
    return f"{mode_s} {state_s} PC:{pc_s} CH:{ch_s} {name_s} | BT:{bt_s}"

def print_dbg_header(ch1):
    print(fmt_dbg("MODE", "STATE", 0, ch1, "NAME", "LAST_RX"))
    print("-" * (DBG_COL_MODE + DBG_COL_STATE + DBG_COL_PC + DBG_COL_CH + DBG_COL_NAME + DBG_COL_BT + 20))

# -----------------------------
# PRINT ALL PIN ASSIGNMENTS (STARTUP)
# -----------------------------
def print_pin_assignments():
    print("\n=== PIN ASSIGNMENTS / CONFIG ===")

    # Digital inputs + analog
    print(f"MOMANTARY        : GP{PIN_FOOTSW} (IN, PULL_UP)")
    print(f"LAYER SWITCH     : GP{PIN_LAYER_SWITCH} (IN, PULL_UP)")
    print(f"POT (ADC)        : GP{PIN_POT} (ADC)")

    # OLED
    if OLED_ENABLED:
        print("OLED             : ENABLED")
        print(f"  I2C ID          : {OLED_I2C_ID}")
        print(f"  SDA             : GP{OLED_SDA_PIN}")
        print(f"  SCL             : GP{OLED_SCL_PIN}")
        print(f"  RESOLUTION      : {OLED_W}x{OLED_H}")
        print(f"  I2C FREQ        : {OLED_FREQ}")
        print(f"  ADDR FALLBACK   : {hex(OLED_ADDR_FALLBACK)}")
    else:
        print("OLED             : DISABLED")

    # MIDI
    if MIDI_ENABLED:
        print("MIDI             : ENABLED")
        print(f"  UART ID         : {MIDI_UART_ID}")
        print(f"  BAUD            : {MIDI_BAUD}")
        print(f"  TX              : GP{MIDI_TX_PIN} (TX only)")
        print(f"  TEST CHANNEL    : {TEST_CHANNEL} (CH shown as {TEST_CHANNEL+1})")
        print(f"  PC_MINUS_ONE    : {PC_MINUS_ONE}")
        print(f"  DIRECT_SWITCH   : {TEST_DIRECT_MIDI_SWITCH} (TEST mode: skip OFF)")
    else:
        print("MIDI             : DISABLED")

    # Bluetooth
    if BT_ENABLED:
        print("BLUETOOTH (HC-06) : ENABLED")
        print(f"  UART ID         : {BT_UART_ID}")
        print(f"  BAUD            : {BT_BAUD}")
        print(f"  TX              : GP{BT_TX_PIN} (RP2040 TX -> HC-06 RXD)")
        print(f"  RX              : GP{BT_RX_PIN} (RP2040 RX <- HC-06 TXD)")
    else:
        print("BLUETOOTH (HC-06) : DISABLED")

    # SD Card
    if SD_ENABLED:
        print("SD CARD (SPI)     : ENABLED")
        print(f"  SPI ID          : {SD_SPI_ID}")
        print(f"  SCK             : GP{SD_SCK_PIN}")
        print(f"  MOSI            : GP{SD_MOSI_PIN}")
        print(f"  MISO            : GP{SD_MISO_PIN}")
        print(f"  CS              : GP{SD_CS_PIN}")
        print(f"  MOUNT           : {SD_MOUNT_PT}")
    else:
        print("SD CARD (SPI)     : DISABLED")

    print("=== END CONFIG ===\n")

# -----------------------------
# OLED INIT + HELPERS (FAIL-SAFE INIT)
#   Uses EXACT working config:
#     i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
# -----------------------------
oled = None
oled_addr = OLED_ADDR_FALLBACK

def _oled_init(timeout_cb=None):
    global oled, oled_addr

    if not (OLED_ENABLED and SSD1306_AVAILABLE and ssd1306 is not None):
        return

    if timeout_cb and timeout_cb():
        raise TimeoutError("OLED init timeout before start")

    i2c = I2C(OLED_I2C_ID, scl=Pin(OLED_SCL_PIN), sda=Pin(OLED_SDA_PIN), freq=OLED_FREQ)
    devices = i2c.scan()

    if not devices:
        raise RuntimeError("No I2C devices found")

    # Prefer 0x3C/0x3D, else first found
    addr = None
    for preferred in (0x3C, 0x3D):
        if preferred in devices:
            addr = preferred
            break
    if addr is None:
        addr = devices[0]

    oled_addr = addr
    oled = ssd1306.SSD1306(OLED_W, OLED_H, i2c, addr=oled_addr)

try:
    if OLED_ENABLED and SSD1306_AVAILABLE and ssd1306 is not None:
        print("[OLED] init (fail-safe)...")
        run_with_timeout(_oled_init, 1200, "OLED init")
        if oled:
            HW_STATUS["OLED"]["ok"] = True
            HW_STATUS["OLED"]["info"] = f"I2C{OLED_I2C_ID} addr {hex(oled_addr)}"
        else:
            HW_STATUS["OLED"]["info"] = "not detected"
    else:
        if not OLED_ENABLED:
            HW_STATUS["OLED"]["info"] = "disabled"
        elif not SSD1306_AVAILABLE:
            HW_STATUS["OLED"]["info"] = "ssd1306.py missing"
        else:
            HW_STATUS["OLED"]["info"] = "not available"
except Exception as e:
    oled = None
    oled_addr = OLED_ADDR_FALLBACK
    HW_STATUS["OLED"]["ok"] = False
    HW_STATUS["OLED"]["info"] = f"init failed/timeout: {e}"
    print("[WARN] OLED init skipped:", e)

def oled_clear():
    if oled:
        oled.fill(0)
        oled.show()

def _chunk_16(s: str):
    s = str(s)
    if not s:
        return [""]
    return [s[i:i+16] for i in range(0, len(s), 16)]

def oled_show_preset(mode_name, preset_name, pc, ch1, state="ON"):
    """
    Shows preset name nicely wrapped across 2 lines.
    state: "ON" or "BYPASS"
    """
    if not oled:
        return

    lines = []
    lines.append(mode_name[:16])

    wrapped = _chunk_16(preset_name)
    lines.append(wrapped[0][:16])
    lines.append(wrapped[1][:16] if len(wrapped) > 1 else "")

    lines.append(f"{state[:6]:6} PC:{pc:02d}"[:16])
    lines.append(f"CH:{ch1:02d}"[:16])

    oled.fill(0)
    y = 0
    for s in lines[:6]:
        oled.text(s, 0, y)
        y += 10
    oled.show()

def oled_show_effect_live(mode_name, preset_name, pc, ch1, state, pot_8bit, cc11_val):
    """
    LIVE screen that shows the currently selected EFFECT,
    plus an extra 6th line with POT/CC11.
    """
    if not oled:
        return

    lines = []
    lines.append(mode_name[:16])

    wrapped = _chunk_16(preset_name)
    lines.append(wrapped[0][:16])
    lines.append(wrapped[1][:16] if len(wrapped) > 1 else "")

    lines.append(f"{state[:6]:6} PC:{pc:02d}"[:16])
    lines.append(f"CH:{ch1:02d}"[:16])

    # 6th line: POT (0..255) + CC11 (0..127)
    lines.append(f"P:{pot_8bit:03d} C:{cc11_val:03d}"[:16])

    oled.fill(0)
    y = 0
    for s in lines[:6]:
        oled.text(s, 0, y)
        y += 10
    oled.show()

def oled_show_realtime_status(momentary, layer_sw_val, mode, state, pc, pot_8bit, cc11_val, ch1):
    """
    Shows live realtime values (buttons + pot) compactly on 6 lines (16 chars each).
    """
    if not oled:
        return

    l1 = f"MOM:{1 if momentary else 0} LY:{1 if layer_sw_val else 0}"[:16]
    l2 = f"MODE:{mode}"[:16]
    l3 = f"STATE:{state}"[:16]
    l4 = f"PC:{pc:02d}  CH:{ch1:02d}"[:16]
    l5 = f"POT:{pot_8bit:03d}"[:16]
    l6 = f"CC11:{cc11_val:03d}"[:16]

    oled.fill(0)
    y = 0
    for s in (l1, l2, l3, l4, l5, l6):
        oled.text(s, 0, y)
        y += 10
    oled.show()

def oled_test_screen(timeout_cb=None):
    if not oled:
        print("OLED not available -> skip test screen")
        return

    if timeout_cb and timeout_cb():
        raise TimeoutError("OLED test timeout before start")

    oled.fill(0)
    oled.text("SSD1306 TEST", 0, 0)
    oled.text(f"I2C{OLED_I2C_ID} {hex(oled_addr)}", 0, 12)
    oled.text(f"SDA GP{OLED_SDA_PIN}", 0, 24)
    oled.text(f"SCL GP{OLED_SCL_PIN}", 0, 36)
    oled.text("OLED is OK :)", 0, 48)
    oled.show()
    time.sleep_ms(600)

    oled.fill(0)
    oled.text("Progress:", 0, 0)
    oled.rect(0, 16, OLED_W, 12, 1)
    oled.show()

    for w in range(0, OLED_W - 2, 6):
        if timeout_cb and timeout_cb():
            raise TimeoutError("OLED test timeout during progress")
        oled.fill_rect(1, 17, w, 10, 1)
        oled.show()
        time.sleep_ms(20)

    oled.fill(0)
    oled.text("SSD1306 TEST", 0, 0)
    oled.text("DONE", 0, 12)
    oled.show()
    time.sleep_ms(300)
    oled_clear()

# -----------------------------
# SD + BLUETOOTH TESTS (FAIL-SAFE)
# -----------------------------
def bluetooth_test(timeout_cb=None, duration_ms=6000):
    global bt_rx_buf, bt_last_line, bt_last_bytes, bt_rx_count

    print("\n=== BLUETOOTH TEST (HC-06) ===")
    if not (BT_ENABLED and bt is not None):
        print("Bluetooth not enabled/available.")
        HW_STATUS["BT"]["ok"] = False
        if "disabled" not in HW_STATUS["BT"]["info"]:
            HW_STATUS["BT"]["info"] = "not available"
        return

    bt_rx_buf = b""
    bt_last_line = ""
    bt_last_bytes = b""
    bt_rx_count = 0

    if oled:
        oled_show_preset("BT TEST", "send/read", 0, 0, state="ON")

    # Mark as OK if UART exists and TX works; RX is a bonus
    HW_STATUS["BT"]["ok"] = True
    HW_STATUS["BT"]["info"] = f"UART{BT_UART_ID} init OK"

    try:
        bt.write(b"HC-06 TEST: hello from RP2040!\r\n")
        print("BT: sent test line. Pair phone/PC and open serial terminal.")
        print("BT: send something back during the next seconds...")
        HW_STATUS["BT"]["info"] = "TX OK (waiting RX)"
    except Exception as e:
        print("BT write failed:", e)
        HW_STATUS["BT"]["ok"] = False
        HW_STATUS["BT"]["info"] = f"write failed: {e}"

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        if timeout_cb and timeout_cb():
            raise TimeoutError("BT test timeout")
        bt_poll()
        if bt_last_bytes:
            print("BT RX:", bt_last_bytes)
            bt_last_bytes = b""
        time.sleep_ms(20)

    if HW_STATUS["BT"]["ok"]:
        if bt_rx_count > 0:
            print("BT received bytes:", bt_rx_count)
            print("BT last line:", bt_last_line if bt_last_line else "-")
            HW_STATUS["BT"]["info"] = f"TX OK, {bt_rx_count} bytes RX"
            if oled:
                oled_show_preset("BT TEST", "RX OK", 0, 0, state="ON")
        else:
            print("BT: no data received. Send something from phone/PC while test runs.\n")
            HW_STATUS["BT"]["info"] = "TX OK, no RX data"
            if oled:
                oled_show_preset("BT TEST", "no RX", 0, 0, state="ON")

    time.sleep_ms(400)
    if oled:
        oled_clear()

def sdcard_test(timeout_cb=None):
    print("\n=== SD CARD TEST (SPI) ===")

    if not SD_ENABLED:
        print("SD disabled.")
        HW_STATUS["SD"]["ok"] = False
        HW_STATUS["SD"]["info"] = "disabled"
        return

    if sdcard is None:
        print("sdcard.py not found -> copy sdcard.py into your project.")
        HW_STATUS["SD"]["ok"] = False
        HW_STATUS["SD"]["info"] = "sdcard.py missing"
        return

    if oled:
        oled_show_preset("SD TEST", "init...", 0, 0, state="ON")

    if timeout_cb and timeout_cb():
        raise TimeoutError("SD test timeout before start")

    try:
        spi = SPI(
            SD_SPI_ID,
            baudrate=10_000_000,
            polarity=0,
            phase=0,
            sck=Pin(SD_SCK_PIN),
            mosi=Pin(SD_MOSI_PIN),
            miso=Pin(SD_MISO_PIN),
        )
        cs = Pin(SD_CS_PIN, Pin.OUT, value=1)

        if timeout_cb and timeout_cb():
            raise TimeoutError("SD test timeout after SPI init")

        sd = sdcard.SDCard(spi, cs)
        vfs = os.VfsFat(sd)

        if timeout_cb and timeout_cb():
            raise TimeoutError("SD test timeout after SDCard init")

        try:
            os.umount(SD_MOUNT_PT)
        except:
            pass

        os.mount(vfs, SD_MOUNT_PT)

        if timeout_cb and timeout_cb():
            raise TimeoutError("SD test timeout after mount")

        print("Mounted SD at", SD_MOUNT_PT)

        # Listing can be slow on some cards; keep it bounded
        try:
            root = os.listdir(SD_MOUNT_PT)
            print("Root:", root)
        except Exception as e:
            print("[WARN] listdir failed:", e)

        fn = SD_MOUNT_PT + "/sd_test.txt"
        with open(fn, "w") as f:
            f.write("SD OK - hello!\n")

        if timeout_cb and timeout_cb():
            raise TimeoutError("SD test timeout after write")

        with open(fn, "r") as f:
            content = f.read()

        print("Read back:", repr(content))

        os.umount(SD_MOUNT_PT)
        print("Unmounted SD.")

        HW_STATUS["SD"]["ok"] = True
        HW_STATUS["SD"]["info"] = "mount + rw OK"

        if oled:
            oled_show_preset("SD TEST", "OK", 0, 0, state="ON")

    except Exception as e:
        print("SD TEST FAILED/SKIPPED:", e)
        HW_STATUS["SD"]["ok"] = False
        HW_STATUS["SD"]["info"] = str(e)
        if oled:
            oled_show_preset("SD TEST", "FAILED", 0, 0, state="ON")

    time.sleep_ms(300)
    if oled:
        oled_clear()

# -----------------------------
# DEBOUNCE / ADC HELPERS
# -----------------------------
def debounce_init(pin):
    v = pin.value()
    now = time.ticks_ms()
    return {"stable": v, "last_raw": v, "last_change_ms": now}

def debounce_update(pin, state, now_ms):
    raw = pin.value()
    if raw != state["last_raw"]:
        state["last_raw"] = raw
        state["last_change_ms"] = now_ms
    if time.ticks_diff(now_ms, state["last_change_ms"]) >= DEBOUNCE_MS:
        if state["stable"] != state["last_raw"]:
            state["stable"] = state["last_raw"]

def pressed_from_pullup(stable_raw):
    return stable_raw == 0

def adc_to_8bit(v_u16):
    return (v_u16 * 255 + 32767) // 65535

# -----------------------------
# PRESET MAPS (0-based)
# -----------------------------
def build_presets_classic():
    """
    CLASSIC (0-based send map):
      WHAMMY Active: 0..9     | Bypass: 22..31
      DETUNE Active: SHALLOW=11, DEEP=10 | Bypass: SHALLOW=33, DEEP=32
      HARMONY Active: 12..20  | Bypass: 34..42
    """
    active = []
    bypass = []

    for i, name in enumerate(WHAMMY_NAMES):
        active.append((f"WHAMMY {name}", 0 + i))
        bypass.append((f"WHAMMY {name}", 22 + i))

    active.append((f"DETUNE {DETUNE_NAMES[1]}", 10))  # DEEP
    bypass.append((f"DETUNE {DETUNE_NAMES[1]}", 32))  # DEEP bypass

    active.append((f"DETUNE {DETUNE_NAMES[0]}", 11))  # SHALLOW
    bypass.append((f"DETUNE {DETUNE_NAMES[0]}", 33))  # SHALLOW bypass

    for i, name in enumerate(HARMONY_NAMES):
        active.append((f"HARMONY {name}", 12 + i))
        bypass.append((f"HARMONY {name}", 34 + i))

    return active, bypass

def build_presets_chords():
    """
    CHORDS (0-based send map = manual minus 1):
      WHAMMY Active: 42..51  | Bypass: 63..72
      DETUNE Active: SHALLOW=53, DEEP=52 | Bypass: SHALLOW=74, DEEP=73
      HARMONY Active: 54..62 | Bypass: 75..83
    """
    active = []
    bypass = []

    for i, name in enumerate(WHAMMY_NAMES):
        active.append((f"WHAMMY {name}", 42 + i))
        bypass.append((f"WHAMMY {name}", 63 + i))

    active.append((f"DETUNE {DETUNE_NAMES[1]}", 52))  # DEEP
    bypass.append((f"DETUNE {DETUNE_NAMES[1]}", 73))  # DEEP bypass

    active.append((f"DETUNE {DETUNE_NAMES[0]}", 53))  # SHALLOW
    bypass.append((f"DETUNE {DETUNE_NAMES[0]}", 74))  # SHALLOW bypass

    for i, name in enumerate(HARMONY_NAMES):
        active.append((f"HARMONY {name}", 54 + i))
        bypass.append((f"HARMONY {name}", 75 + i))

    return active, bypass

def make_bypass_lookup(bypass_list):
    d = {}
    for name, pc in bypass_list:
        d[name] = pc
    return d

# -----------------------------
# TEST ROUTINES
# -----------------------------
def test_mode(mode_name, active_list, bypass_list, ch0):
    print(f"\n=== TEST MODE: {mode_name} | CH={ch0+1} ===")

    bypass_lookup = make_bypass_lookup(bypass_list)

    if oled:
        oled_show_preset(mode_name, "READY", 0, ch0 + 1, state="ON")
    time.sleep_ms(250)

    print_dbg_header(ch0 + 1)

    for name, pc_on in active_list:
        midi_pc(pc_on, ch0)
        bt_poll()
        print(fmt_dbg(mode_name[:DBG_COL_MODE], "ON", pc_on, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))
        if oled:
            oled_show_preset(mode_name, name, pc_on, ch0 + 1, state="ON")
        time.sleep_ms(PC_STEP_DELAY_MS)

        bt_poll()
        # OFF/BYPASS only if enabled AND not in direct-switch mode
        if SEND_EFFECT_OFF_AFTER_ACTIVE and not TEST_DIRECT_MIDI_SWITCH:
            pc_off = bypass_lookup.get(name, None)
            if pc_off is not None:
                midi_pc(pc_off, ch0)
                bt_poll()
                print(fmt_dbg(mode_name[:DBG_COL_MODE], "OFF", pc_off, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))
                if oled:
                    oled_show_preset(mode_name, name, pc_off, ch0 + 1, state="BYPASS")
                time.sleep_ms(EFFECT_OFF_DELAY_MS)

                bt_poll()

def run_all_tests(ch0):
    print("=== Whammy 5: FULL TEST (CLASSIC + CHORDS) ===")
    print(f"UART={MIDI_UART_ID} TX=GP{MIDI_TX_PIN} (TX-only) baud={MIDI_BAUD}")
    print(f"TEST_CHANNEL={ch0} (shown as CH={ch0+1})  PC_MINUS_ONE={PC_MINUS_ONE}")
    print(f"TEST_DIRECT_MIDI_SWITCH={TEST_DIRECT_MIDI_SWITCH}  (skip OFF in test)")
    print("Ctrl+C to stop.\n")

    if oled:
        oled_show_preset("Whammy 5", "FULL TEST", 0, ch0 + 1, state="ON")
        time.sleep_ms(600)

    classic_active, classic_bypass = build_presets_classic()
    chords_active, chords_bypass = build_presets_chords()

    test_mode("CLASSIC", classic_active, classic_bypass, ch0)
    time.sleep_ms(BETWEEN_MODES_MS)
    test_mode("CHORDS", chords_active, chords_bypass, ch0)

    if BT_ENABLED and bt is not None:
        bt_poll()
        print("\n=== BT SUMMARY (END OF TEST LOOP) ===")
        print("BT total RX bytes:", bt_rx_count)
        print("BT last line:", bt_last_line if bt_last_line else "-")

    print("\n=== TESTS FINISHED ===\n")
    if oled:
        oled_show_preset("TESTS", "FINISHED", 0, ch0 + 1, state="ON")
        time.sleep_ms(800)
        oled_clear()

# -----------------------------
# LIVE MODE (realtime values + pot CC11)
# -----------------------------
def live_monitor():
    """
    LIVE control scheme:
      - LAYER SWITCH selects MODE:
          layer pressed (LY=1)  -> CHORDS
          layer not pressed     -> CLASSIC

      - MOMENTARY (footswitch):
          ALWAYS cycles to NEXT preset and turns it ON.
          It will BYPASS the previously active preset (in that mode) first.
          First press in a mode activates preset 0 (no skipping).

      - POT controls CC11 continuously
      - OLED shows REALTIME VALUES:
          MOM, LY, MODE, STATE, PC, POT_8bit, CC11, CH
      - OLED updates on events (mode switch, pot change, footswitch)
        and also periodically (PRINT_EVERY_MS) but only if something changed.
    """
    print("=== LIVE MODE: Preset Cycle + Pot(CC11) ===")
    print("LAYER_SW: CLASSIC <-> CHORDS")
    print("MOMENTARY: NEXT preset (BYPASS prev -> ON next)")
    print("POT -> CC11: 0=toe up, 127=toe down")
    print("Ctrl+C to stop.\n")

    classic_active, classic_bypass = build_presets_classic()
    chords_active, chords_bypass = build_presets_chords()
    classic_bypass_lu = make_bypass_lookup(classic_bypass)
    chords_bypass_lu = make_bypass_lookup(chords_bypass)

    fs_state = debounce_init(footsw)
    ly_state = debounce_init(layer_sw)

    # ADC smoothing init
    raw8 = adc_to_8bit(pot.read_u16())
    filt8 = raw8
    last_pot_8_reported = filt8

    # selection state per mode
    idx = {"CLASSIC": 0, "CHORDS": 0}

    # track whether a mode has already activated a preset
    started = {"CLASSIC": False, "CHORDS": False}

    # keep consistent state per mode (last sent PC + state text)
    last_pc_sent = {"CLASSIC": 0, "CHORDS": 0}
    last_state_txt = {"CLASSIC": "OFF", "CHORDS": "OFF"}

    def mode_from_layer(ly_on: bool) -> str:
        return "CHORDS" if ly_on else "CLASSIC"

    # prime initial mode
    debounce_update(layer_sw, ly_state, time.ticks_ms())
    cur_mode = mode_from_layer(pressed_from_pullup(ly_state["stable"]))

    last_fs_pressed = False
    last_mode = cur_mode

    # init selected preset (OFF)
    if cur_mode == "CLASSIC":
        _init_name, init_pc = classic_active[idx["CLASSIC"]]
    else:
        _init_name, init_pc = chords_active[idx["CHORDS"]]

    last_pc_sent[cur_mode] = init_pc
    last_state_txt[cur_mode] = "OFF"

    # OLED change-detection cache (avoid flicker)
    last_oled_tuple = None

    # initial OLED
    if oled:
        ly_on = pressed_from_pullup(ly_state["stable"])
        fs_pressed = False
        cc11_val = (last_pot_8_reported * 127 + 127) // 255
        tup = (fs_pressed, ly_on, cur_mode, "OFF", init_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
        oled_show_realtime_status(fs_pressed, ly_on, cur_mode, "OFF", init_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
        last_oled_tuple = tup

    last_print_ms = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        # debounce inputs
        debounce_update(footsw, fs_state, now)
        debounce_update(layer_sw, ly_state, now)

        fs_pressed = pressed_from_pullup(fs_state["stable"])
        ly_on = pressed_from_pullup(ly_state["stable"])

        # mode switch handling
        cur_mode = mode_from_layer(ly_on)
        if cur_mode != last_mode:
            last_mode = cur_mode

            # choose current selection in that mode
            if cur_mode == "CLASSIC":
                _name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                _name, sel_pc = chords_active[idx["CHORDS"]]

            cc11_val = (last_pot_8_reported * 127 + 127) // 255
            show_pc = last_pc_sent[cur_mode] if last_pc_sent[cur_mode] else sel_pc
            show_state = last_state_txt[cur_mode]

            if oled:
                tup = (fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                if tup != last_oled_tuple:
                    oled_show_realtime_status(fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                    last_oled_tuple = tup

            print(f"[MODE] switched to {cur_mode}")

        # pot smoothing + CC11
        raw8 = adc_to_8bit(pot.read_u16())
        filt8 = filt8 + (POT_SMOOTH_ALPHA_NUM * (raw8 - filt8)) // POT_SMOOTH_ALPHA_DEN

        pot_changed = abs(filt8 - last_pot_8_reported) >= POT_PRINT_THRESHOLD_8BIT
        if pot_changed:
            last_pot_8_reported = filt8

            cc11_val = (last_pot_8_reported * 127 + 127) // 255
            if LIVE_SEND_CC11 and MIDI_ENABLED and midi is not None:
                midi_cc(11, cc11_val, LIVE_CC11_CHANNEL)

            # determine what should be shown
            if cur_mode == "CLASSIC":
                _name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                _name, sel_pc = chords_active[idx["CHORDS"]]

            show_pc = last_pc_sent[cur_mode] if last_pc_sent[cur_mode] else sel_pc
            show_state = last_state_txt[cur_mode]

            if oled:
                tup = (fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                if tup != last_oled_tuple:
                    oled_show_realtime_status(fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                    last_oled_tuple = tup

        # footswitch rising edge -> NEXT PRESET (bypass prev, enable next)
        if fs_pressed and not last_fs_pressed:
            if cur_mode == "CLASSIC":
                active_list = classic_active
                bypass_lu = classic_bypass_lu
                mkey = "CLASSIC"
            else:
                active_list = chords_active
                bypass_lu = chords_bypass_lu
                mkey = "CHORDS"

            # 1) if already started in this mode -> bypass previous preset first, then advance
            if started[mkey]:
                prev_name, _prev_pc_on = active_list[idx[mkey]]
                prev_pc_off = bypass_lu.get(prev_name, None)
                if prev_pc_off is not None:
                    midi_pc(prev_pc_off, LIVE_CC11_CHANNEL)
                    time.sleep_ms(120)   # 80–200ms testen
                    last_pc_sent[mkey] = prev_pc_off
                    last_state_txt[mkey] = "BYPASS"
                else:
                    print(f"[LIVE] BYPASS missing for: {prev_name}")

                idx[mkey] = (idx[mkey] + 1) % len(active_list)
            else:
                # First press: do NOT advance -> activate preset 0
                started[mkey] = True

            # 2) enable current preset
            _name, pc_on = active_list[idx[mkey]]
            midi_pc(pc_on, LIVE_CC11_CHANNEL)
            last_pc_sent[mkey] = pc_on
            last_state_txt[mkey] = "ON"

            cc11_val = (last_pot_8_reported * 127 + 127) // 255
            if oled:
                tup = (fs_pressed, ly_on, cur_mode, "ON", pc_on, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                if tup != last_oled_tuple:
                    oled_show_realtime_status(fs_pressed, ly_on, cur_mode, "ON", pc_on, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                    last_oled_tuple = tup

            print(f"[LIVE] {cur_mode} NEXT -> ON  PC {pc_on:02d}")

        last_fs_pressed = fs_pressed

        # periodic console status (OLED only if changed)
        if time.ticks_diff(now, last_print_ms) >= PRINT_EVERY_MS:
            cc11_val = (last_pot_8_reported * 127 + 127) // 255

            if cur_mode == "CLASSIC":
                _name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                _name, sel_pc = chords_active[idx["CHORDS"]]

            show_pc = last_pc_sent[cur_mode] if last_pc_sent[cur_mode] else sel_pc
            show_state = last_state_txt[cur_mode]

            print(
                f"MOMENTARY={fs_pressed} | "
                f"LAYER_SW={ly_on} | "
                f"MODE={cur_mode:<7} | "
                f"STATE={show_state:<6} | "
                f"PC={show_pc:02d} | "
                f"POT_8bit={last_pot_8_reported:3d} | "
                f"CC11={cc11_val:3d} | "
                f"CH={LIVE_CC11_CHANNEL+1:02d}"
            )

            if oled:
                tup = (fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                if tup != last_oled_tuple:
                    oled_show_realtime_status(fs_pressed, ly_on, cur_mode, show_state, show_pc, last_pot_8_reported, cc11_val, LIVE_CC11_CHANNEL + 1)
                    last_oled_tuple = tup

            last_print_ms = now

        time.sleep_ms(POLL_MS)

# -----------------------------
# MAIN (MIDI ALWAYS FIRST; TESTS FAIL-SAFE)
# -----------------------------
try:
    print_pin_assignments()

    # Make MIDI "alive" immediately, regardless of OLED/SD/BT status.
    midi_heartbeat()

    # OLED test (fail-safe)
    try:
        run_with_timeout(oled_test_screen, 1500, "OLED test")
    except Exception as e:
        print("[WARN] OLED test skipped:", e)

    # SD test (fail-safe) - even if it fails, MIDI continues.
    try:
        run_with_timeout(sdcard_test, 2000, "SD test")
    except Exception as e:
        print("[WARN] SD test skipped:", e)

    print_hw_report()
    try:
        oled_hw_report_brief()
    except:
        pass

    if oled:
        try:
            oled_clear()
        except:
            pass

    # MIDI tests + live mode run regardless of other failures.
    run_all_tests(TEST_CHANNEL)
    live_monitor()

except KeyboardInterrupt:
    if oled:
        oled_show_preset("Stopped", "by user", 0, TEST_CHANNEL + 1, state="ON")
    print("\nStopped by user (Ctrl+C).")

