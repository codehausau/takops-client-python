# TAKOps Python Client

Python client for passively consuming TAKOps realtime track events.

## Install

```bash
pip install takops-client
```

## Passive Consumer

```python
from takops_client import TakOpsClient, TakOpsCredentials

client = TakOpsClient(
    "https://takops.example.com",
    credentials=TakOpsCredentials("takops", "codehaus-takops-123"),
)

subscription = client.subscribe(
    on_track=lambda track, event: print(track["id"], track["geometry"]["coordinates"]),
)

try:
    while True:
        pass
except KeyboardInterrupt:
    subscription.close()
```

## Optional Active Location Publish

```python
from takops_client import TakOpsLocation

client.publish_location(
    TakOpsLocation(
        callsign="ops-01",
        lat=-34.845,
        lon=138.715,
    )
)
```

## Authentication

If TAKOps is behind Traefik Basic Auth, pass `TakOpsCredentials`. The client
sends the Basic Auth header for both HTTP and WebSocket requests.
