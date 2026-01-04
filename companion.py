import asyncio
import aiohttp
import base64
import json
import requests
import threading
from io import BytesIO
from PIL import Image
from typing import Optional, Callable
import midi
import connections_registry


class CompanionWebSocket:
    """Handles tRPC WebSocket connection to Companion."""
    
    def __init__(self, host: str, port: str):
        self.url = f"ws://{host}:{port}/trpc"
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._next_id = 1
        self._subscriptions: dict[int, dict] = {}
        self._running = False

        
        # Callbacks
        self.on_image: Optional[Callable[[int, int, int, Image.Image, bool], None]] = None
    
    def _get_next_id(self) -> int:
        msg_id = self._next_id
        self._next_id += 1
        return msg_id
    
    @staticmethod
    def _decode_image(image_data: str) -> bytes:
        """Decode base64 image (handles URL-safe base64)."""
        if image_data.startswith("data:"):
            image_data = image_data.split(",", 1)[1]
        try:
            return base64.urlsafe_b64decode(image_data + "==")
        except:
            padding = 4 - len(image_data) % 4
            if padding != 4:
                image_data += "=" * padding
            return base64.b64decode(image_data)
    
    async def _send(self, messages: list[dict]) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.send_str(json.dumps(messages))
    
    async def _subscribe_graphics(self, page: int, rows: int, columns: int) -> None:
        """Subscribe to button graphics for grid."""
        batch = []
        for row in range(rows):
            for col in range(columns):
                msg_id = self._get_next_id()
                self._subscriptions[msg_id] = {"page": page, "row": row, "col": col}
                batch.append({
                    "id": msg_id,
                    "method": "subscription",
                    "params": {
                        "input": {"location": {"pageNumber": page, "column": col, "row": row}},
                        "path": "preview.graphics.location"
                    }
                })
        await self._send(batch)
    
    async def _handle_message(self, item: dict) -> None:
        """Process a single tRPC response."""
        msg_id = item.get("id")
        result = item.get("result", {})
        data = result.get("data")
        
        if not data or "image" not in data:
            return
        
        sub = self._subscriptions.get(msg_id)
        if not sub:
            return
        
        image_data = data.get("image")
        is_used = data.get("isUsed", False)
        
        if image_data and self.on_image:
            try:
                img_bytes = self._decode_image(image_data)
                img = Image.open(BytesIO(img_bytes))
                self.on_image(sub["page"], sub["row"], sub["col"], img, is_used)
            except Exception as e:
                print(f"[WS] Image decode error: {e}")
    
    async def _message_loop(self) -> None:
        """Main message receiving loop."""
        while self._running and self._ws and not self._ws.closed:
            try:
                msg = await self._ws.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "PING":
                        await self._ws.send_str("PONG")
                        continue
                    
                    parsed = json.loads(msg.data)
                    items = parsed if isinstance(parsed, list) else [parsed]
                    for item in items:
                        await self._handle_message(item)
                        
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WS] Error: {e}")
                break
    
    async def connect(self, page: int = 1, rows: int = 8, columns: int = 9) -> None:
        """Connect and subscribe to button graphics."""
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(self.url)
        self._running = True
        
        # Subscribe to pages first
        await self._send([
            {"id": self._get_next_id(), "method": "subscription", "params": {"path": "pages.watch"}},
            {"id": self._get_next_id(), "method": "subscription", "params": {"path": "userConfig.watchConfig"}}
        ])
        
        await asyncio.sleep(0.1)
        await self._subscribe_graphics(page, rows, columns)
    
    async def run(self) -> None:
        """Run the message loop (call after connect)."""
        await self._message_loop()
    
    async def disconnect(self) -> None:
        """Close the connection."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()


class Companion:
    def __init__(self, ip="127.0.0.1", port="8000"):
        self.ip = ip
        self.port = port
        self._ws_client: Optional[CompanionWebSocket] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _on_button_image(self, page: int, row: int, col: int, img: Image.Image, is_used: bool) -> None:
        """Handle received button image - read bottom-right pixel."""
        width, height = img.size
        pixel = img.getpixel((width - 1, height - 1))

        # IMPORTANT: do not iterate over a mutable global list across threads.
        for conn in midi.snapshot_connections():
            if conn.page == page:
                note_str = f"{page}/{row}/{col}"
                conn.set_color(note_str, pixel)

    async def start(self, page: int = 1, rows: int = 9, columns: int = 9) -> None:
        """Connect to Companion WebSocket and start receiving images."""
        self._ws_client = CompanionWebSocket(self.ip, self.port)
        self._ws_client.on_image = self._on_button_image
        
        print(f"Connecting to Companion at {self._ws_client.url}...")
        await self._ws_client.connect(page, rows, columns)
        print(f"Connected! Receiving {rows}x{columns} buttons from page {page}")
        
        await self._ws_client.run()
    
    def _run_in_thread(self, page: int, rows: int, columns: int) -> None:
        """Thread target - creates event loop and runs async code."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self.start(page, rows, columns))
        finally:
            self._loop.close()
            self._loop = None
    
    def start_background(self, page: int = 1, rows: int = 9, columns: int = 9) -> None:
        """Start polling in a background thread. Non-blocking."""
        if self._thread and self._thread.is_alive():
            print("Already running!")
            return
        
        self._thread = threading.Thread(
            target=self._run_in_thread,
            args=(page, rows, columns),
            daemon=True
        )
        self._thread.start()
        print("Started Companion polling in background thread")
    
    def stop_background(self) -> None:
        """Stop the background polling."""
        if self._ws_client and self._loop:
            asyncio.run_coroutine_threadsafe(self._ws_client.disconnect(), self._loop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        print("Stopped background polling")
    
    async def stop(self) -> None:
        """Disconnect from Companion (async version)."""
        if self._ws_client:
            await self._ws_client.disconnect()
            print("Disconnected from Companion")

    def down(self, button):
        requests.post(f"http://{self.ip}:{self.port}/api/location/{button}/down")

    def up(self, button):
        requests.post(f"http://{self.ip}:{self.port}/api/location/{button}/up")


COMPANION = Companion()


if __name__ == "__main__":
    async def main():
        companion = Companion()
        try:
            await companion.start(page=1, rows=9, columns=8)
        except KeyboardInterrupt:
            pass
        finally:
            await companion.stop()
    
    asyncio.run(main())