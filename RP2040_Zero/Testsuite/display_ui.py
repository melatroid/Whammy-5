# display_ui.py
import time
import framebuf

class DisplayUI:
    def __init__(self, oled, width=128, height=64, line_h=10, chars_per_line=16):
        self.oled = oled
        self.width = width
        self.height = height
        self.line_h = line_h
        self.chars = chars_per_line
        self.last_screen = None

    def available(self):
        return self.oled is not None

    def clear(self):
        if not self.oled:
            return
        self.oled.fill(0)
        self.oled.show()

    def _chunk(self, s):
        s = "" if s is None else str(s)
        if not s:
            return [""]
        return [s[i:i+self.chars] for i in range(0, len(s), self.chars)]

    def draw_lines(self, lines):
        """
        Draw up to 6 lines (for 64px height with 10px step)
        Each line auto-cut to 16 chars.
        """
        if not self.oled:
            return
        self.oled.fill(0)
        y = 0
        for i in range(min(6, len(lines))):
            self.oled.text(str(lines[i])[:self.chars], 0, y)
            y += self.line_h
        self.oled.show()

    # ---------- BITMAPS / ANIMATIONS ----------

    def draw_bitmap(self, data, w=None, h=None, x=0, y=0, clear=True, show=True, fmt=None):
        """
        Draw a single monochrome bitmap to the OLED.

        data: bytes/bytearray containing MONO_VLSB (recommended from Nexosoft tool)
        w,h : bitmap dimensions. Default to display size.
        x,y : top-left position on OLED
        clear: clear screen before drawing
        fmt : framebuf format. Default MONO_VLSB.
        """
        if not self.oled or data is None:
            return False

        if w is None: w = self.width
        if h is None: h = self.height
        if fmt is None: fmt = framebuf.MONO_VLSB

        if clear:
            self.oled.fill(0)

        # FrameBuffer expects a mutable buffer in many builds; bytearray is safest.
        buf = data if isinstance(data, bytearray) else bytearray(data)

        fb = framebuf.FrameBuffer(buf, w, h, fmt)
        self.oled.blit(fb, x, y)

        if show:
            self.oled.show()
        return True

    def play_animation(self, frames, w=None, h=None, x=0, y=0, fps=12, loop=False, duration_ms=None, clear_each=True, fmt=None):
        """
        Play an animation on the OLED.

        frames: iterable of bytes/bytearray frames (each MONO_VLSB)
        fps: frames per second
        loop: repeat forever if True (ignore duration_ms)
        duration_ms: optional max runtime (useful for "boot animation"), None = play once (or forever if loop=True)
        clear_each: clear screen before each frame
        fmt: framebuf format. Default MONO_VLSB
        """
        if not self.oled or not frames:
            return False

        if w is None: w = self.width
        if h is None: h = self.height
        if fmt is None: fmt = framebuf.MONO_VLSB

        delay_ms = max(1, int(1000 / max(1, fps)))
        t0 = time.ticks_ms()

        while True:
            for fr in frames:
                if duration_ms is not None:
                    if time.ticks_diff(time.ticks_ms(), t0) >= duration_ms:
                        return True

                self.draw_bitmap(
                    fr, w=w, h=h, x=x, y=y,
                    clear=clear_each, show=True, fmt=fmt
                )
                time.sleep_ms(delay_ms)

            if not loop:
                break

        return True

    # --------- SCREENS ---------

    def screen_effect(self, mode, preset, pc, ch, state, extra_lines=None):
        lines = []
        lines.append(str(mode)[:self.chars])

        wrapped = self._chunk(preset)
        lines.append(wrapped[0][:self.chars])
        lines.append(wrapped[1][:self.chars] if len(wrapped) > 1 else "")

        lines.append(f"{str(state)[:6]:6} PC:{int(pc):02d}"[:self.chars])
        lines.append(f"CH:{int(ch):02d}"[:self.chars])

        if extra_lines:
            base = lines[:4]
            rebuilt = base
            rebuilt.append(lines[4])
            for ln in extra_lines:
                rebuilt.append(str(ln)[:self.chars])
            lines = rebuilt[:6]

        self.draw_lines(lines)

    def screen_live_params(self, title, params_dict, footer=None):
        lines = [str(title)[:self.chars]]
        for k, v in params_dict.items():
            lines.append(f"{k}:{v}"[:self.chars])
        if footer is not None:
            lines.append(str(footer)[:self.chars])
        self.draw_lines(lines[:6])
