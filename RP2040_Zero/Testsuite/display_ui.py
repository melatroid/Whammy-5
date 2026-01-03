# display_ui.py
# ------------------------------------------------------------
# SSD1306 Menu + Slider UI (MicroPython)
# Controls (as requested):
#   - LAYER switch: NEXT item / cycle
#   - MOMENTARY:    SELECT / ENTER
#   - POT (ADC):    adjust values in sliders / optional scroll
#
# Key design:
#   - run(menu, read_layer, read_mom, read_pot): BLOCKING UI takeover
#   - Submenus via MenuItem(submenu=...)
#   - Slider screens (bar charts) as modal calls from menu items
#   - POT Test screen (bar) as modal call from menu item
#   - Only the ACTIVE (selected) entry shows ">>>" on the right (3 arrows)
# ------------------------------------------------------------

import time
import framebuf


# ============================================================
# Menu Model
# ============================================================
class MenuItem:
    """
    label: shown text
    on_select(ui): callback
    submenu: Menu or None
    """
    def __init__(self, label, on_select=None, submenu=None):
        self.label = str(label)
        self.on_select = on_select
        self.submenu = submenu

    def __repr__(self):
        return f"MenuItem({self.label})"


class Menu:
    def __init__(self, title, items):
        self.title = str(title)
        self.items = list(items) if items else []


# ============================================================
# Internal Exit signal (for breakout / blocking UI)
# ============================================================
class UIExit(Exception):
    pass


