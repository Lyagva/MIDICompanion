import rtmidi2
import threading
from collections import deque

import connections_registry

# MIDI event logging
_MIDI_LOGS = deque(maxlen=100)  # Keep last 100 events
_MIDI_LOG_CALLBACKS = []
_MIDI_LOG_LOCK = threading.Lock()


def add_log_callback(callback):
    """Register a callback to be called when MIDI events occur."""
    with _MIDI_LOG_LOCK:
        _MIDI_LOG_CALLBACKS.append(callback)


def remove_log_callback(callback):
    """Unregister a callback."""
    with _MIDI_LOG_LOCK:
        if callback in _MIDI_LOG_CALLBACKS:
            _MIDI_LOG_CALLBACKS.remove(callback)


def _log_midi_event(connection_name, event_type, channel, note):
    """Log a MIDI event and notify all callbacks."""
    log_entry = {
        'connection': connection_name,
        'event': event_type,
        'channel': channel,
        'note': note
    }

    with _MIDI_LOG_LOCK:
        _MIDI_LOGS.append(log_entry)
        # Notify all registered callbacks
        for callback in _MIDI_LOG_CALLBACKS[:]:  # Copy list to avoid issues if callback modifies it
            try:
                callback(log_entry)
            except Exception as e:
                print(f"Error in MIDI log callback: {e}")


def get_recent_logs(count=100):
    """Get recent MIDI logs."""
    with _MIDI_LOG_LOCK:
        return list(_MIDI_LOGS)[-count:]


class Devices:
    def __init__(self):
        self.midi_in = []
        self.midi_out = []

        self.update()

    def update(self):
        self.midi_in = list(map(lambda x: ' '.join(x.split(' ')[:-1]), rtmidi2.get_in_ports()))
        self.midi_out = list(map(lambda x: ' '.join(x.split(' ')[:-1]), rtmidi2.get_out_ports()))

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
    def __init__(self, name="conn1", port_in="", port_out="", page=1, out_channel=1, bindings=None):
        self.name = name
        self.page = page
        self.port_in = port_in
        self.port_out = port_out
        self.out_channel = out_channel  # 1-16
        self.bindings = bindings if bindings is not None else {}  # {midi_note: "page/row/col"}

        self.midi_in = rtmidi2.MidiIn()
        self.midi_in.callback = self.make_callback(self)

        self.midi_out = rtmidi2.MidiOut()

        if port_in != "":
            self.connect_in(port_in)
        if port_out != "":
            self.connect_out(port_out)

    @staticmethod
    def make_callback(conn):
        def callback(msg, _):
            msgtype, channel = rtmidi2.splitchannel(msg[0])

            # If OUT port is configured, duplicate MIDI message with channel override
            if conn.midi_out and conn.port_out:
                try:
                    # Reconstruct message with new channel (out_channel is 1-16, need 0-15 for internal)
                    new_channel = conn.out_channel - 1
                    # MIDI status byte = message type (high 4 bits) + channel (low 4 bits)
                    new_status = (msgtype & 0xF0) | (new_channel & 0x0F)
                    new_msg = [new_status] + list(msg[1:])
                    conn.midi_out.send_raw(*new_msg)
                except Exception as e:
                    print(f"MIDI OUT error: {e}")

            # Simple MIDI logic: NOTEON -> down, NOTEOFF -> up
            note = msg[1] if len(msg) > 1 else 0

            if msgtype == rtmidi2.NOTEON:
                conn.noteon(channel, note)
            elif msgtype == rtmidi2.NOTEOFF:
                conn.noteoff(channel, note)

        return callback

    def noteon(self, channel, note):
        # Log MIDI event
        _log_midi_event(self.name, 'NOTEON', channel, note)

        if note not in self.bindings:
            return

        location = self.bindings[note]

        print(f"NOTEON {self.name}: ch{channel} note{note} -> {location}")
        import companion
        companion.COMPANION.down(location)

    def noteoff(self, channel, note):
        # Log MIDI event
        _log_midi_event(self.name, 'NOTEOFF', channel, note)

        if note not in self.bindings:
            return
        location = self.bindings[note]


        print(f"NOTEOFF {self.name}: ch{channel} note{note} -> {location}")
        import companion
        companion.COMPANION.up(location)

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

    def close(self):
        """Close MIDI ports properly."""
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
        import companion
        print("Input ports", DEVICES.get_in())
        print("Output ports", DEVICES.get_out())
        print()
        conn = Connection(name="test", port_in="MIDIIN2 (LPMiniMK3 MIDI) 2", port_out="MIDIOUT2 (LPMiniMK3 MIDI) 3")
        add_connection(conn)
    except:
        pass