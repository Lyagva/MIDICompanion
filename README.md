# MIDI Companion (WIP)

MIDI Companion is a **work-in-progress** bridge between **Bitfocus Companion** and a **Novation Device** (currently: Device Mini MK3 mapping is implemented).

The goal is to use the Device as a small hardware surface for Companion:

- **Companion → Device**: mirror button colors to the Device LEDs.
- **Device → Companion**: send pad presses/releases to Companion as `down`/`up` actions.

> Status: things work enough for experimentation, but the API and structure may change.

---

## What it does (current behavior)
### Device → Companion (button presses)

- Listens on MIDI IN.
- When a pad is pressed:
  - MIDI `NOTEON` (velocity 127) → HTTP `POST /api/location/<page>/<row>/<col>/down`
- When released:
  - `NOTEOFF` (or `NOTEON` with velocity != 127) → HTTP `POST /api/location/<page>/<row>/<col>/up`

The note mapping for Device Mini MK3 is implemented in `devices.py`.

---

## Web UI (current recommended workflow)

The project now ships with a small **Flask Web UI** (see `main.py`) which is the easiest way to run and configure everything.

### Start the app

- Run `main.py`.
- It starts a local web server on **port 5000**.
- It attempts to open your browser automatically at:
  - `http://127.0.0.1:5000`

### What you can do in the Web UI

- Configure **Bitfocus Companion** host/port and restart the websocket client.
- Create and manage **MIDI connections**:
  - Name
  - Page
  - Device type (currently MiniMK3)
  - MIDI IN / OUT ports
  - Activate / Deactivate
- Reload MIDI device lists without restarting the app:
  - **Reload MIDI devices** button (POST `/ports/refresh` → page reload)
- Exit the program:
  - **Exit program** button (POST `/exit`)

### Notes

- The UI shows the currently detected MIDI input/output ports.
- If you plug/unplug devices while the app is running, use **Reload MIDI devices**.

---

## Repository layout

- `main.py`
  - Flask Web UI and routes.
- `companion.py`
  - `CompanionWebSocket`: connects to Companion, subscribes to button graphics, decodes images.
  - `Companion`: convenience wrapper and background-thread runner.
- `midi.py`
  - `Connection`: MIDI in/out handling, note mapping, and sending colors.
- `devices.py`
  - `MiniMK3`: Device Mini MK3 mapping + SysEx.
  - **Novation palette is embedded in code** (no external `NovationPalette` file needed at runtime).
- `connections_registry.py`
  - Thread-safe registry of active MIDI connections.

---

## Threading note (important)

Companion’s image callback runs in a **background thread** (the websocket client is run on its own event loop in a dedicated thread). If you iterate or mutate shared globals unsafely across threads, it can look like state is “randomly empty”.

This repo includes `connections_registry.py` and `midi.snapshot_connections()` to safely iterate active connections from any thread.

---

## Requirements

This project depends on a few Python packages (based on imports in the code):

- `aiohttp`
- `requests`
- `Pillow`
- `rtmidi2`
- `Flask`

You also need:

- A running Bitfocus Companion instance (local or reachable over the network).
- A Device (or another device once mapped) + working MIDI driver.

---

## Building a standalone EXE (Windows)

There is a helper script:

- `build_exe.bat`

It builds a single-file EXE using PyInstaller and bundles `templates/` and `static/` (including the Web UI assets and favicon), and uses `icon256.ico` as the EXE icon.

---

## Troubleshooting

- **No MIDI ports / wrong port names**: use the Web UI, click **Reload MIDI devices**, then re-open the dropdowns.
- **No LED updates**:
  - Confirm Companion is reachable at `ws://<ip>:<port>/trpc`.
  - Confirm you’re subscribing to the correct `page` and grid size.
- **Presses don’t trigger actions in Companion**:
  - Confirm Companion HTTP API is reachable at `http://<ip>:<port>/api/...`.
- **State differs between threads**:
  - Always iterate connections using `midi.snapshot_connections()` / `connections_registry.snapshot_connections()`.

---

## License

No license is included yet. If you plan to publish this publicly, consider adding one.