# ============================================================
# Display UI
# ============================================================
class DisplayUI:
    def __init__(
        self,
        oled,
        width=128,
        height=64,
        header_h=16,     # top band (yellow zone often)
        line_h=8,        # compact -> makes text feel smaller
        chars=16,        # ssd1306 font: 16 chars at 128px
        debounce_ms=60,
        hold_exit_ms=700,   # long-press LAYER to exit at root
    ):
        self.oled = oled
        self.W = width
        self.H = height
        self.HEADER_H = header_h
        self.LINE_H = line_h
        self.CHARS = chars

        self.debounce_ms = debounce_ms
        self.hold_exit_ms = hold_exit_ms

        # Menu state
        self.menu = None
        self._stack = []          # (menu, sel, top)
        self.sel = 0
        self.top = 0

        # Input state
        self._last_layer = False
        self._last_mom = False
        self._last_action_ms = time.ticks_ms()

        self._layer_press_ms = 0  # for long-press exit

        # Render cache
        self._last_sig = None

        # Store readers for modal screens triggered from menu callbacks
        self._read_layer = None
        self._read_momentary = None
        self._read_pot_u16 = None

    # -----------------------------
    # Basic drawing helpers
    # -----------------------------
    def clear(self):
        if not self.oled:
            return
        self.oled.fill(0)
        self.oled.show()

    def _hline(self, y, c=1):
        if hasattr(self.oled, "hline"):
            self.oled.hline(0, y, self.W, c)
        else:
            for x in range(self.W):
                self.oled.pixel(x, y, c)

    def _fill_rect(self, x, y, w, h, c):
        if hasattr(self.oled, "fill_rect"):
            self.oled.fill_rect(x, y, w, h, c)
        else:
            for yy in range(y, y+h):
                for xx in range(x, x+w):
                    self.oled.pixel(xx, yy, c)

    # ============================================================
    # MENU (blocking takeover)
    # ============================================================
    def set_menu(self, menu: Menu):
        self.menu = menu
        self._stack = []
        self.sel = 0
        self.top = 0
        self._last_sig = None
        self.render_menu(force=True)

    def push_menu(self, menu: Menu):
        if self.menu is not None:
            self._stack.append((self.menu, self.sel, self.top))
        self.menu = menu
        self.sel = 0
        self.top = 0
        self._last_sig = None
        self.render_menu(force=True)

    def pop_menu(self):
        if not self._stack:
            return False
        self.menu, self.sel, self.top = self._stack.pop()
        self._last_sig = None
        self.render_menu(force=True)
        return True

    def request_exit(self):
        raise UIExit()

    def run(
        self,
        menu: Menu,
        read_layer,       # -> bool (pressed)
        read_momentary,   # -> bool (pressed)
        read_pot_u16=None,# -> int 0..65535 or None
        poll_ms=10,
        idle_cb=None,
    ):
        """
        BLOCKING UI takeover:
          - LAYER: NEXT item
          - MOMENTARY: SELECT
          - POT: optional (used in sliders; menu scroll optional if you want later)
          - Long-press LAYER in root menu => EXIT to main
        """
        if not self.oled:
            return

        # store readers so menu callbacks can open modal screens
        self._read_layer = read_layer
        self._read_momentary = read_momentary
        self._read_pot_u16 = read_pot_u16

        self.set_menu(menu)

        try:
            while True:
                layer = bool(read_layer())
                mom = bool(read_momentary())

                # long-press tracking for root exit
                self._handle_longpress_exit(layer)

                # edge actions
                self._handle_menu_inputs(layer, mom)

                # render if needed
                self.render_menu()

                if callable(idle_cb):
                    try:
                        idle_cb()
                    except:
                        pass

                time.sleep_ms(poll_ms)

        except UIExit:
            self.clear()
            return
        except KeyboardInterrupt:
            self.clear()
            return

    def _handle_longpress_exit(self, layer_pressed):
        now = time.ticks_ms()

        if layer_pressed:
            if self._layer_press_ms == 0:
                self._layer_press_ms = now
            else:
                # only allow long-press exit at ROOT
                if not self._stack:
                    if time.ticks_diff(now, self._layer_press_ms) >= self.hold_exit_ms:
                        # visual feedback
                        self._toast("EXIT", "to main", 250)
                        self.request_exit()
        else:
            self._layer_press_ms = 0

    def _debounced_edge(self, pressed, last_pressed):
        """
        Returns True only on rising edge with debounce time.
        """
        if pressed and not last_pressed:
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_action_ms) >= self.debounce_ms:
                self._last_action_ms = now
                return True
        return False

    def _handle_menu_inputs(self, layer_pressed, mom_pressed):
        if self.menu is None or not self.menu.items:
            self._last_layer = layer_pressed
            self._last_mom = mom_pressed
            return

        layer_edge = self._debounced_edge(layer_pressed, self._last_layer)
        mom_edge = self._debounced_edge(mom_pressed, self._last_mom)

        # LAYER: NEXT item
        if layer_edge:
            self._menu_next()

        # MOM: SELECT
        if mom_edge:
            self._menu_select()

        self._last_layer = layer_pressed
        self._last_mom = mom_pressed

    def _menu_next(self):
        n = len(self.menu.items)
        self.sel = (self.sel + 1) % n
        self._ensure_visible()
        self._last_sig = None

    def _menu_select(self):
        item = self.menu.items[self.sel]
        # submenu
        if item.submenu is not None:
            self.push_menu(item.submenu)
            return
        # callback
        if callable(item.on_select):
            item.on_select(self)
            self._last_sig = None

    def _ensure_visible(self):
        vis_lines = (self.H - self.HEADER_H) // self.LINE_H
        n = len(self.menu.items)
        if n <= vis_lines:
            self.top = 0
            return
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + vis_lines:
            self.top = self.sel - vis_lines + 1

    def render_menu(self, force=False):
        if not self.oled or self.menu is None:
            return

        sig = self._menu_sig()
        if (not force) and (sig == self._last_sig):
            return
        self._last_sig = sig

        o = self.oled
        o.fill(0)

        # header (2 lines)
        o.text(self.menu.title[:self.CHARS], 0, 0)
        self._hline(self.HEADER_H - 1, 1)

        # list
        items = self.menu.items
        vis_lines = (self.H - self.HEADER_H) // self.LINE_H
        start = self.top
        end = min(len(items), start + vis_lines)

        y = self.HEADER_H
        for idx in range(start, end):
            selected = (idx == self.sel)
            label = items[idx].label

            # >>> ONLY for active entry (selected), not for all submenus
            # Also: don't append " >" to submenu labels anymore.

            if selected:
                # highlight bar + readable text trick
                self._fill_rect(0, y, self.W, self.LINE_H, 1)
                self._fill_rect(0, y, 4, self.LINE_H, 0)
                self._fill_rect(4, y, self.W - 4, self.LINE_H, 0)

                # Leave space for ">>>"
                o.text(label[:max(0, self.CHARS - 4)], 6, y)

                # 3 arrows at right side
                o.text(">>>", self.W - 24, y)  # 3 chars * 8px
            else:
                o.text(label[:self.CHARS], 0, y)

            y += self.LINE_H

        # scroll markers
        if start > 0:
            o.text("^", self.W - 8, self.HEADER_H)
        if end < len(items):
            o.text("v", self.W - 8, self.H - self.LINE_H)

        o.show()

    def _menu_sig(self):
        items = self.menu.items
        vis_lines = (self.H - self.HEADER_H) // self.LINE_H
        end = min(len(items), self.top + vis_lines)
        vis_labels = tuple(it.label for it in items[self.top:end])
        return (id(self.menu), self.menu.title, len(items), self.sel, self.top, vis_labels)

    # ============================================================
    # POT TEST (blocking modal)  -> shows bar from POT value
    # ============================================================
    def run_pot_test(self, title="POT TEST", poll_ms=20):
        """
        BLOCKING pot test screen:
          - Shows POT value (0..65535) as a bar + percent + u16.
          - Exit: LAYER pressed once (rising edge).
        Requires that run(...) was called before, so readers are stored.
        """
        if not self.oled:
            return

        if not callable(self._read_layer) or not callable(self._read_pot_u16):
            self._toast("POT", "no reader", 450)
            return

        last_layer = False
        last_action_ms = time.ticks_ms()

        def edge(pressed, lastp):
            nonlocal last_action_ms
            if pressed and not lastp:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_action_ms) >= self.debounce_ms:
                    last_action_ms = now
                    return True
            return False

        try:
            while True:
                layer = bool(self._read_layer())

                if edge(layer, last_layer):
                    self._toast("BACK", "", 150)
                    return

                pot = int(self._read_pot_u16())
                if pot < 0: pot = 0
                if pot > 65535: pot = 65535

                self._draw_pot_test_screen(title, pot)

                last_layer = layer
                time.sleep_ms(poll_ms)

        except KeyboardInterrupt:
            return

    def _draw_pot_test_screen(self, title, pot_u16):
        o = self.oled
        if not o:
            return

        o.fill(0)

        # Header
        o.text(str(title)[:self.CHARS], 0, 0)
        o.text("LY=BACK"[:self.CHARS], 0, self.LINE_H)
        self._hline(self.HEADER_H - 1, 1)

        # percent
        pct = (pot_u16 * 100 + 32767) // 65535

        # Bar area
        bar_x = 6
        bar_y = self.HEADER_H + 10
        bar_w = self.W - 12
        bar_h = 12

        if hasattr(o, "rect"):
            o.rect(bar_x, bar_y, bar_w, bar_h, 1)
        else:
            self._hline(bar_y, 1)
            self._hline(bar_y + bar_h - 1, 1)

        fill_w = int((bar_w - 2) * pct / 100)
        if fill_w < 0: fill_w = 0
        if fill_w > (bar_w - 2): fill_w = bar_w - 2
        self._fill_rect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, 1)

        # Texts below
        o.text(f"{pct}% "[:self.CHARS], 0, bar_y + bar_h + 6)
        o.text(f"u16:{pot_u16}"[:self.CHARS], 0, bar_y + bar_h + 14)

        o.show()

    # ============================================================
    # SLIDER / BAR SCREENS (blocking modal)
    # ============================================================
    def run_slider(
        self,
        title,
        value_ref,          # dict-like {"val": int} or object w/ attribute
        vmin,
        vmax,
        read_layer,         # back
        read_momentary,     # accept
        read_pot_u16,       # adjust
        unit="",
        steps=0,            # 0 = continuous, else quantize to steps
        poll_ms=10,
        show_number=True,
    ):
        """
        BLOCKING slider:
          - POT adjusts value
          - LAYER = BACK (cancel)  -> returns (False, old_value)
          - MOM   = OK (accept)    -> returns (True, new_value)
        """
        if not self.oled:
            return (False, None)

        # read old value
        old = self._get_ref_value(value_ref)
        if old is None:
            old = vmin

        # clamp
        old = self._clamp(old, vmin, vmax)
        cur = old

        # input edges
        last_layer = False
        last_mom = False
        last_action_ms = time.ticks_ms()

        def edge(pressed, lastp):
            nonlocal last_action_ms
            if pressed and not lastp:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_action_ms) >= self.debounce_ms:
                    last_action_ms = now
                    return True
            return False

        try:
            while True:
                layer = bool(read_layer())
                mom = bool(read_momentary())

                # BACK
                if edge(layer, last_layer):
                    self._toast("CANCEL", "", 200)
                    # revert
                    self._set_ref_value(value_ref, old)
                    return (False, old)

                # OK
                if edge(mom, last_mom):
                    self._toast("OK", "", 150)
                    self._set_ref_value(value_ref, cur)
                    return (True, cur)

                # POT -> value
                pot = int(read_pot_u16())
                cur = self._map_pot_to_range(pot, vmin, vmax)

                if steps and steps > 1:
                    cur = self._quantize(cur, vmin, vmax, steps)

                self._set_ref_value(value_ref, cur)

                # draw slider screen
                self._draw_slider_screen(title, cur, vmin, vmax, unit, show_number=show_number)

                last_layer = layer
                last_mom = mom
                time.sleep_ms(poll_ms)

        except KeyboardInterrupt:
            self._set_ref_value(value_ref, old)
            return (False, old)

    def _draw_slider_screen(self, title, val, vmin, vmax, unit, show_number=True):
        o = self.oled
        if not o:
            return

        o.fill(0)

        # Header band
        o.text(str(title)[:self.CHARS], 0, 0)
        o.text("LY=BACK MOM=OK"[:self.CHARS], 0, self.LINE_H)
        self._hline(self.HEADER_H - 1, 1)

        # Bar area (simple)
        bar_x = 6
        bar_y = self.HEADER_H + 10
        bar_w = self.W - 12
        bar_h = 12

        # frame
        if hasattr(o, "rect"):
            o.rect(bar_x, bar_y, bar_w, bar_h, 1)
        else:
            # cheap frame
            self._hline(bar_y, 1)
            self._hline(bar_y + bar_h - 1, 1)

        # fill
        span = (vmax - vmin) if vmax != vmin else 1
        frac = (val - vmin) / span
        fill_w = int((bar_w - 2) * frac)
        if fill_w < 0: fill_w = 0
        if fill_w > (bar_w - 2): fill_w = bar_w - 2
        self._fill_rect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, 1)

        # numbers / value
        if show_number:
            s = f"{val}{unit}"
            o.text(s[:self.CHARS], 0, bar_y + bar_h + 8)

        o.show()

    # ============================================================
    # Multi-bar (simple "balkendiagramm" with multiple channels)
    # ============================================================
    def draw_bars(self, title, bars, vmin=0, vmax=127, unit=""):
        """
        bars: list of tuples [("Name", value), ...]
        Draws simple horizontal bars stacked vertically.
        Non-blocking render (you call it when needed).
        """
        o = self.oled
        if not o:
            return

        o.fill(0)
        o.text(str(title)[:self.CHARS], 0, 0)
        self._hline(self.HEADER_H - 1, 1)

        y = self.HEADER_H
        bar_w = self.W - 40
        name_w = 36

        span = (vmax - vmin) if vmax != vmin else 1

        max_lines = (self.H - self.HEADER_H) // self.LINE_H
        for i in range(min(max_lines, len(bars))):
            name, val = bars[i]
            val = self._clamp(int(val), vmin, vmax)

            # name
            o.text(str(name)[:4], 0, y)

            # bar frame
            bx = name_w
            by = y + 1
            bh = 6
            bw = bar_w
            if hasattr(o, "rect"):
                o.rect(bx, by, bw, bh, 1)

            # fill
            frac = (val - vmin) / span
            fw = int((bw - 2) * frac)
            if fw < 0: fw = 0
            if fw > (bw - 2): fw = bw - 2
            self._fill_rect(bx + 1, by + 1, fw, bh - 2, 1)

            # value
            o.text(f"{val}{unit}"[:5], bx + bw + 2, y)

            y += self.LINE_H

        o.show()

    # ============================================================
    # Helpers
    # ============================================================
    def _toast(self, a, b="", ms=250):
        if not self.oled:
            return
        self.oled.fill(0)
        self.oled.text(str(a)[:self.CHARS], 0, 0)
        if b:
            self.oled.text(str(b)[:self.CHARS], 0, self.LINE_H)
        self.oled.show()
        time.sleep_ms(ms)

    def _clamp(self, v, lo, hi):
        if v < lo: return lo
        if v > hi: return hi
        return v

    def _map_pot_to_range(self, pot_u16, lo, hi):
        # map 0..65535 to lo..hi
        span = hi - lo
        if span <= 0:
            return lo
        return lo + (pot_u16 * span + 32767) // 65535

    def _quantize(self, v, lo, hi, steps):
        # steps: number of discrete values between lo and hi inclusive
        if steps <= 1:
            return v
        span = hi - lo
        if span <= 0:
            return lo
        idx = int(round((v - lo) * (steps - 1) / span))
        if idx < 0: idx = 0
        if idx > steps - 1: idx = steps - 1
        return lo + (idx * span) // (steps - 1)

    def _get_ref_value(self, ref):
        # supports dict {"val":x} or object with .val
        if isinstance(ref, dict):
            return ref.get("val", None)
        return getattr(ref, "val", None)

    def _set_ref_value(self, ref, v):
        if isinstance(ref, dict):
            ref["val"] = v
        else:
            setattr(ref, "val", v)


# ============================================================
# Convenience: Build requested top menu skeleton
# ============================================================
def build_main_menu(effect_box_menu, preset_option_menu, playground_menu):
    return Menu("MAIN MENU", [
        MenuItem("Effect-Box", submenu=effect_box_menu),
        MenuItem("Preset Option", submenu=preset_option_menu),
        MenuItem("Playground", submenu=playground_menu),
    ])
