# Melatroid - Whammy 5 MIDI TEST SUITE - 1.05
#
# COPY ALL PY FILES TO RP2040!!!
#
PIN_FOOTSW = 7
PIN_LAYER_SWITCH = 8
PIN_POT = 29
POT_DEADZONE_8BIT = 10
PIN_BANK_SWITCH = 6
BANK_SWITCH_INVERT = True # Set to "False" it Classic and Chords Toogle is wrong invertet

OLED_I2C_ID = 1
OLED_SCL_PIN = 15
OLED_SDA_PIN = 14
OLED_W = 128
OLED_H = 64
OLED_FREQ = 400000
OLED_ADDR_FALLBACK = 0x3c

OLED_ENABLED = True

TEST_DIRECT_MIDI_SWITCH = True

from machine import Pin, ADC, UART, I2C
import time
import framebuf

try:
    import ui_menu
    UI_MENU_AVAILABLE = True
except ImportError:
    ui_menu = None
    UI_MENU_AVAILABLE = False
    print("[WARN] ui_menu.py not found -> menu disabled")

class TimeoutError(Exception):
    pass

def run_with_timeout(fn, timeout_ms, name="task", *args, **kwargs):
    t0 = time.ticks_ms()

    def timeout_cb():
        return time.ticks_diff(time.ticks_ms(), t0) >= timeout_ms

    try:
        return fn(timeout_cb, *args, **kwargs)
    except TypeError:
        if timeout_cb():
            raise TimeoutError(f"{name} timeout before start")
        return fn(*args, **kwargs)

try:
    import ssd1306
    SSD1306_AVAILABLE = True
except ImportError:
    ssd1306 = None
    SSD1306_AVAILABLE = False
    print("[WARN] ssd1306.py not found -> OLED disabled")

try:
    import display_ui
    DISPLAY_UI_AVAILABLE = True
except ImportError:
    display_ui = None
    DISPLAY_UI_AVAILABLE = False
    print("[WARN] display_ui.py not found -> UI helper disabled")

try:
    from pictures import START, START_W, START_H
    PICTURES_AVAILABLE = True
except ImportError:
    START = None
    START_W = 128
    START_H = 64
    PICTURES_AVAILABLE = False
    print("[WARN] pictures.py not found -> start image disabled")

try:
    from animation import ANI1, ANI1_W, ANI1_H
    ANIMATION_AVAILABLE = True
except ImportError:
    ANI1 = None
    ANI1_W = 128
    ANI1_H = 64
    ANIMATION_AVAILABLE = False
    print("[WARN] animation.py not found -> start animation disabled")

