# Melatroid - Whammy 5 MIDI TEST - SWITCHES AND MIDI CHANNELS 1.00

from machine import Pin, ADC, UART
import time

# -----------------------------
# PINS
# -----------------------------
PIN_FOOTSW = 5
PIN_LAYER_SWITCH = 14
PIN_POT = 26

# -----------------------------
# MIDI CONFIG
# -----------------------------
MIDI_ENABLED = True
MIDI_UART_ID = 0
MIDI_BAUD = 31250
MIDI_TX_PIN = 0
MIDI_RX_PIN = 1

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

midi = None
if MIDI_ENABLED:
    midi = UART(MIDI_UART_ID, baudrate=MIDI_BAUD, tx=Pin(MIDI_TX_PIN), rx=Pin(MIDI_RX_PIN))

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

    for name, pc_on in active_list:
        midi_pc(pc_on, ch0)
        print(f"  ON  PC {pc_on:02d}  {name}")
        time.sleep_ms(PC_STEP_DELAY_MS)

        if SEND_EFFECT_OFF_AFTER_ACTIVE:
            pc_off = bypass_lookup.get(name, None)
            if pc_off is not None:
                midi_pc(pc_off, ch0)
                print(f"  OFF PC {pc_off:02d}  {name} (BYPASS)")
                time.sleep_ms(EFFECT_OFF_DELAY_MS)

def run_all_tests(ch0):
    print("=== Whammy 5: FULL TEST (CLASSIC + CHORDS) ===")
    print(f"UART={MIDI_UART_ID} TX=GP{MIDI_TX_PIN} RX=GP{MIDI_RX_PIN} baud={MIDI_BAUD}")
    print(f"TEST_CHANNEL={ch0} (shown as CH={ch0+1})  PC_MINUS_ONE={PC_MINUS_ONE}")
    print("Ctrl+C to stop.\n")

    classic_active, classic_bypass = build_presets_classic()
    chords_active, chords_bypass = build_presets_chords()

    test_mode("CLASSIC", classic_active, classic_bypass, ch0)
    time.sleep_ms(BETWEEN_MODES_MS)
    test_mode("CHORDS", chords_active, chords_bypass, ch0)

    print("\n=== TESTS FINISHED ===\n")

# -----------------------------
# LIVE MODE (show switches + pot, pot -> CC11)
# -----------------------------
def live_monitor():
    print("=== LIVE MODE: Switch/Pot Monitor + Pot controls CC11 ===")
    print("POT -> CC11: 0=toe up, 127=toe down")
    print("Ctrl+C to stop.\n")

    fs_state = debounce_init(footsw)
    ly_state = debounce_init(layer_sw)

    raw8 = adc_to_8bit(pot.read_u16())
    filt8 = raw8
    last_pot_8_reported = filt8

    last_print_ms = time.ticks_ms()

    while True:
        now = time.ticks_ms()

        debounce_update(footsw, fs_state, now)
        debounce_update(layer_sw, ly_state, now)

        raw8 = adc_to_8bit(pot.read_u16())
        filt8 = filt8 + (POT_SMOOTH_ALPHA_NUM * (raw8 - filt8)) // POT_SMOOTH_ALPHA_DEN

        pot_changed = abs(filt8 - last_pot_8_reported) >= POT_PRINT_THRESHOLD_8BIT
        if pot_changed:
            last_pot_8_reported = filt8

            if LIVE_SEND_CC11 and MIDI_ENABLED and midi is not None:
                cc11_val = (last_pot_8_reported * 127 + 127) // 255  # 0..255 -> 0..127 (rounded)
                midi_cc(11, cc11_val, LIVE_CC11_CHANNEL)

        if time.ticks_diff(now, last_print_ms) >= PRINT_EVERY_MS:
            fs_pressed = pressed_from_pullup(fs_state["stable"])
            ly_on = pressed_from_pullup(ly_state["stable"])

            cc11_val = (last_pot_8_reported * 127 + 127) // 255
            print(
                f"FOOTSW={fs_pressed} | "
                f"LAYER_SW={ly_on} | "
                f"POT_8bit={last_pot_8_reported:3d} | "
                f"CC11={cc11_val:3d} | "
                f"CH={LIVE_CC11_CHANNEL+1:02d}"
            )
            last_print_ms = now

        time.sleep_ms(POLL_MS)

# -----------------------------
# MAIN
# -----------------------------
try:
    run_all_tests(TEST_CHANNEL)
    live_monitor()
except KeyboardInterrupt:
    print("\nStopped by user (Ctrl+C).")

