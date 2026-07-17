# PSX Tracker — Live API service

A small FastAPI service that serves delayed PSX screener snapshots over REST, WebSocket, and
SSE, with a provider abstraction so the data source can start as the unofficial `psxdata` scraper
and later be swapped for a licensed vendor without touching the frontend contract.

Built from and closely follows the implementation plan in this repo's source document — this is the
actual working code, not just the plan.

**Status: built and tested in this session.** 15/15 tests pass; REST, WebSocket, SSE, and the
admin-refresh endpoint were all manually exercised and confirmed working, using the built-in `mock`
provider (see "Providers" below for why).

## Read this first: the legal situation is real, not boilerplate

PSX's own [Data Services & Vending](https://www.psx.com.pk/psx/product-and-services/data-services-vending)
page and data-portal notices state that dissemination, transmission, and commercial use of PSX
market data — live or delayed — requires authorization from PSX. `psxdata` being MIT-licensed and
keyless does **not** grant you redistribution rights to PSX's underlying data; it just makes the
scraping easy. Two ready-to-send email templates (to PSX and to Capital Stake, PSX's listed
authorized vendor) are in [`docs/outreach-emails.md`](docs/outreach-emails.md).

**Recommended posture:** build and test privately now (this repo does that). Get written
clarification from PSX before putting live/delayed quotes on a public website. If PSX says you need
a license, swap `PROVIDER=psxdata` for a `CapitalStakeProvider` adapter — the interface in
`providers.py` is designed for exactly that swap.

## What's actually in this repo

```
psx-tracker/
├─ live_api/
│  ├─ app/
│  │  ├─ main.py            FastAPI app: REST + WebSocket + SSE + admin + poll loop
│  │  ├─ providers.py        MarketDataProvider protocol, PsxDataProvider, MockProvider
│  │  ├─ models.py           Pydantic response schemas
│  │  ├─ ws.py                WebSocket connection hub with per-client symbol filters
│  │  ├─ settings.py          Env config + PSX market-hours/holiday awareness
│  │  └─ holidays_2026.json  Official PSX 2026 holiday calendar (sourced live, see file)
│  ├─ tests/                 15 tests: normalization, REST, WebSocket
│  ├─ requirements.txt
│  ├─ Dockerfile
│  ├─ docker-compose.yml
│  └─ .env.example
├─ frontend/
│  └─ index.html             Standalone dashboard demo (works with zero backend, or points at a live one)
├─ .github/workflows/live-api-ci.yml   Path-filtered — won't fire on your daily data-only commits
└─ docs/outreach-emails.md   PSX + Capital Stake licensing email templates
```

## Providers: `mock` vs `psxdata`

This ships with **two** providers, not one:

- **`mock`** (default) — synthetic, randomly-walking quotes. No network access required. This is
  what all the tests use, and it's what you should leave on for local dev, demos, and CI.
- **`psxdata`** — the real (unofficial) scraper. It needs outbound internet access to
  `dps.psx.com.pk` at runtime. When tested from this sandboxed build environment (which has no
  route to that host) it failed with a clean `PSXAuthError`, and — this is the important part —
  the service **did not crash**: `/healthz` reported `ok: false` with the error visible, quotes
  endpoints kept serving the last-known cache, and everything else kept working. That's the
  intended failure mode. From a normal machine or cloud host with regular internet access, this
  provider should reach PSX's public site directly. `psxdata.quote()` returns a screener/fundamentals
  snapshot and its cache refreshes at roughly 15-minute intervals; it is not a tick-level feed.

Switch providers with one env var:
```
PROVIDER=mock       # or
PROVIDER=psxdata
```

## Quickstart

```bash
cd psx-tracker
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r live_api/requirements.txt
cp live_api/.env.example .env
uvicorn live_api.app.main:app --reload --host 127.0.0.1 --port 8000
```

Then:
```bash
curl http://127.0.0.1:8000/healthz
curl "http://127.0.0.1:8000/api/v1/quotes?symbols=OGDC,PPL,HBL"
curl http://127.0.0.1:8000/api/v1/meta
```

Open `frontend/index.html` directly in a browser for a working demo dashboard — it runs a fully
offline synthetic-data mode out of the box, or point `LIVE_API_BASE` at your running server to see
real REST + WebSocket updates.

Run the tests:
```bash
pytest -q live_api/tests
```

