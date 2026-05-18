from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class TrackGeometry(TypedDict):
    type: Literal["Point"]
    coordinates: tuple[float, float]
    altitudeMeters: NotRequired[float]


class ProtocolMetadata(TypedDict, total=False):
    kind: Literal["cot"]
    uid: str
    type: str
    how: str
    detail: dict[str, Any]


class Track(TypedDict, total=False):
    id: str
    tenantId: str
    workspaceId: str
    missionId: str | None
    connectionId: str | None
    callsign: str | None
    label: str | None
    trackType: str
    affiliation: Literal["friendly", "hostile", "neutral", "unknown"]
    geometry: TrackGeometry
    courseDegrees: float | None
    speedMetersPerSecond: float | None
    observedAt: str
    staleAt: str | None
    status: Literal["active", "stale", "removed"]
    protocol: ProtocolMetadata
    createdAt: str
    updatedAt: str
    version: int


class RealtimeEvent(TypedDict, total=False):
    id: str
    schemaVersion: int
    type: str
    occurredAt: str
    tenantId: str
    workspaceId: str | None
    missionId: str | None
    payload: dict[str, Any]
