from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import request
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from .types import RealtimeEvent, Track


@dataclass(frozen=True)
class TakOpsCredentials:
    username: str
    password: str


@dataclass(frozen=True)
class TakOpsLocation:
    callsign: str
    lat: float
    lon: float
    altitudeMeters: float | None = None
    accuracyMeters: float | None = None
    headingDegrees: float | None = None
    speedMetersPerSecond: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if value is not None}


class TakOpsSubscription:
    def __init__(self) -> None:
        self._closed = threading.Event()
        self._socket: Any = None

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def set_socket(self, socket: Any) -> None:
        self._socket = socket

    def close(self) -> None:
        self._closed.set()
        if self._socket is not None:
            self._socket.close()


class TakOpsClient:
    def __init__(
        self,
        base_url: str,
        credentials: TakOpsCredentials | None = None,
        reconnect: bool = True,
        reconnect_base_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.credentials = credentials
        self.reconnect = reconnect
        self.reconnect_base_seconds = reconnect_base_seconds
        self.reconnect_max_seconds = reconnect_max_seconds

    def subscribe(
        self,
        on_event: Callable[[RealtimeEvent], None] | None = None,
        on_snapshot: Callable[[RealtimeEvent], None] | None = None,
        on_track: Callable[[Track, RealtimeEvent], None] | None = None,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> TakOpsSubscription:
        subscription = TakOpsSubscription()
        thread = threading.Thread(
            target=self._run_subscription,
            args=(subscription, on_event, on_snapshot, on_track, on_open, on_close, on_error),
            daemon=True,
        )
        thread.start()
        return subscription

    def publish_location(self, location: TakOpsLocation) -> dict[str, Any]:
        body = json.dumps(location.to_json()).encode("utf-8")
        req = request.Request(
            urljoin(self.base_url, "api/location"),
            data=body,
            method="POST",
            headers={
                **self._auth_headers(),
                "content-type": "application/json",
            },
        )

        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_recent_track_log(self, limit: int = 100) -> dict[str, Any]:
        query = urlencode({"limit": str(limit)})
        req = request.Request(
            urljoin(self.base_url, f"api/tracks/log?{query}"),
            headers=self._auth_headers(),
        )

        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _run_subscription(
        self,
        subscription: TakOpsSubscription,
        on_event: Callable[[RealtimeEvent], None] | None,
        on_snapshot: Callable[[RealtimeEvent], None] | None,
        on_track: Callable[[Track, RealtimeEvent], None] | None,
        on_open: Callable[[], None] | None,
        on_close: Callable[[], None] | None,
        on_error: Callable[[BaseException], None] | None,
    ) -> None:
        try:
            import websocket
        except ImportError as error:
            if on_error:
                on_error(error)
            return

        attempt = 0

        while not subscription.closed:
            try:
                socket = websocket.WebSocketApp(
                    self._realtime_url(),
                    header=self._websocket_headers(),
                    on_open=lambda _socket: on_open() if on_open else None,
                    on_close=lambda _socket, _code, _reason: on_close() if on_close else None,
                    on_error=lambda _socket, error: on_error(error) if on_error else None,
                    on_message=lambda _socket, message: self._handle_message(
                        message,
                        on_event,
                        on_snapshot,
                        on_track,
                        on_error,
                    ),
                )
                subscription.set_socket(socket)
                socket.run_forever()
                attempt = 0
            except BaseException as error:
                if on_error:
                    on_error(error)

            if subscription.closed or not self.reconnect:
                return

            attempt += 1
            delay = min(
                self.reconnect_base_seconds * 2 ** min(attempt - 1, 5),
                self.reconnect_max_seconds,
            )
            time.sleep(delay)

    def _handle_message(
        self,
        message: str | bytes,
        on_event: Callable[[RealtimeEvent], None] | None,
        on_snapshot: Callable[[RealtimeEvent], None] | None,
        on_track: Callable[[Track, RealtimeEvent], None] | None,
        on_error: Callable[[BaseException], None] | None,
    ) -> None:
        try:
            raw = message.decode("utf-8") if isinstance(message, bytes) else message
            event = json.loads(raw)
            if on_event:
                on_event(event)

            event_type = event.get("type")
            if event_type == "sync.snapshot" and on_snapshot:
                on_snapshot(event)
            elif event_type == "track.upserted" and on_track:
                on_track(event["payload"]["track"], event)
        except BaseException as error:
            if on_error:
                on_error(error)

    def _auth_headers(self) -> dict[str, str]:
        if self.credentials is None:
            return {}

        token = f"{self.credentials.username}:{self.credentials.password}".encode("utf-8")
        return {
            "authorization": f"Basic {base64.b64encode(token).decode('ascii')}",
        }

    def _websocket_headers(self) -> list[str]:
        return [f"{key}: {value}" for key, value in self._auth_headers().items()]

    def _realtime_url(self) -> str:
        parsed = urlparse(urljoin(self.base_url, "realtime"))
        scheme = "wss" if parsed.scheme == "https" else "ws"
        return urlunparse(parsed._replace(scheme=scheme))
