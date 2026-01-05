from flask import Flask, request, redirect, url_for, render_template
from flask_socketio import SocketIO, emit
import midi, companion
import os
import threading
import webbrowser

app = Flask(__name__)
app.secret_key = "device-companion-ui"
socketio = SocketIO(app, cors_allowed_origins="*")

def _find_connection(name: str):
    for c in midi.snapshot_connections():
        if c.name == name:
            return c
    return None

@app.route("/", methods=["GET"])
def index():
    connections = midi.snapshot_connections()
    return render_template(
        "index.html",
        companion_ip=companion.COMPANION.ip,
        companion_port=companion.COMPANION.port,
        connections=connections,
        midi_in=midi.DEVICES.get_in(),
        midi_out=midi.DEVICES.get_out()
    )

@app.route("/logs", methods=["GET"])
def midi_logs():
    return render_template("logs.html")

@app.post("/companion")
def update_companion():
    companion.COMPANION.ip = request.form.get("ip", companion.COMPANION.ip)
    companion.COMPANION.port = request.form.get("port", companion.COMPANION.port)

    return redirect(url_for("index"))

@app.post("/connections/create")
def create_connection():
    name = request.form.get("name", "").strip()
    page = int(request.form.get("page", "1") or 1)
    out_channel = int(request.form.get("out_channel", "1") or 1)
    if name:
        conn = midi.Connection(name=name, page=page, out_channel=out_channel)
        midi.add_connection(conn)
    return redirect(url_for("index"))

@app.post("/connections/update")
def update_connection():
    name = request.form.get("name", "")
    if not name:
        return redirect(url_for("index"))

    # Find existing connection to preserve bindings
    old_conn = _find_connection(name)
    bindings = old_conn.bindings if old_conn else {}

    port_in = request.form.get("port_in", "")
    port_out = request.form.get("port_out", "")
    page = int(request.form.get("page", "1") or 1)
    out_channel = int(request.form.get("out_channel", "1") or 1)
    midi.remove_connection(name)
    conn = midi.Connection(name=name, port_in=port_in, port_out=port_out, page=page, out_channel=out_channel, bindings=bindings)
    midi.add_connection(conn)
    return redirect(url_for("index"))

@app.post("/connections/remove")
def remove_connection():
    midi.remove_connection(request.form.get("name", ""))
    return redirect(url_for("index"))

@app.route("/connections/<name>/bindings", methods=["GET"])
def edit_bindings(name):
    conn = _find_connection(name)
    if not conn:
        return redirect(url_for("index"))
    return render_template(
        "bindings.html",
        connection=conn
    )

@app.post("/connections/<name>/bindings/add")
def add_binding(name):
    conn = _find_connection(name)
    if not conn:
        return redirect(url_for("index"))

    midi_note = request.form.get("midi_note", "").strip()
    page = request.form.get("page", "").strip()
    row = request.form.get("row", "").strip()
    col = request.form.get("col", "").strip()

    if midi_note and page and row and col:
        try:
            note_num = int(midi_note)
            location = f"{page}/{row}/{col}"
            conn.bindings[note_num] = location
        except ValueError:
            pass

    return redirect(url_for("edit_bindings", name=name))

@app.post("/connections/<name>/bindings/remove")
def remove_binding(name):
    conn = _find_connection(name)
    if not conn:
        return redirect(url_for("index"))

    midi_note = request.form.get("midi_note", "")
    if midi_note:
        try:
            note_num = int(midi_note)
            if note_num in conn.bindings:
                del conn.bindings[note_num]
        except ValueError:
            pass

    return redirect(url_for("edit_bindings", name=name))

@app.post("/ports/refresh")
def refresh_ports():
    midi.DEVICES.update()
    return redirect(url_for("index"))

@app.post("/exit")
def exit_program():
    """Terminate the application.

    We spawn a short-lived thread so we can return a redirect to the browser first.
    """

    def _shutdown():
        try:
            import time
            time.sleep(0.25)
        except Exception:
            pass

        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()
    return redirect(url_for("index"))


# WebSocket handlers for MIDI logs
# Store callbacks per session ID to properly clean them up
_active_callbacks = {}

@socketio.on('connect')
def handle_connect():
    from flask import request
    sid = request.sid
    print(f"Client connected to WebSocket: {sid}")

    # Send recent logs on connect
    recent_logs = midi.get_recent_logs()
    for log in recent_logs:
        emit('midi_event', log)

    # Register callback for new events specific to this client
    def send_log_to_client(log_entry):
        socketio.emit('midi_event', log_entry, to=sid)

    # Store callback reference so we can remove it later
    _active_callbacks[sid] = send_log_to_client
    midi.add_log_callback(send_log_to_client)


@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    sid = request.sid
    print(f"Client disconnected from WebSocket: {sid}")

    # Remove the callback for this specific client
    if sid in _active_callbacks:
        callback = _active_callbacks[sid]
        midi.remove_log_callback(callback)
        del _active_callbacks[sid]


if __name__ == "__main__":
    midi.DEVICES.update()
    webbrowser.open("http://127.0.0.1:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