## API surface

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /healthz` | Liveness + last error, for platform health checks | none |
| `GET /api/v1/quotes?symbols=OGDC,PPL` | Current cached quotes | public |
| `GET /api/v1/meta` | Provider, market-open flag, poll interval, last success/error | public |
| `WS /ws/quotes?symbols=OGDC,PPL` | Push updates, filtered per connection | public |
| `GET /sse/quotes?symbols=OGDC,PPL` | Same, over Server-Sent Events | public |
| `POST /admin/refresh` | Force an immediate poll | Bearer token (`ADMIN_BEARER_TOKEN`) |

The normalized quote contract mirrors the source fields: `price`, `change_pct`, `change_1y_pct`,
`pe_ratio`, `dividend_yield`, `market_cap`, `free_float`, and `volume_avg_30d`. The source does not
provide absolute change, today's volume, or a row timestamp. `change_points_derived` is reconstructed
from `price` and `change_pct` and is explicitly approximate; `source_timestamp` is therefore null,
while `fetched_at` records when this service retrieved the row.

Every quote also carries `delayed: true` and a `stale` flag that flips true once nothing has refreshed
successfully for `STALE_AFTER_SECONDS` (default 20 min). The frontend labels the reconstructed point
change and 30-day average volume explicitly rather than implying live ticks or today's volume.

## Market-hours and holiday awareness

`settings.py` encodes PSX's published trading hours (fetched from psx.com.pk during this build):

- Mon–Thu: 09:32–15:30 PKT
- Fri: 09:17–12:00 and 14:32–16:30 PKT

and the **official 2026 PSX holiday calendar** (also fetched live from
`psx.com.pk/psx/exchange/general/calendar-holidays`), in `holidays_2026.json`. Outside market
hours/holidays, the poll loop backs off to `OFF_HOURS_POLL_SECONDS` (default 5 min) instead of
polling at full cadence for nothing. Note: several of PSX's holidays (Eid, Ashura, Milad-un-Nabi)
are moon-sighting-dependent and PSX explicitly reserves the right to adjust them — re-check the
official page close to those dates and update the JSON file, or add a `holidays_2027.json` when the
year rolls over.

## Deployment

Dockerfile and docker-compose are ready as-is. Quick cost/fit summary from the plan (verify current
pricing before committing):

| Platform | Best for | Watch out for |
|---|---|---|
| Fly.io | Cheapest always-on (~$2/mo smallest shared machine) | Slightly more hands-on than Render/Railway |
| Railway | Easiest GitHub-connected DX | Always-on cost climbs faster than Fly at this size |
| Render | Fast proof-of-concept | Free tier spins down after 15 min idle, ephemeral disk |
| DigitalOcean App Platform | Clean PaaS, $5/mo+ | Free tier is static-only, not for this service |
| AWS App Runner | If you're already on AWS | No permanent free tier, more moving parts |

Whichever you pick: deploy `live_api/` from a **dedicated branch** or disable platform auto-deploy
and rely on the path-filtered GitHub Action instead, so your daily `data/latest.json` commits (from
your existing pipeline) don't trigger pointless redeploys of this service.

## Rollback / kill switch

Nothing here is designed to be hard to turn off:
- Set `PROVIDER=mock` to instantly stop hitting PSX's site while keeping the API up.
- Point the frontend back at only `data/latest.json` (your existing daily pipeline) to drop the live
  layer entirely — it was designed as a non-breaking addition, not a replacement.
- If PSX licensing turns out to require action you're not ready to take, this is the fastest lever:
  turn off public live endpoints, keep the daily snapshot site running unchanged.

## Suggested next steps

1. Send the two outreach emails in `docs/outreach-emails.md` (PSX + Capital Stake) — do this in
   parallel with building, not after.
2. Deploy to Fly.io or Railway for a private/internal test with `PROVIDER=psxdata`, confirm it
   actually reaches `dps.psx.com.pk` from that host (it couldn't from this sandboxed build
   environment — normal cloud hosts should be fine).
3. Wire the frontend into your existing `psx-tracker` site's bootstrap sequence
   (`data/latest.json` → REST → WebSocket, as in `frontend/index.html`).
4. Once PSX/Capital Stake respond, decide: ship with `psxdata` under whatever terms they give you,
   or build a `CapitalStakeProvider` in `providers.py` following the same `MarketDataProvider`
   interface as the two providers already there.
