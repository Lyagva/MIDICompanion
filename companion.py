import requests


class Companion:
    def __init__(self, ip: str = "127.0.0.1", port: str = "8000"):
        self.ip = ip
        self.port = port

    def down(self, button: str) -> None:
        try:
            requests.post(f"http://{self.ip}:{self.port}/api/location/{button}/down")
        except Exception:
            # Best-effort: ignore network errors
            pass

    def up(self, button: str) -> None:
        try:
            requests.post(f"http://{self.ip}:{self.port}/api/location/{button}/up")
        except Exception:
            pass


COMPANION = Companion()

