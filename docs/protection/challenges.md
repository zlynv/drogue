# Challenges (CAPTCHA)

## What is a challenge?

Instead of answering page traffic with a bare `429` JSON body, Drogue can serve an interstitial containing a challenge widget (CAPTCHA). The visitor solves it, their answer is verified server side with the provider's API, and the visitor receives a signed pass cookie that unlocks the page for a configurable period. Used as the escalation step after rate limits, this cleanly separates humans from bot floods on HTML routes.

## Why it matters

Rate limiting blocks bad traffic but cannot tell an attacked visitor apart from the attack. A challenge page fixes this for human-facing flows:

- Real visitors click a widget and keep browsing
- Bots fail the check and stay on the denial path
- Pass cookies are HMAC-signed, expiry-based, and bound to the client, so a solved cookie cannot be farmed or shared across a botnet

## Quick start (FastAPI)

```python
import os
from fastapi import FastAPI
from drogue.adapters.fastapi import DrogueLimiter
from drogue.core.config import DrogueConfig
from drogue.core.storage.redis import RedisStorage

signing_key = os.environ["DROGUE_CHALLENGE_SIGNING_KEY"]   # >= 32 chars
site_key = os.environ["TURNSTILE_SITE_KEY"]
secret = os.environ["TURNSTILE_SECRET"]

config = DrogueConfig(
    challenge_enabled=True,
    challenge_signing_key=signing_key,
    challenge_site_key=site_key,
    challenge_secret=secret,
)

app = FastAPI()
storage = RedisStorage("redis://localhost")

limiter = DrogueLimiter(
    app,
    storage=storage,
    config=config,
    # challenge_provider is auto-built (Turnstile) from the config keys;
    # pass your own provider here to use a different challenge system
)
```

The limiter wires two routes: `GET /drogue/challenge` (the interstitial) and `POST /drogue/verify` (the answer). When a denial hits a `GET` request whose `Accept` header welcomes HTML (`text/html`, or `*/*`), the response is the challenge page instead of plain JSON; everything else (POST bodies, CORS preflights, API clients) keeps the normal denial.

Never commit `challenge_signing_key` or the provider secret: read them from environment variables or your secret manager.

## Configuration (DrogueConfig)

| Field | Default | Description |
|-------|---------|-------------|
| `challenge_enabled` | `False` | Master switch |
| `challenge_signing_key` | `""` | HMAC seed for pass cookies, at least 32 chars, separate from the provider secret |
| `challenge_cookie_name` | `"drogue_pass"` | Pass cookie name |
| `challenge_cookie_ttl` | `86400.0` | Pass cookie lifetime, seconds |
| `challenge_token_ttl` | `300.0` | How long a provider token stays claimed (single use) |
| `challenge_failure_mode` | `"block"` | Provider outage behavior: `block` re-serves 503 denial, `allow` degrades to the normal denial without erroring |
| `challenge_failure_threshold` | `3` | Failed verifications in the window before escalation |
| `challenge_rate_limit` | `20` | Verify attempts allowed per client per `challenge_rate_window` |
| `challenge_rate_window` | `60.0` | Verify rate-limit window, seconds |
| `challenge_verify_url` | `"/drogue/verify"` | Verify endpoint path (interstitial lives next to it at `.../challenge`) |
| `challenge_site_key` | `""` | Turnstile site key |
| `challenge_secret` | `""` | Turnstile secret key |
| `challenge_action` | `None` | Optional Turnstile `action` to require |

## Security model

- **Replay protection:** every token is claimed in storage via `compare_and_swap` *before* the provider round-trip. A token verifies once; rejected tokens stay claimed (dead for the TTL). On an undecided provider outage the claim is released so the visitor can retry.
- **Verify endpoint rate limiting:** unsolved attempts are cheap to generate, so the verify endpoint itself is rate limited (default 20 attempts/minute per client). Escalating spam of answers therefore cannot be used to bounce load onto the provider.
- **Failure escalation:** repeated failed verifications (default 3 in 5 minutes) feed the existing `AutoBanManager` (`record_violation`) and poison trust, so a client brute-forcing challenges gets auto-banned instead of getting unlimited retries.
- **Pass cookies:** the value is `expiry.ipHash16.hmacSHA256-expiry-ip-hash`, keyed by `SHA-256("drogue-challenge-pass-v1::" + signing_key)`. Validation compares digests, never plain strings. Changing `challenge_signing_key` invalidates all issued passes.
- **Open-redirect defense:** the `next` field set by the interstitial survives only same-site relative paths. Absolute URLs and `//evil.com` collapse to `/`.
- **No cookie grant on outage:** a provider outage never mints a pass cookie, so bots cannot force failures to obtain a pass.

## Custom providers

A provider implements `drogue.challenge.base.ChallengeProvider`:

```python
from drogue.challenge.base import ChallengeErrorCode, Verification

class MyCaptchaProvider:
    field_name = "my_token"  # form input expected in the challenge page

    def render_html(self) -> str:
        return "<script src=... ></script>"

    async def verify(self, token: str, remote_ip: str | None) -> Verification:
        ...  # raise ChallengeVerificationError(REJECTED) on wrong address
```

Pass `challenge_provider=YourProvider()` to `DrogueLimiter` instead of relying on the auto-built Turnstile instance. The manager handles cookies, replay claims, failure escalation, rate limiting, and page rendering; providers only verify tokens.

## Observability

`limiter.get_challenge_manager().get_stats()` returns counters: `issued`, `passed`, `failed`, `banned`, `rate_limited`. A sustained `rate_limited` or high `failed:banned` ratio is an active bot flood signal.
