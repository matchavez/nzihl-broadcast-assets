# Deploying the Player Lower Thirds control channel

This adds a Durable-Object-backed control channel to the existing
`blue-butterfly-aa69.matchavez.workers.dev` worker (the same one that already
proxies box-score/stats/standings fetches for every overlay page). It's an
in-place update to that worker, not a new one.

**Why this can't be pasted into the dashboard's Quick Edit box like the
original worker.js was:** Durable Objects need a `wrangler.toml` migration
declared alongside the code, which Quick Edit doesn't support. `wrangler
deploy` is the only reliable path.

**Plan requirement:** none — confirmed against Cloudflare's current docs
(2026-07-12) that SQLite-backed Durable Objects (what `wrangler.toml` here
requests, via `new_sqlite_classes`) work on both the Workers Free and Workers
Paid plans. No upgrade needed. (I can't check your specific account's plan
tier from here — if `wrangler deploy` below errors out on the Durable
Objects step specifically, that's the first thing to check in the dashboard,
but it shouldn't happen.)

## Files

Both live in `nzihl-broadcast-assets/summary/` in this repo:
- `worker.js` — the full worker (existing CORS proxy, unchanged behavior,
  plus the new `/control/<slug>` routes and `ControlChannel` Durable Object
  class).
- `wrangler.toml` — deploy config. `name = "blue-butterfly-aa69"` targets
  your existing worker by name — **double-check this matches your actual
  worker's name in the dashboard** (Workers & Pages → your worker → the name
  shown at the top, not just the workers.dev subdomain, though they're
  usually the same when a worker was created without a custom name).

## Steps

1. Install wrangler if you don't already have it:
   ```
   npm install -g wrangler
   ```

2. From `nzihl-broadcast-assets/summary/`, log in (opens a browser):
   ```
   wrangler login
   ```

3. Deploy:
   ```
   wrangler deploy
   ```
   First deploy with the new Durable Object class will show a migration
   step (`ControlChannel` — new SQLite class) — confirm it.

4. Verify the box-score proxy still works (should return HTML, unchanged):
   ```
   curl "https://blue-butterfly-aa69.matchavez.workers.dev/?url=https%3A%2F%2Fadmin.esportsdesk.com%2Fleagues%2Fstandings.cfm%3Fclientid%3D7131%26leagueid%3D35499%26printPage%3D1"
   ```

5. Verify the control channel is live:
   ```
   curl "https://blue-butterfly-aa69.matchavez.workers.dev/control/pure-nz-admirals"
   ```
   Expect `{"status":"idle","player":null,...}` — a fresh Durable Object's
   default state. If you get `{"error":"control channel not deployed",...}`
   instead, the deploy didn't pick up the Durable Object binding — re-run
   `wrangler deploy` and watch its output for errors.

6. Tell me once this is live and I'll run the full fire → overlay →
   auto-hide → clear round-trip test and confirm the phone control page and
   Activity Banner overlay both talk to it correctly.

## About the "pending Activity Banner REDEPLOY" note in memory

Some of my notes mention an Activity Banner no-cache-origin worker REDEPLOY
as still pending. Checked against the actual current worker.js in this repo
before touching it: `admin.esportsdesk.com` is already in the ALLOWED list,
and per the Activity Banner project's own history, that redeploy went out
and was verified live on 2026-06-30. That part is done — nothing from this
change is riding along to "fix" it; that note in memory is just stale and
I've corrected it. This deploy is purely additive (the new `/control/`
routes + Durable Object) on top of an already-current worker.

## Rollback

If anything looks wrong after deploying, the previous worker.js (CORS proxy
only, no control channel) is in git history — `git log -- summary/worker.js`
— redeploy that version with `wrangler deploy` to revert. The Durable Object
class/migration doesn't need to be undone; an unused DO binding is harmless.

---

## 2026-07-13 — Starting Lineup endpoints added

`worker.js` gained `GET/POST /lineup/<team-slug>` (persistent per-team
starting-six state for `hockey/startinglineup/`). It reuses the existing
`ControlChannel` Durable Object with a separate storage key, so **no new
migration is needed** — redeploy is just:

```sh
cd nzihl-broadcast-assets/summary/   # must be IN this folder (see gotcha above)
wrangler deploy
```

Until redeployed, `/lineup/<slug>` falls through to the box-score proxy and
returns `missing ?url` (400) — the startinglineup pages detect this and show
a "worker needs redeploy" notice.