if ANIMATION_AVAILABLE and (ANI1 is not None):
    fb = (ANI1_W * ((ANI1_H + 7)//8))
    try:
        n = len(ANI1)
        frames = (n // fb) if (fb > 0 and n % fb == 0) else "??"
        print("[ANI] bytes:", n, "frame_bytes:", fb, "frames:", frames)
    except Exception as e:
        print("[ANI] check failed:", e)

HW_STATUS = {
    "OLED":   {"ok": False, "weight": 35, "info": ""},
    "MIDI":   {"ok": False, "weight": 40, "info": ""},
    "INPUTS": {"ok": False, "weight": 25, "info": ""},
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
    if not oled:
        return
    ok = hw_score_percent()
    oled.fill(0)
    oled.text("HW REPORT", 0, 0)
    oled.text(f"SCORE: {ok:3d}%", 0, 12)
    oled.text(f"OLED:{'OK' if HW_STATUS['OLED']['ok'] else 'NO'}", 0, 24)
    oled.text(f"MIDI:{'OK' if HW_STATUS['MIDI']['ok'] else 'NO'}", 0, 34)
    oled.text(f"IN  :{'OK' if HW_STATUS['INPUTS']['ok'] else 'NO'}", 0, 44)
    oled.show()
    time.sleep_ms(1200)

MIDI_ENABLED = True
MIDI_UART_ID = 0
MIDI_BAUD = 31250
MIDI_TX_PIN = 0

TEST_CHANNEL = 0
PC_MINUS_ONE = False

PC_STEP_DELAY_MS = 100
EFFECT_OFF_DELAY_MS = 100
BETWEEN_MODES_MS = 100

SEND_EFFECT_OFF_AFTER_ACTIVE = True

DEBOUNCE_MS = 30
POLL_MS = 5
PRINT_EVERY_MS = 1000

POT_SMOOTH_ALPHA_NUM = 1
POT_SMOOTH_ALPHA_DEN = 8
POT_PRINT_THRESHOLD_8BIT = 3

LIVE_SEND_CC11 = True

LIVE_CH_CLASSIC = TEST_CHANNEL
LIVE_CH_CHORDS  = TEST_CHANNEL

MENU_OPEN_HOLD_MS = 900

DETUNE_NAMES = ["SHALLOW", "DEEP"]

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

footsw = Pin(PIN_FOOTSW, Pin.IN, Pin.PULL_UP)
layer_sw = Pin(PIN_LAYER_SWITCH, Pin.IN, Pin.PULL_UP)
bank_sw = Pin(PIN_BANK_SWITCH, Pin.IN, Pin.PULL_UP)

pot = ADC(Pin(PIN_POT))

try:
    _ = footsw.value()
    _ = layer_sw.value()
    _ = bank_sw.value()
    _ = pot.read_u16()
    HW_STATUS["INPUTS"]["ok"] = True
    HW_STATUS["INPUTS"]["info"] = "footsw + layer + bank pin + pot OK"
except Exception as e:
    HW_STATUS["INPUTS"]["info"] = str(e)

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


def oled_show_picture(image_name=None, ms=200):
    if not oled:
        return
    try:
        import pictures
        name = None
        if image_name and hasattr(pictures, image_name):
            name = image_name
        elif hasattr(pictures, "START"):
            name = "START"
        if not name:
            return
        data = getattr(pictures, name)
        w = getattr(pictures, f"{name}_W", getattr(pictures, "START_W", OLED_W))
        h = getattr(pictures, f"{name}_H", getattr(pictures, "START_H", OLED_H))
        buf = bytearray(data)
        fb0 = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)
        oled.fill(0)
        oled.blit(fb0, 0, 0)
        oled.show()
        time.sleep_ms(ms)
    except:
        pass

def boot_splash():
    if not oled:
        print("[BOOT] no oled -> skip splash")
        return

    print("[BOOT] PICTURES_AVAILABLE:", PICTURES_AVAILABLE, "START is None:", START is None)
    print("[BOOT] ANIMATION_AVAILABLE:", ANIMATION_AVAILABLE, "ANI1 is None:", ANI1 is None)

    if PICTURES_AVAILABLE and (START is not None):
        try:
            buf = bytearray(START)
            fb0 = framebuf.FrameBuffer(buf, START_W, START_H, framebuf.MONO_VLSB)
            oled.fill(0)
            oled.blit(fb0, 0, 0)
            oled.show()
            time.sleep_ms(1200)
        except Exception as e:
            print("[BOOT] start image failed:", e)

    if ANIMATION_AVAILABLE and (ANI1 is not None):
        try:
            oled_play_animation(oled, ANI1, w=ANI1_W, h=ANI1_H, fps=12, loop=False, clear=True)
            time.sleep_ms(200)
        except Exception as e:
            print("[BOOT] animation failed:", e)

DBG_COL_MODE = 8
DBG_COL_STATE = 7
DBG_COL_PC = 4
DBG_COL_CH = 3
DBG_COL_NAME = 28

def fmt_dbg(mode, state, pc, ch1, name):
    mode_s = f"{str(mode):<{DBG_COL_MODE}}"
    state_s = f"{str(state):<{DBG_COL_STATE}}"
    pc_s = f"{int(pc):>{DBG_COL_PC}d}"
    ch_s = f"{int(ch1):>{DBG_COL_CH}d}"
    name_s = f"{str(name):<{DBG_COL_NAME}}"
    return f"{mode_s} {state_s} PC:{pc_s} CH:{ch_s} {name_s}"

def print_dbg_header(ch1):
    print(fmt_dbg("MODE", "STATE", 0, ch1, "NAME"))
    print("-" * (DBG_COL_MODE + DBG_COL_STATE + DBG_COL_PC + DBG_COL_CH + DBG_COL_NAME + 12))

def print_pin_assignments():
    print("\n=== PIN ASSIGNMENTS / CONFIG ===")
    print(f"MOMANTARY        : GP{PIN_FOOTSW} (IN, PULL_UP)")
    print(f"LAYER SWITCH     : GP{PIN_LAYER_SWITCH} (IN, PULL_UP)  [MENU HOLD]")
    print(f"BANK SWITCH      : GP{PIN_BANK_SWITCH} (IN, PULL_UP)  [to GND]")
    print(f"BANK INVERT      : {BANK_SWITCH_INVERT}")
    print(f"POT (ADC)        : GP{PIN_POT} (ADC)")

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

    if MIDI_ENABLED:
        print("MIDI             : ENABLED")
        print(f"  UART ID         : {MIDI_UART_ID}")
        print(f"  BAUD            : {MIDI_BAUD}")
        print(f"  TX              : GP{MIDI_TX_PIN} (TX only)")
        print(f"  TEST CHANNEL    : {TEST_CHANNEL} (CH shown as {TEST_CHANNEL+1})")
        print(f"  PC_MINUS_ONE    : {PC_MINUS_ONE}")
        print(f"  DIRECT_SWITCH   : {TEST_DIRECT_MIDI_SWITCH} (TEST mode: skip OFF)")
        print(f"  LIVE_CH_CLASSIC : {LIVE_CH_CLASSIC} (CH shown as {LIVE_CH_CLASSIC+1})")
        print(f"  LIVE_CH_CHORDS  : {LIVE_CH_CHORDS} (CH shown as {LIVE_CH_CHORDS+1})")
    else:
        print("MIDI             : DISABLED")

    print("=== END CONFIG ===\n")

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

_ARROW_UP_8 = bytes([
    0b00011000,
    0b00111100,
    0b01111110,
    0b00011000,
    0b00011000,
    0b00011000,
    0b00011000,
    0b00000000,
])

_ARROW_DN_8 = bytes([
    0b00011000,
    0b00011000,
    0b00011000,
    0b00011000,
    0b01111110,
    0b00111100,
    0b00011000,
    0b00000000,
])

_fb_arrow_up = framebuf.FrameBuffer(bytearray(_ARROW_UP_8), 8, 8, framebuf.MONO_HLSB)
_fb_arrow_dn = framebuf.FrameBuffer(bytearray(_ARROW_DN_8), 8, 8, framebuf.MONO_HLSB)

def oled_draw_arrow(x, y, direction):
    if not oled:
        return
    if direction == "up":
        oled.blit(_fb_arrow_up, x, y)
    else:
        oled.blit(_fb_arrow_dn, x, y)

def oled_text_with_arrows(s, x, y):
    if not oled:
        return
    cx = x
    for ch in str(s):
        if ch == "▲":
            oled_draw_arrow(cx, y, "up")
            cx += 8
        elif ch == "▼":
            oled_draw_arrow(cx, y, "down")
            cx += 8
        else:
            oled.text(ch, cx, y)
            cx += 8

def oled_fill_rect_safe(x, y, w, h, c):
    if not oled:
        return
    if hasattr(oled, "fill_rect"):
        oled.fill_rect(x, y, w, h, c)
        return
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            try:
                oled.pixel(xx, yy, c)
            except:
                pass

def _frame_bytes(w, h):
    pages = (h + 7) // 8
    return w * pages

def normalize_frames(anim_data, w, h):
    fb = _frame_bytes(w, h)

    if isinstance(anim_data, (list, tuple)):
        return anim_data

    if isinstance(anim_data, (bytes, bytearray, memoryview)):
        n = len(anim_data)
        if n == fb:
            return [anim_data]
        if n % fb == 0:
            mv = memoryview(anim_data)
            count = n // fb
            return [mv[i*fb:(i+1)*fb] for i in range(count)]
        raise ValueError("ANI buffer size does not match frame size")

    raise TypeError("Unsupported animation data type")

def oled_play_animation(oled, anim_data, w, h, x=0, y=0, fps=12, loop=False, clear=True):
    frames = normalize_frames(anim_data, w, h)
    if not frames:
        return

    fb_len = _frame_bytes(w, h)
    buf = bytearray(fb_len)
    fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)

    delay_ms = max(1, int(1000 // max(1, fps)))

    while True:
        for fr in frames:
            buf[:] = fr
            if clear:
                oled.fill(0)
            oled.blit(fb, x, y)
            oled.show()
            time.sleep_ms(delay_ms)

        if not loop:
            break

def _chunk_16(s: str):
    s = str(s)
    if not s:
        return [""]
    return [s[i:i+16] for i in range(0, len(s), 16)]

def oled_show_preset(mode_name, preset_name, pc, ch1, state="ON"):
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
        oled_text_with_arrows(s, 0, y)
        y += 8
    oled.show()

def oled_show_realtime_status(momentary, layer_sw_val, mode, state, pc, pot_8bit, preset_name, ch1):
    if not oled:
        return

    l1 = f"MOM:{1 if momentary else 0} LY:{1 if layer_sw_val else 0}"[:16]
    l2 = f"MODE:{mode}"[:16]
    l3 = f"STATE:{state}"[:16]
    l4 = f"PC:{pc:02d}  CH:{ch1:02d}"[:16]
    l5 = f"POT:{pot_8bit:03d}"[:16]
    l6 = f"{str(preset_name)[:16]}"

    oled.fill(0)
    y = 0
    for s in (l1, l2, l3, l4, l5, l6):
        oled_text_with_arrows(s, 0, y)
        y += 8
    oled.show()

def oled_test_screen(timeout_cb=None):
    if not oled:
        print("OLED not available -> skip test screen")
        return

    if timeout_cb and timeout_cb():
        raise TimeoutError("OLED test timeout before start")

    oled.fill(0)
    oled.rect(0, 16, OLED_W, 12, 1)
    oled.show()

    for w in range(0, OLED_W - 2, 6):
        if timeout_cb and timeout_cb():
            raise TimeoutError("OLED test timeout during progress")
        oled_fill_rect_safe(1, 17, w, 10, 1)
        oled.show()
        time.sleep_ms(20)

    oled_clear()

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

def build_presets_classic():
    active = []
    bypass = []

    for i, name in enumerate(WHAMMY_NAMES):
        active.append((f"{name}", 0 + i))
        bypass.append((f"{name}", 22 + i))

    active.append((f"DETUNE {DETUNE_NAMES[1]}", 10))
    bypass.append((f"DETUNE {DETUNE_NAMES[1]}", 32))

    active.append((f"DETUNE {DETUNE_NAMES[0]}", 11))
    bypass.append((f"DETUNE {DETUNE_NAMES[0]}", 33))

    for i, name in enumerate(HARMONY_NAMES):
        active.append((f"HARMONY {name}", 12 + i))
        bypass.append((f"HARMONY {name}", 34 + i))

    return active, bypass

def build_presets_chords():
    active = []
    bypass = []

    for i, name in enumerate(WHAMMY_NAMES):
        active.append((f"WHAMMY {name}", 42 + i))
        bypass.append((f"WHAMMY {name}", 63 + i))

    active.append((f"DETUNE {DETUNE_NAMES[1]}", 52))
    bypass.append((f"DETUNE {DETUNE_NAMES[1]}", 73))

    active.append((f"DETUNE {DETUNE_NAMES[0]}", 53))
    bypass.append((f"DETUNE {DETUNE_NAMES[0]}", 74))

    for i, name in enumerate(HARMONY_NAMES):
        active.append((f"HARMONY {name}", 54 + i))
        bypass.append((f"HARMONY {name}", 75 + i))

    return active, bypass

def make_bypass_lookup(bypass_list):
    d = {}
    for name, pc in bypass_list:
        d[name] = pc
    return d

def test_mode(mode_name, active_list, bypass_list, ch0):
    print(f"\n=== TEST MODE: {mode_name} | CH={ch0+1} ===")

    bypass_lookup = make_bypass_lookup(bypass_list)

    if oled:
        oled_show_preset(mode_name, "READY", 0, ch0 + 1, state="ON")
    time.sleep_ms(250)

    print_dbg_header(ch0 + 1)

    for name, pc_on in active_list:
        midi_pc(pc_on, ch0)
        print(fmt_dbg(mode_name[:DBG_COL_MODE], "ON", pc_on, ch0 + 1, name[:DBG_COL_NAME]))
        if oled:
            oled_show_preset(mode_name, name, pc_on, ch0 + 1, state="ON")
        time.sleep_ms(PC_STEP_DELAY_MS)

        if SEND_EFFECT_OFF_AFTER_ACTIVE and not TEST_DIRECT_MIDI_SWITCH:
            pc_off = bypass_lookup.get(name, None)
            if pc_off is not None:
                midi_pc(pc_off, ch0)
                print(fmt_dbg(mode_name[:DBG_COL_MODE], "OFF", pc_off, ch0 + 1, name[:DBG_COL_NAME]))
                if oled:
                    oled_show_preset(mode_name, name, pc_off, ch0 + 1, state="BYPASS")
                time.sleep_ms(EFFECT_OFF_DELAY_MS)

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

    print("\n=== TESTS FINISHED ===\n")
    if oled:
        oled_show_preset("TESTS", "FINISHED", 0, ch0 + 1, state="ON")
        time.sleep_ms(800)
        oled_clear()

def live_monitor():
    print("=== LIVE MODE: Pot Select + Momentary Toggle + Bank Switch ===")
    print("BANK SWITCH: GP6 (PULL_UP) released/pressed selects bank")
    print(f"BANK_SWITCH_INVERT={BANK_SWITCH_INVERT}")
    print("POT: selects target preset")
    print("MOMENTARY: toggles selected preset ON/OFF")
    print("POT -> CC11 (optional) on current bank channel")
    print(f"LONG-HOLD LAYER ({MENU_OPEN_HOLD_MS}ms): OPEN MENU")
    print("Ctrl+C to stop.\n")

    classic_active, classic_bypass = build_presets_classic()
    chords_active, chords_bypass = build_presets_chords()
    classic_bypass_lu = make_bypass_lookup(classic_bypass)
    chords_bypass_lu = make_bypass_lookup(chords_bypass)

    fs_state = debounce_init(footsw)
    ly_state = debounce_init(layer_sw)

    raw8 = adc_to_8bit(pot.read_u16())
    filt8 = raw8
    last_pot_8_reported = filt8

    sel_idx = {"CLASSIC": 0, "CHORDS": 0}
    effect_on = {"CLASSIC": False, "CHORDS": False}
    last_pc_sent = {"CLASSIC": 0, "CHORDS": 0}
    last_state_txt = {"CLASSIC": "OFF", "CHORDS": "OFF"}

    FREEZE_AFTER_TOGGLE_MS = 250
    freeze_sel_until_ms = 0

    def _read_layer_pressed():
        return (layer_sw.value() == 0)

    def _read_mom_pressed():
        return (footsw.value() == 0)

    def _read_pot_u16():
        return pot.read_u16()

    layer_hold_start = None
    block_until_layer_release = False

    def bank_from_switch() -> str:
        pressed = (bank_sw.value() == 0)
        if not BANK_SWITCH_INVERT:
            return "CHORDS" if pressed else "CLASSIC"
        return "CLASSIC" if pressed else "CHORDS"

    def bank_ctx(bank: str):
        if bank == "CHORDS":
            return chords_active, chords_bypass_lu, LIVE_CH_CHORDS
        return classic_active, classic_bypass_lu, LIVE_CH_CLASSIC

    def pot8_to_index(p8: int, n: int) -> int:
        if n <= 1:
            return 0

        dz = POT_DEADZONE_8BIT
        lo = dz
        hi = 255 - dz

        if p8 < lo:
            p8 = lo
        elif p8 > hi:
            p8 = hi

        span = hi - lo
        if span <= 0:
            return 0

        scaled = p8 - lo
        return (scaled * (n - 1) + (span // 2)) // span

    last_fs_pressed = False
    last_bank = bank_from_switch()
    last_oled_tuple = None
    last_print_ms = time.ticks_ms()

    if oled:
        debounce_update(layer_sw, ly_state, time.ticks_ms())
        ly_on = pressed_from_pullup(ly_state["stable"])

        bank = last_bank
        active_list, _bypass_lu, ch0 = bank_ctx(bank)

        name, pc_on = active_list[sel_idx[bank]]
        show_state = last_state_txt[bank]
        show_pc = pc_on

        tup = (False, ly_on, bank, show_state, show_pc, filt8, name, ch0 + 1)
        oled_show_realtime_status(False, ly_on, bank, show_state, show_pc, filt8, name, ch0 + 1)
        last_oled_tuple = tup

    while True:
        now = time.ticks_ms()

        debounce_update(footsw, fs_state, now)
        debounce_update(layer_sw, ly_state, now)

        fs_pressed = pressed_from_pullup(fs_state["stable"])
        ly_on = pressed_from_pullup(ly_state["stable"])

        if UI_MENU_AVAILABLE and ui_menu and ui_menu.enabled():
            if block_until_layer_release:
                if not ly_on:
                    block_until_layer_release = False
                time.sleep_ms(POLL_MS)
                continue

            if ly_on and layer_hold_start is None:
                layer_hold_start = now
            if not ly_on:
                layer_hold_start = None

            if ly_on and layer_hold_start is not None:
                if time.ticks_diff(now, layer_hold_start) >= MENU_OPEN_HOLD_MS:
                    layer_hold_start = None
                    try:
                        if oled:
                            oled_show_picture("MENU_IN", 200)
                            time.sleep_ms(200)
                    except:
                        pass

                    req = ui_menu.open_blocking(_read_layer_pressed, _read_mom_pressed, _read_pot_u16, poll_ms=15)
                    if req == "playground":
                        if oled:
                            oled_show_preset("PLAYGROUND", "start", 0, TEST_CHANNEL + 1, state="ON")
                            time.sleep_ms(600)
                            oled_clear()
                        fs_state = debounce_init(footsw)
                        ly_state = debounce_init(layer_sw)
                        last_fs_pressed = False
                        block_until_layer_release = True
                        last_oled_tuple = None
                        continue
                    try:
                        oled_show_picture("MENU_OUT", 200)
                    except:
                        pass

                    fs_state = debounce_init(footsw)
                    ly_state = debounce_init(layer_sw)
                    last_fs_pressed = False
                    block_until_layer_release = True
                    last_oled_tuple = None
                    continue

        bank = bank_from_switch()
        active_list, bypass_lu, ch0 = bank_ctx(bank)

        if bank != last_bank:
            last_bank = bank
            last_oled_tuple = None
            print(f"[BANK] switched to {bank} (CH={ch0+1})")

        raw8 = adc_to_8bit(pot.read_u16())
        filt8 = filt8 + (POT_SMOOTH_ALPHA_NUM * (raw8 - filt8)) // POT_SMOOTH_ALPHA_DEN

        pot_changed = abs(filt8 - last_pot_8_reported) >= POT_PRINT_THRESHOLD_8BIT
        if pot_changed:
            last_pot_8_reported = filt8
            cc11_val = (filt8 * 127 + 127) // 255
            if LIVE_SEND_CC11 and MIDI_ENABLED and midi is not None:
                midi_cc(11, cc11_val, ch0)

        if time.ticks_diff(now, freeze_sel_until_ms) >= 0:
            new_idx = pot8_to_index(filt8, len(active_list))
            if new_idx != sel_idx[bank]:
                sel_idx[bank] = new_idx
                name, pc_on = active_list[sel_idx[bank]]

                if effect_on[bank]:
                    midi_pc(pc_on, ch0)
                    last_pc_sent[bank] = pc_on
                    last_state_txt[bank] = "ON"
                    print(f"[LIVE] {bank} SELECT -> ON  PC {pc_on:02d} ({name})")

                last_oled_tuple = None

        if fs_pressed and not last_fs_pressed:
            freeze_sel_until_ms = time.ticks_add(now, FREEZE_AFTER_TOGGLE_MS)

            idx = sel_idx[bank]
            name, pc_on = active_list[idx]
            pc_off = bypass_lu.get(name, None)

            if not effect_on[bank]:
                midi_pc(pc_on, ch0)
                effect_on[bank] = True
                last_pc_sent[bank] = pc_on
                last_state_txt[bank] = "ON"
                print(f"[LIVE] {bank} ON  -> PC {pc_on:02d} ({name})")
            else:
                if pc_off is not None:
                    midi_pc(pc_off, ch0)
                    effect_on[bank] = False
                    last_pc_sent[bank] = pc_off
                    last_state_txt[bank] = "BYPASS"
                    print(f"[LIVE] {bank} OFF -> PC {pc_off:02d} ({name})")
                else:
                    effect_on[bank] = False
                    last_state_txt[bank] = "OFF"
                    print(f"[LIVE] {bank} OFF requested but BYPASS missing for: {name}")

        last_fs_pressed = fs_pressed

        name, pc_on = active_list[sel_idx[bank]]
        show_pc = pc_on
        show_state = last_state_txt[bank]

        if oled:
            tup = (fs_pressed, ly_on, bank, show_state, show_pc, filt8, name, ch0 + 1)
            if tup != last_oled_tuple:
                oled_show_realtime_status(fs_pressed, ly_on, bank, show_state, show_pc, filt8, name, ch0 + 1)
                last_oled_tuple = tup

        if time.ticks_diff(now, last_print_ms) >= PRINT_EVERY_MS:
            cc11_val = (filt8 * 127 + 127) // 255
            print(
                f"MOMENTARY={fs_pressed} | "
                f"LAYER_SW={ly_on} | "
                f"BANK={bank:<7} | "
                f"STATE={show_state:<6} | "
                f"PC_SEL={pc_on:02d} | "
                f"PC_SENT={last_pc_sent[bank]:02d} | "
                f"SEL={sel_idx[bank]:02d} | "
                f"POT_8bit={filt8:3d} | "
                f"CC11={cc11_val:3d} | "
                f"CH={ch0+1:02d}"
            )
            last_print_ms = now

        time.sleep_ms(POLL_MS)

try:
    print_pin_assignments()
    midi_heartbeat()

    try:
        run_with_timeout(oled_test_screen, 6000, "OLED test")
    except Exception as e:
        print("[WARN] OLED test skipped:", e)

    boot_splash()

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

    if UI_MENU_AVAILABLE and ui_menu and oled and DISPLAY_UI_AVAILABLE and display_ui:
        try:
            ui_menu.init(
                oled=oled,
                oled_w=OLED_W,
                oled_h=OLED_H,
                display_ui_module=display_ui,
                print_hw_report=print_hw_report,
                oled_hw_report_brief=oled_hw_report_brief,
                run_all_tests=run_all_tests,
                run_with_timeout=run_with_timeout,
                oled_clear=oled_clear,
                test_channel=TEST_CHANNEL,
            )
        except Exception as e:
            print("[UI_MENU] init failed:", e)

    run_all_tests(TEST_CHANNEL)
    live_monitor()

except KeyboardInterrupt:
    if oled:
        oled_show_preset("Stopped", "by user", 0, TEST_CHANNEL + 1, state="ON")
    print("\nStopped by user (Ctrl+C).")


