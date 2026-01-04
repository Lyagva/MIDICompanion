import math

from midi import Connection


class Palette:
    def __init__(self, path = "NovationPalette"):
        self.path = path
        self.LUT = []
        with open(self.path, "r") as f:
            for line in f:
                self.LUT.append(list(map(int, line.split(", ")[-1].
                                replace("\n", "").replace(";", "").split(" "))))

    def get_velocity(self, color):
        weight = []
        for i, lut_color in enumerate(self.LUT):
            weight.append((i, math.sqrt(
                (lut_color[0] - color[0] / 2)**2 +
                (lut_color[1] - color[1] / 2)**2 +
                (lut_color[2] - color[2] / 2)**2)))
        weight.sort(key=lambda x: x[1])
        return weight[0][0]

PALETTE = Palette()


class MiniMK3:
    @staticmethod
    def get_note(conn: Connection, note):
        if 11 <= note <= 99:
            x = note % 10 - 1
            y = 9 - (note // 10)

            return f"{conn.page}/{y}/{x}"
        return "0/0/0"
    
    @staticmethod
    def get_midi_note(conn: Connection, note_str: str) -> int:
        try:
            page, row, col = map(int, note_str.split("/"))
            if 0 <= row <= 8 and 0 <= col <= 8:
                return (9 - row) * 10 + (col + 1)
        except Exception:
            pass
        return 0

    @staticmethod
    def activate(conn: Connection):
        sysex = [
            240,
            0, 32, 41,
            2,
            13,
            14,
            1,
            247
        ]

        conn.midi_out.send_raw(*sysex)

    @staticmethod
    def set_color(conn: Connection, midi_note: int, color):
        sysex = [
            240, 0, 32, 41, 2, 13, 3, 3,
            midi_note,
            color[0] // 2, color[1] // 2, color[2] // 2,
            247
        ]
        conn.midi_out.send_raw(*sysex)