# ui_menu.py
import time

_UI = None
_UI_MAIN_MENU = None
_UI_ENABLED = False

def init(
    oled,
    oled_w,
    oled_h,
    display_ui_module,
    # callbacks / actions aus main:
    print_hw_report,
    oled_hw_report_brief,
    run_all_tests,
    run_with_timeout,
    bluetooth_test,
    sdcard_test,
    oled_clear,
    test_channel,
):
    """
    Initialisiert Menü + UI Engine (DisplayUI) einmalig.
    main.py ruft nur init(...) und später open_blocking(...)
    """
    global _UI, _UI_MAIN_MENU, _UI_ENABLED

    if (oled is None) or (display_ui_module is None):
        _UI_ENABLED = False
        return False

    try:
        DisplayUI = display_ui_module.DisplayUI
        Menu = display_ui_module.Menu
        MenuItem = display_ui_module.MenuItem
        build_main_menu = display_ui_module.build_main_menu
    except Exception as e:
        print("[UI_MENU] import wiring failed:", e)
        _UI_ENABLED = False
        return False

    _UI = DisplayUI(oled, width=oled_w, height=oled_h)

    # ---------------------------------------------------------
    # Menüstruktur:
    # MAIN:
    #   - Effect-Box
    #   - Preset Option
    #   - Playground
    #
    # => "Dinge die derzeit in Effektbox sind" sollen in "Options"
    # Wir machen:
    #   Effect-Box -> (leer / später echte Effektfunktionen)
    #   Options    -> HW Report / OLED Brief / ...
    # ---------------------------------------------------------

    # OPTIONS (ehemals "Effect-Box Inhalte")
    options_menu = Menu("Options", [
        MenuItem("HW Report (USB)", on_select=lambda u: (print_hw_report(), u._toast("HW", "printed", 350))),
        MenuItem("OLED HW Brief", on_select=lambda u: (oled_hw_report_brief(), u._toast("OLED", "brief", 350))),
        MenuItem("Back", on_select=lambda u: u.pop_menu()),
    ])

    # EFFECT-BOX (Platzhalter -> du füllst später echte Sachen rein)
    effect_box_menu = Menu("Effect-Box", [
        MenuItem("Back", on_select=lambda u: u.pop_menu()),
    ])

    # PRESET OPTION
    preset_option_menu = Menu("Preset Option", [
        MenuItem("Run ALL Tests", on_select=lambda u: (
            u._toast("TEST", "running...", 350),
            run_all_tests(test_channel),
            u._toast("TEST", "done", 350)
        )),
        MenuItem("Back", on_select=lambda u: u.pop_menu()),
    ])

    # PLAYGROUND
    playground_menu = Menu("Playground", [
        MenuItem("BT Test", on_select=lambda u: (
            u._toast("BT", "test...", 300),
            run_with_timeout(bluetooth_test, 8000, "BT test"),
            u._toast("BT", "done", 300)
        )),
        MenuItem("SD Test", on_select=lambda u: (
            u._toast("SD", "test...", 300),
            run_with_timeout(sdcard_test, 8000, "SD test"),
            u._toast("SD", "done", 300)
        )),
        MenuItem("OLED Clear", on_select=lambda u: (oled_clear(), u._toast("OLED", "cleared", 250))),
        MenuItem("Back", on_select=lambda u: u.pop_menu()),
    ])

    # MAIN MENU bauen (hier ändern wir Build-Order: Effect-Box, Options, Preset, Playground)

    _UI_MAIN_MENU = Menu("MAIN MENU", [
        MenuItem("Effect-Box", submenu=effect_box_menu),
        MenuItem("Presets",    submenu=preset_option_menu),
        MenuItem("Options",    submenu=options_menu),
        MenuItem("Playground", submenu=playground_menu),
    ])

    _UI_ENABLED = True
    print("[UI_MENU] menus ready")
    return True


def enabled():
    return bool(_UI_ENABLED and _UI and _UI_MAIN_MENU)


def open_blocking(read_layer, read_momentary, read_pot_u16, poll_ms=15):
    """
    Blockender Menü-Takeover.
    WICHTIG: wartet erst auf LAYER-Release, damit long-press-exit nicht sofort triggert.
    """
    if not enabled():
        return

    # wait for LAYER release (bounded)
    t0 = time.ticks_ms()
    while True:
        try:
            if not bool(read_layer()):
                break
        except:
            break
        if time.ticks_diff(time.ticks_ms(), t0) > 2000:
            break
        time.sleep_ms(10)

    # Reset tracking, damit keine "ghost edges" passieren
    try:
        _UI._layer_press_ms = 0
        _UI._last_action_ms = time.ticks_ms()
        _UI._last_layer = False
        _UI._last_mom = False
    except:
        pass

    try:
        _UI.run(_UI_MAIN_MENU, read_layer, read_momentary, read_pot_u16, poll_ms=poll_ms)
    except Exception as e:
        print("[UI_MENU] run failed:", e)
        try:
            _UI.clear()
        except:
            pass

