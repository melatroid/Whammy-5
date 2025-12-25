# Melatroid - Whammy 5 MIDI/BLUETOOTH/SDCARD TEST SUITE - 1.02

from machine import Pin, ADC, UART, I2C, SPI
import time
import os

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

# -----------------------------
# PINS
# -----------------------------
PIN_FOOTSW = 5
PIN_LAYER_SWITCH = 14
PIN_POT = 26

OLED_ENABLED = True
OLED_I2C_ID = 1
OLED_SDA_PIN = 6
OLED_SCL_PIN = 7
OLED_W = 128
OLED_H = 64
OLED_FREQ = 400000
OLED_ADDR_FALLBACK = 0x3C  # typical: 0x3C or 0x3D

# -----------------------------
# BLUETOOTH (HC-06) TEST CONFIG
# -----------------------------
BT_ENABLED = True
BT_UART_ID = 1
BT_BAUD = 9600

# Default pins for UART1 (change if your wiring is different!)
BT_TX_PIN = 8   # RP2040 TX -> HC-06 RXD
BT_RX_PIN = 9   # RP2040 RX <- HC-06 TXD

# -----------------------------
# SD CARD (SPI) TEST CONFIG
# -----------------------------
SD_ENABLED = True
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
MIDI_TX_PIN = 0  # TX only (no RX)

TEST_CHANNEL = 0
PC_MINUS_ONE = False

# -----------------------------
# TEST TIMING
# -----------------------------
PC_STEP_DELAY_MS = 300
EFFECT_OFF_DELAY_MS = 500
BETWEEN_MODES_MS = 1000

# Send effect off (bypass PC) after active PC
SEND_EFFECT_OFF_AFTER_ACTIVE = True

# -----------------------------
# LIVE MODE (after tests)
# -----------------------------
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

# MIDI: TX-only (no RX)
midi = None
if MIDI_ENABLED:
    midi = UART(MIDI_UART_ID, baudrate=MIDI_BAUD, tx=Pin(MIDI_TX_PIN))

# Bluetooth UART
bt = None
if BT_ENABLED:
    bt = UART(BT_UART_ID, baudrate=BT_BAUD, tx=Pin(BT_TX_PIN), rx=Pin(BT_RX_PIN))

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
# OLED INIT + HELPERS (AUTO-DETECT + PERSIST)
# -----------------------------
oled = None
cfg = None
oled_addr = OLED_ADDR_FALLBACK

if OLED_ENABLED:
    try:
        oled, cfg = ssd1306.init_oled(width=OLED_W, height=OLED_H, freq=OLED_FREQ, debug=True, strict=False)

        if cfg:
            oled_addr = int(cfg.get("addr", OLED_ADDR_FALLBACK))
        else:
            oled_addr = OLED_ADDR_FALLBACK
    except Exception as e:
        oled = None
        cfg = None
        oled_addr = OLED_ADDR_FALLBACK
        print("OLED init failed:", e)


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


def oled_test_screen():
    if not oled:
        print("OLED not available -> skip test screen")
        return

    oled.fill(0)
    oled.text("SSD1306 TEST", 0, 0)
    oled.text(f"I2C{OLED_I2C_ID} {hex(oled_addr)}", 0, 12)
    oled.text(f"SDA GP{OLED_SDA_PIN}", 0, 24)
    oled.text(f"SCL GP{OLED_SCL_PIN}", 0, 36)
    oled.text("OLED is OK :)", 0, 48)
    oled.show()
    time.sleep_ms(1200)

    oled.fill(0)
    oled.text("Progress:", 0, 0)
    oled.rect(0, 16, OLED_W, 12, 1)
    oled.show()

    for w in range(0, OLED_W - 2, 6):
        oled.fill_rect(1, 17, w, 10, 1)
        oled.show()
        time.sleep_ms(30)

    oled.fill(0)
    oled.text("SSD1306 TEST", 0, 0)
    oled.text("DONE", 0, 12)
    oled.show()
    time.sleep_ms(600)
    oled_clear()

# -----------------------------
# SD + BLUETOOTH TESTS
# -----------------------------
def bluetooth_test(duration_ms=6000):
    global bt_rx_buf, bt_last_line, bt_last_bytes, bt_rx_count

    print("\n=== BLUETOOTH TEST (HC-06) ===")
    if not (BT_ENABLED and bt is not None):
        print("Bluetooth not enabled/available.")
        return

    bt_rx_buf = b""
    bt_last_line = ""
    bt_last_bytes = b""
    bt_rx_count = 0

    if oled:
        oled_show_preset("BT TEST", "send/read", 0, 0, state="ON")

    try:
        bt.write(b"HC-06 TEST: hello from RP2040!\r\n")
        print("BT: sent test line. Pair phone/PC and open serial terminal.")
        print("BT: send something back during the next seconds...")
    except Exception as e:
        print("BT write failed:", e)

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        bt_poll()
        if bt_last_bytes:
            print("BT RX:", bt_last_bytes)
            bt_last_bytes = b""
        time.sleep_ms(20)

    if bt_rx_count > 0:
        print("BT received bytes:", bt_rx_count)
        print("BT last line:", bt_last_line if bt_last_line else "-")
        if oled:
            oled_show_preset("BT TEST", "RX OK", 0, 0, state="ON")
    else:
        print("BT: no data received. Send something from phone/PC while test runs.\n")
        if oled:
            oled_show_preset("BT TEST", "no RX", 0, 0, state="ON")

    time.sleep_ms(800)
    if oled:
        oled_clear()


