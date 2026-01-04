# LaunchpadCompanion (WIP)

LaunchpadCompanion is a **work-in-progress** bridge between **Bitfocus Companion** and a **Novation Launchpad** (currently: Launchpad Mini MK3 mapping is implemented).

The goal is to use the Launchpad as a small hardware surface for Companion:

- **Companion → Launchpad**: mirror button colors to the Launchpad LEDs.
- **Launchpad → Companion**: send pad presses/releases to Companion as `down`/`up` actions.

> Status: things work enough for experimentation, but the API and structure may change.

---

## What it does (current behavior)

### 1) Companion → Launchpad (LED feedback)

- Connects to Companion via **tRPC WebSocket** at:
  - `ws://<ip>:<port>/trpc`
- Subscribes to `preview.graphics.location` for each grid location.
- When an image is received, it reads the **bottom-right pixel** of that image.
- That pixel’s RGB value is sent to each MIDI connection whose `conn.page` matches the image `page`.
- For Launchpad Mini MK3, colors are sent via **SysEx RGB**.

### 2) Launchpad → Companion (button presses)

- Listens on MIDI IN.
- When a pad is pressed:
  - MIDI `NOTEON` (velocity 127) → HTTP `POST /api/location/<page>/<row>/<col>/down`
- When released:
  - `NOTEOFF` (or `NOTEON` with velocity != 127) → HTTP `POST /api/location/<page>/<row>/<col>/up`

The note mapping for Launchpad Mini MK3 is implemented in `launchpads.py`.

---

## Repository layout

- `companion.py`
  - `CompanionWebSocket`: connects to Companion, subscribes to button graphics, decodes images.
  - `Companion`: convenience wrapper and background-thread runner.
- `midi.py`
  - `Connection`: MIDI in/out handling, note mapping, and sending colors.
- `launchpads.py`
  - `MiniMK3`: Launchpad Mini MK3 mapping + SysEx.
  - Palette loading from `NovationPalette`.
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

You also need:

- A running Bitfocus Companion instance (local or reachable over the network).
- A Launchpad (or another device once mapped) + working MIDI driver.

---

## How to try it (experimental)

There’s a basic demo entrypoint in `midi.py` under `if __name__ == "__main__":`.

What it does:

1. Prints available MIDI input/output ports.
2. Creates a `Connection(...)` using explicit port names.
3. Adds the connection.
4. Starts Companion polling in a background thread.

You will almost certainly need to edit the port names:

- `port_in` must match one of `rtmidi2.get_in_ports()`.
- `port_out` must match one of `rtmidi2.get_out_ports()`.

You may also need to adjust Companion host/port (see `companion.py`).

---

## Troubleshooting

- **No MIDI ports / wrong port names**: print the port list (the demo already does) and copy the exact strings.
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

