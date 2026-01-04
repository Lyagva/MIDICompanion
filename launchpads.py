import math

from midi import Connection


# Embedded Novation palette (velocity -> RGB) so we don't depend on an external file.
# Source: repository's NovationPalette file.
_NOVATION_PALETTE_RAW = (
    "0, 0 0 0;\r"
    "1, 27 27 27;\r"
    "2, 45 45 45;\r"
    "3, 63 63 63;\r"
    "4, 63 11 11;\r"
    "5, 63 0 0;\r"
    "6, 55 0 0;\r"
    "7, 42 0 0;\r"
    "8, 63 45 19;\r"
    "9, 63 13 0;\r"
    "10, 49 11 0;\r"
    "11, 47 8 0;\r"
    "12, 63 50 19;\r"
    "13, 63 61 0;\r"
    "14, 51 50 0;\r"
    "15, 43 43 0;\r"
    "16, 15 63 9;\r"
    "17, 6 63 0;\r"
    "18, 1 51 0;\r"
    "19, 5 33 0;\r"
    "20, 0 63 19;\r"
    "21, 0 62 0;\r"
    "22, 0 54 0;\r"
    "23, 0 34 0;\r"
    "24, 13 63 23;\r"
    "25, 0 63 7;\r"
    "26, 0 51 3;\r"
    "27, 0 42 2;\r"
    "28, 11 63 28;\r"
    "29, 0 63 25;\r"
    "30, 0 49 19;\r"
    "31, 0 41 20;\r"
    "32, 10 63 42;\r"
    "33, 0 63 42;\r"
    "34, 0 50 31;\r"
    "35, 0 40 26;\r"
    "36, 11 63 63;\r"
    "37, 0 55 63;\r"
    "38, 0 50 50;\r"
    "39, 0 44 45;\r"
    "40, 23 52 63;\r"
    "41, 0 32 63;\r"
    "42, 0 24 49;\r"
    "43, 0 17 34;\r"
    "44, 24 32 63;\r"
    "45, 0 0 62;\r"
    "46, 0 0 50;\r"
    "47, 0 0 36;\r"
    "48, 34 28 63;\r"
    "49, 8 0 63;\r"
    "50, 5 0 52;\r"
    "51, 2 0 43;\r"
    "52, 63 25 49;\r"
    "53, 63 0 49;\r"
    "54, 52 0 41;\r"
    "55, 39 0 21;\r"
    "56, 63 16 30;\r"
    "57, 63 0 28;\r"
    "58, 49 0 7;\r"
    "59, 44 0 3;\r"
    "60, 63 1 0;\r"
    "61, 63 27 0;\r"
    "62, 54 41 0;\r"
    "63, 20 41 0;\r"
    "64, 1 29 0;\r"
    "65, 0 23 2;\r"
    "66, 0 5 40;\r"
    "67, 0 0 52;\r"
    "68, 0 32 25;\r"
    "69, 1 0 52;\r"
    "70, 50 46 40;\r"
    "71, 12 12 12;\r"
    "72, 63 0 0;\r"
    "73, 45 63 0;\r"
    "74, 39 49 0;\r"
    "75, 17 59 0;\r"
    "76, 1 48 0;\r"
    "77, 0 53 18;\r"
    "78, 0 51 59;\r"
    "79, 0 26 59;\r"
    "80, 1 0 59;\r"
    "81, 20 0 59;\r"
    "82, 63 11 46;\r"
    "83, 21 1 0;\r"
    "84, 63 6 0;\r"
    "85, 40 63 0;\r"
    "86, 39 63 7;\r"
    "87, 0 63 0;\r"
    "88, 8 63 5;\r"
    "89, 8 63 26;\r"
    "90, 8 63 47;\r"
    "91, 16 51 63;\r"
    "92, 7 34 43;\r"
    "93, 19 22 53;\r"
    "94, 53 6 63;\r"
    "95, 63 0 28;\r"
    "96, 63 13 0;\r"
    "97, 52 48 0;\r"
    "98, 26 63 0;\r"
    "99, 42 36 0;\r"
    "100, 32 21 0;\r"
    "101, 0 28 1;\r"
    "102, 0 25 11;\r"
    "103, 10 8 16;\r"
    "104, 1 8 18;\r"
    "105, 28 18 4;\r"
    "106, 28 0 0;\r"
    "107, 46 16 11;\r"
    "108, 52 25 1;\r"
    "109, 63 49 1;\r"
    "110, 37 63 3;\r"
    "111, 25 47 0;\r"
    "112, 6 5 18;\r"
    "113, 63 63 33;\r"
    "114, 36 63 33;\r"
    "115, 35 45 62;\r"
    "116, 47 40 62;\r"
    "117, 26 26 26;\r"
    "118, 46 47 47;\r"
    "119, 50 57 50;\r"
    "120, 48 0 0;\r"
    "121, 31 0 0;\r"
    "122, 0 50 0;\r"
    "123, 0 39 0;\r"
    "124, 48 50 0;\r"
    "125, 38 30 0;\r"
    "126, 46 25 0;\r"
    "127, 33 1 0;"
)


def _parse_embedded_palette(raw: str):
    lut = []
    # File is a single line with \r separators in the repo.
    for chunk in raw.replace("\n", "").split("\r"):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Format: "<idx>, R G B;"
        # We only need the RGB triplet.
        try:
            rgb_part = chunk.split(",", 1)[1]
            rgb_part = rgb_part.replace(";", "").strip()
            r, g, b = map(int, rgb_part.split())
            lut.append([r, g, b])
        except Exception:
            # Skip malformed entries
            continue
    return lut


class Palette:
    def __init__(self):
        self.LUT = _parse_embedded_palette(_NOVATION_PALETTE_RAW)

    def get_velocity(self, color):
        weight = []
        for i, lut_color in enumerate(self.LUT):
            weight.append((i, math.sqrt(
                (lut_color[0] - color[0] / 2) ** 2 +
                (lut_color[1] - color[1] / 2) ** 2 +
                (lut_color[2] - color[2] / 2) ** 2)))
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
    def deactivate(conn: Connection):
        sysex = [
            240,
            0, 32, 41,
            2,
            13,
            14,
            0,
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