# display_ui.py - flexible OLED UI helper for SSD1306 (MicroPython)
import time

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

    # --------- SCREENS ---------

    def screen_effect(self, mode, preset, pc, ch, state, extra_lines=None):
        """
        Generic "Effect" screen (like your current oled_show_preset),
        but supports extra_lines (list of strings) for flexibility.
        """
        lines = []
        lines.append(str(mode)[:self.chars])

        wrapped = self._chunk(preset)
        lines.append(wrapped[0][:self.chars])
        lines.append(wrapped[1][:self.chars] if len(wrapped) > 1 else "")

        lines.append(f"{str(state)[:6]:6} PC:{int(pc):02d}"[:self.chars])
        lines.append(f"CH:{int(ch):02d}"[:self.chars])

        # If user wants more (overwrites last lines if >6)
        if extra_lines:
            # Put extra lines at bottom, replacing from the end
            # Keep total 6 lines max
            base = lines[:4]  # mode + 2 preset lines + footer1
            # We will rebuild to fit 6 lines:
            # base (4 lines) + CH + extras (but max 6)
            rebuilt = base
            rebuilt.append(lines[4])  # CH line
            for ln in extra_lines:
                rebuilt.append(str(ln)[:self.chars])
            lines = rebuilt[:6]

        self.draw_lines(lines)

    def screen_live_params(self, title, params_dict, footer=None):
        """
        Very flexible screen:
        title on top, then key/value pairs,
        footer optional.
        Example:
          title="LIVE"
          params={"MODE":"CLASSIC","STATE":"ON","PC":12,"CC11":64}
        """
        lines = [str(title)[:self.chars]]

        # render params as "K:V"
        for k, v in params_dict.items():
            lines.append(f"{k}:{v}"[:self.chars])

        if footer is not None:
            lines.append(str(footer)[:self.chars])

        self.draw_lines(lines[:6])
