import time

import rtmidi2
import threading

import connections_registry


class Devices:
    def __init__(self):
        self.midi_in = []
        self.midi_out = []

        self.update()

    def update(self):
        self.midi_in = rtmidi2.get_in_ports()
        self.midi_out = rtmidi2.get_out_ports()

    def get_out(self):
        return self.midi_out

    def get_in(self):
        return self.midi_in


DEVICES = Devices()

# Backward compatibility: some code still accesses midi.CONNECTIONS directly.
# Keep it, but ensure mutations are done under a lock and provide snapshot helpers.
_CONNECTIONS_LOCK = threading.RLock()
CONNECTIONS = []


def add_connection(conn: "Connection") -> None:
    with _CONNECTIONS_LOCK:
        CONNECTIONS.append(conn)
    connections_registry.add_connection(conn)


def remove_connection(name: str) -> None:
    """Remove connection by name, closing its ports and notifying registry if supported."""
    with _CONNECTIONS_LOCK:
        remaining = []
        for c in CONNECTIONS:
            if c.name == name:
                try:
                    c.close()
                except Exception:
                    pass
                if hasattr(connections_registry, "remove_connection"):
                    try:
                        connections_registry.remove_connection(c)
                    except Exception:
                        pass
            else:
                remaining.append(c)
        CONNECTIONS[:] = remaining


def snapshot_connections():
    # Prefer the registry snapshot (single source of truth).
    return connections_registry.snapshot_connections()


class Connection:
    def __init__(self, name="conn1", port_in="", port_out="", device_type=None, page=1):
        self.name = name
        self.page = page
        self.port_in = port_in
        self.port_out = port_out

        self.midi_in = rtmidi2.MidiIn()
        self.midi_in.callback = self.make_callback(self)

        self.midi_out = rtmidi2.MidiOut()
        self.device_type = device_type

        if port_in != "":
            self.connect_in(port_in)
        if port_out != "":
            self.connect_out(port_out)

    @staticmethod
    def make_callback(conn):
        def callback(msg, _):
            msgtype, channel = rtmidi2.splitchannel(msg[0])
            if msgtype == rtmidi2.NOTEON or msgtype == rtmidi2.CC:
                note, vel = msg[1], msg[2]
                if vel == 127:
                    conn.noteon(channel, note)
                    return

                conn.noteoff(channel, note)
                return

        return callback

    def noteon(self, channel, note):
        note = self.device_type.get_note(self, note)
        # Ленивый импорт, чтобы разорвать циклическую зависимость midi <-> companion
        import companion
        companion.COMPANION.down(note)
        # print(f"NOTEON {self.name}: {channel}ch {note}")

    def noteoff(self, channel, note):
        note = self.device_type.get_note(self, note)
        # Ленивый импорт, чтобы разорвать циклическую зависимость midi <-> companion
        import companion
        companion.COMPANION.up(note)
        # print(f"NOTEOFF {self.name}: {channel}ch {note}")

    def connect_in(self, port_in=""):
        name = port_in
        if name == "":
            return

        if port_in not in DEVICES.get_in():
            return
        port = DEVICES.get_in().index(port_in)

        try:
            self.midi_in.open_port(port)
            self.port_in = port_in
        except Exception as e:
            print(e)
            return

    def connect_out(self, port_out=""):
        name = port_out
        if name == "":
            return

        if port_out not in DEVICES.get_out():
            return
        port = DEVICES.get_out().index(port_out)

        try:
            self.midi_out.open_port(port)
            self.port_out = port_out
        except Exception as e:
            print(e)
            return
    
    def set_color(self, note, color):
        midi_note = self.device_type.get_midi_note(self, note)
        self.device_type.set_color(self, midi_note, color)

    def close(self):
        """Close MIDI ports and deactivate device if possible."""
        try:
            if hasattr(self.device_type, "deactivate"):
                self.device_type.deactivate(self)
        except Exception:
            pass
        try:
            self.midi_in.close_port()
        except Exception:
            pass
        try:
            self.midi_out.close_port()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        import launchpads
        import companion
        print("Input ports", DEVICES.get_in())
        print("Output ports", DEVICES.get_out())
        print()

        conn = Connection(name="test", port_in="MIDIIN2 (LPMiniMK3 MIDI) 2", port_out="MIDIOUT2 (LPMiniMK3 MIDI) 3",
                        device_type=launchpads.MiniMK3)
        add_connection(conn)
        companion.COMPANION.start_background(page=conn.page, rows=9, columns=9)

        running = True
        while running:
            cmd = input()
            if cmd == "q":
                running = False
                continue
    except Exception as e:
        print(e)
    companion.COMPANION.stop_background()