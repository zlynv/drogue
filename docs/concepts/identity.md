# Identity Extraction

## Built-in extractors

### RemoteAddressExtractor (default)

Identifies clients by IP address. Handles `X-Forwarded-For` and `X-Real-IP`.

```python
from drogue.core.identity import RemoteAddressExtractor

extractor = RemoteAddressExtractor(
    trusted_proxies=["10.0.0.0/8"],
    proxy_header="x-forwarded-for",
    trust_x_real_ip=True,
)
```

### UserExtractor

Identifies by authenticated user ID. Returns `"anonymous"` for unauthenticated requests.

```python
from drogue.core.identity import UserExtractor

extractor = UserExtractor(
    user_id_key="user_id",
    anonymous_value="anonymous",
)
```

### HeaderExtractor

Identifies by any HTTP header value.

```python
from drogue.core.identity import HeaderExtractor

extractor = HeaderExtractor(header_name="x-api-key", fallback="anonymous")
```

### StaticKeyExtractor

Uses a fixed key for global rate limiting.

```python
from drogue.core.identity import StaticKeyExtractor

extractor = StaticKeyExtractor(key="global")
```

## Combining extractors

Use `+` or `|` to create composite extractors. First non-anonymous value wins:

```python
from drogue.core.identity import RemoteAddressExtractor, UserExtractor

extractor = UserExtractor() + RemoteAddressExtractor()
```

## Per-route overrides

```python
@app.get("/api/public")
@limiter.limit("100/minute", key_func=RemoteAddressExtractor())
async def public_endpoint(): ...

@app.get("/api/private")
@limiter.limit("10/minute", key_func=UserExtractor())
async def private_endpoint(): ...
```