def sdcard_test():
    print("\n=== SD CARD TEST (SPI) ===")

    if not SD_ENABLED:
        print("SD disabled.")
        return

    if sdcard is None:
        print("sdcard.py not found -> copy sdcard.py into your project.")
        return

    if oled:
        oled_show_preset("SD TEST", "init...", 0, 0, state="ON")

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

        sd = sdcard.SDCard(spi, cs)
        vfs = os.VfsFat(sd)

        try:
            os.umount(SD_MOUNT_PT)
        except:
            pass

        os.mount(vfs, SD_MOUNT_PT)
        print("Mounted SD at", SD_MOUNT_PT)
        print("Root:", os.listdir(SD_MOUNT_PT))

        fn = SD_MOUNT_PT + "/sd_test.txt"
        with open(fn, "w") as f:
            f.write("SD OK - hello!\n")

        with open(fn, "r") as f:
            content = f.read()

        print("Read back:", repr(content))

        os.umount(SD_MOUNT_PT)
        print("Unmounted SD.")

        if oled:
            oled_show_preset("SD TEST", "OK", 0, 0, state="ON")

    except Exception as e:
        print("SD TEST FAILED:", e)
        if oled:
            oled_show_preset("SD TEST", "FAILED", 0, 0, state="ON")

    time.sleep_ms(800)
    if oled:
        oled_clear()

# -----------------------------
# MIDI HELPERS
# -----------------------------
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

    oled_show_preset(mode_name, "READY", 0, ch0 + 1, state="ON")
    time.sleep_ms(250)

    print_dbg_header(ch0 + 1)

    for name, pc_on in active_list:
        midi_pc(pc_on, ch0)
        bt_poll()
        print(fmt_dbg(mode_name[:DBG_COL_MODE], "ON", pc_on, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))
        oled_show_preset(mode_name, name, pc_on, ch0 + 1, state="ON")
        time.sleep_ms(PC_STEP_DELAY_MS)

        bt_poll()
        print(fmt_dbg(mode_name[:DBG_COL_MODE], "ON_END", pc_on, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))

        if SEND_EFFECT_OFF_AFTER_ACTIVE:
            pc_off = bypass_lookup.get(name, None)
            if pc_off is not None:
                midi_pc(pc_off, ch0)
                bt_poll()
                print(fmt_dbg(mode_name[:DBG_COL_MODE], "OFF", pc_off, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))
                oled_show_preset(mode_name, name, pc_off, ch0 + 1, state="BYPASS")
                time.sleep_ms(EFFECT_OFF_DELAY_MS)

                bt_poll()
                print(fmt_dbg(mode_name[:DBG_COL_MODE], "OFF_END", pc_off, ch0 + 1, name[:DBG_COL_NAME], bt_status_str()))


