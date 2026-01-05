from flask import Flask, request, redirect, url_for, render_template
import midi, companion
import os
import threading
import webbrowser

app = Flask(__name__)
app.secret_key = "device-companion-ui"

def _find_connection(name: str):
    for c in midi.snapshot_connections():
        if c.name == name:
            return c
    return None

def _ensure_companion(page: int = 1):
    companion.COMPANION.start_background(page=page, rows=9, columns=9)

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
    port_in = request.form.get("port_in", "")
    port_out = request.form.get("port_out", "")
    page = int(request.form.get("page", "1") or 1)
    out_channel = int(request.form.get("out_channel", "1") or 1)
    midi.remove_connection(name)
    conn = midi.Connection(name=name, port_in=port_in, port_out=port_out, page=page, out_channel=out_channel)
    midi.add_connection(conn)
    return redirect(url_for("index"))

@app.post("/connections/remove")
def remove_connection():
    midi.remove_connection(request.form.get("name", ""))
    return redirect(url_for("index"))

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

if __name__ == "__main__":
    midi.DEVICES.update()
    webbrowser.open("http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