def run_all_tests(ch0):
    print("=== Whammy 5: FULL TEST (CLASSIC + CHORDS) ===")
    print(f"UART={MIDI_UART_ID} TX=GP{MIDI_TX_PIN} (TX-only) baud={MIDI_BAUD}")
    print(f"TEST_CHANNEL={ch0} (shown as CH={ch0+1})  PC_MINUS_ONE={PC_MINUS_ONE}")
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
# LIVE MODE (effect selection + pot CC11)
# -----------------------------
def live_monitor():
    """
    LIVE control scheme:
      - LAYER SWITCH selects MODE:
          layer pressed (LY=1)  -> CHORDS
          layer not pressed     -> CLASSIC
      - MOMENTARY (footswitch) action:
          if current effect is OFF  -> advance to next preset, send ACTIVE PC (turn ON)
          if current effect is ON   -> send BYPASS PC for same preset (turn OFF)
      - POT controls CC11 continuously
      - OLED shows CURRENT EFFECT (mode + name + state + PC + CH + pot/cc)
      - OLED updates immediately when pot changes (not only every PRINT_EVERY_MS)
      - PC shown is consistent: shows last PC actually sent (ON or BYPASS)
    """
    print("=== LIVE MODE: Effect Select + Pot(CC11) ===")
    print("LAYER_SW: CLASSIC <-> CHORDS")
    print("MOMENTARY: if OFF -> next preset + ON | if ON -> BYPASS (OFF)")
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
    effect_on = {"CLASSIC": False, "CHORDS": False}

    # NEW: keep consistent display state per mode (last sent PC + state text)
    last_pc_sent = {"CLASSIC": 0, "CHORDS": 0}
    last_state_txt = {"CLASSIC": "OFF", "CHORDS": "OFF"}

    def mode_from_layer(ly_on: bool) -> str:
        return "CHORDS" if ly_on else "CLASSIC"

    # prime initial mode
    debounce_update(layer_sw, ly_state, time.ticks_ms())
    cur_mode = mode_from_layer(pressed_from_pullup(ly_state["stable"]))

    last_fs_pressed = False
    last_mode = cur_mode

    # init display with selected preset in that mode (OFF)
    if cur_mode == "CLASSIC":
        init_name, init_pc = classic_active[idx["CLASSIC"]]
    else:
        init_name, init_pc = chords_active[idx["CHORDS"]]

    last_pc_sent[cur_mode] = init_pc
    last_state_txt[cur_mode] = "OFF"

    if oled:
        oled_show_effect_live(cur_mode, init_name, init_pc, LIVE_CC11_CHANNEL + 1, "OFF", last_pot_8_reported, 0)

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

            if cur_mode == "CLASSIC":
                name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                name, sel_pc = chords_active[idx["CHORDS"]]

            cc11_val = (last_pot_8_reported * 127 + 127) // 255
            show_pc = last_pc_sent[cur_mode] if last_pc_sent[cur_mode] else sel_pc
            show_state = last_state_txt[cur_mode]

            if oled:
                oled_show_effect_live(cur_mode, name, show_pc, LIVE_CC11_CHANNEL + 1, show_state, last_pot_8_reported, cc11_val)

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

            # NEW: update OLED immediately on pot movement (smooth UX)
            if cur_mode == "CLASSIC":
                name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                name, sel_pc = chords_active[idx["CHORDS"]]

            show_pc = last_pc_sent[cur_mode] if last_pc_sent[cur_mode] else sel_pc
            show_state = last_state_txt[cur_mode]

            if oled:
                oled_show_effect_live(cur_mode, name, show_pc, LIVE_CC11_CHANNEL + 1, show_state, last_pot_8_reported, cc11_val)

        # footswitch rising edge
        if fs_pressed and not last_fs_pressed:
            if cur_mode == "CLASSIC":
                active_list = classic_active
                bypass_lu = classic_bypass_lu
                mkey = "CLASSIC"
            else:
                active_list = chords_active
                bypass_lu = chords_bypass_lu
                mkey = "CHORDS"

            # ON -> BYPASS
            if effect_on[mkey]:
                name, pc_on = active_list[idx[mkey]]
                pc_off = bypass_lu.get(name, None)
                if pc_off is not None:
                    midi_pc(pc_off, LIVE_CC11_CHANNEL)
                    effect_on[mkey] = False

                    last_pc_sent[mkey] = pc_off
                    last_state_txt[mkey] = "BYPASS"

                    cc11_val = (last_pot_8_reported * 127 + 127) // 255
                    if oled:
                        oled_show_effect_live(cur_mode, name, pc_off, LIVE_CC11_CHANNEL + 1, "BYPASS", last_pot_8_reported, cc11_val)

                    print(f"[LIVE] {cur_mode} BYPASS  PC {pc_off:02d}  {name}")
                else:
                    print(f"[LIVE] BYPASS missing for: {name}")

            # OFF -> NEXT + ON
            else:
                idx[mkey] = (idx[mkey] + 1) % len(active_list)
                name, pc_on = active_list[idx[mkey]]
                midi_pc(pc_on, LIVE_CC11_CHANNEL)
                effect_on[mkey] = True

                last_pc_sent[mkey] = pc_on
                last_state_txt[mkey] = "ON"

                cc11_val = (last_pot_8_reported * 127 + 127) // 255
                if oled:
                    oled_show_effect_live(cur_mode, name, pc_on, LIVE_CC11_CHANNEL + 1, "ON", last_pot_8_reported, cc11_val)

                print(f"[LIVE] {cur_mode} ON      PC {pc_on:02d}  {name}")

        last_fs_pressed = fs_pressed

        # periodic console status (and OLED refresh to match console)
        if time.ticks_diff(now, last_print_ms) >= PRINT_EVERY_MS:
            cc11_val = (last_pot_8_reported * 127 + 127) // 255

            if cur_mode == "CLASSIC":
                name, sel_pc = classic_active[idx["CLASSIC"]]
            else:
                name, sel_pc = chords_active[idx["CHORDS"]]

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
                oled_show_effect_live(cur_mode, name, show_pc, LIVE_CC11_CHANNEL + 1, show_state, last_pot_8_reported, cc11_val)

            last_print_ms = now

        time.sleep_ms(POLL_MS)

# -----------------------------
# MAIN
# -----------------------------
try:
    print_pin_assignments()

    oled_test_screen()

    sdcard_test()
    bluetooth_test()

    run_all_tests(TEST_CHANNEL)
    live_monitor()

except KeyboardInterrupt:
    if oled:
        oled_show_preset("Stopped", "by user", 0, TEST_CHANNEL + 1, state="ON")
    print("\nStopped by user (Ctrl+C).")
