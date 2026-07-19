// NZIHL Game Summary — CORS pass-through Worker (Cloudflare)
// Fetches an nzihl/nzwihl box-score (and, as of 2026-07-05, season-stats and
// standings) page server-side and returns it with CORS headers so the static
// Game Summary page can read and parse it.
//
// 2026-07-12: also serves the Player Lower Thirds CONTROL CHANNEL — a
// Durable-Object-backed relay between the phone control page
// (hockey/lowerthirds/) and the Activity Banner overlay, since they're two
// different devices/browser tabs and need live (sub-second) hand-off. See
// the ControlChannel class below and DEPLOY.md in this same folder for the
// exact deploy steps (Durable Objects require a wrangler deploy, not the
// dashboard Quick Edit box this worker was originally pasted into).
//
// Deploy (no local tooling needed, for the box-score proxy alone):
//   1. dash.cloudflare.com → Workers & Pages → Create → Create Worker
//   2. Name it e.g. "nzihl-box" → Deploy → "Edit code"
//   3. Replace the sample with THIS file → Deploy
//   4. Copy the URL (https://nzihl-box.<your-subdomain>.workers.dev)
//   5. Paste that URL into summary.html  (const WORKER = "…")
//
// Deploy (to ADD the control channel — requires wrangler, see DEPLOY.md):
//   wrangler deploy   (uses wrangler.toml in this same folder)
//
// Usage:
//   Box-score proxy:  GET  /?url=<encoded nzihl/esportsdesk URL>
//   Control channel:  GET  /control/<team-slug>
//                      POST /control/<team-slug>  {action, token, ...}
//   Starting lineup:   GET  /lineup/<team-slug>
//                      POST /lineup/<team-slug>   {action, token, ...}

// Shared-secret token gating CONTROL CHANNEL writes only (reads are open —
// same trust model as the rest of this repo family: no real auth anywhere,
// an unguessable value embedded in the public overlay/phone page source
// deters casual abuse, matching how WORKER itself is just pasted into every
// page as a plain constant). Both hockey/lowerthirds/ (phone) and
// hockey/activity-banner/ (overlay) embed this exact same string.
const CONTROL_TOKEN = "l3-EXleXBAfHbgn7P1qHeJ81U1K";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(request, env) {
    // 2026-07-20 resilience pass (see matchavez/hockey's nzihl_resilience_audit_2026_07_20
    // memory / the estate-wide audit this is a continuation of): every routing branch below
    // used to have NO top-level safety net. Any uncaught exception anywhere in this handler
    // -- a routing bug, an unexpected env shape, anything inside the Durable Object -- fell
    // straight through to Cloudflare's own generic error page: no CORS headers, not JSON,
    // nothing the client's error handling (which expects a normal HTTP error response) was
    // built to parse. A browser fetch() against that looks like an opaque "Failed to fetch"
    // with zero diagnostic value client-side. Wrap everything so a bug in this Worker degrades
    // to a clean, recognisable, CORS-safe error instead of an unrecoverable opaque failure.
    try {
      return await routeRequest(request, env);
    } catch (e) {
      console.error("[worker] unhandled exception:", e && e.stack || e);
      return new Response("worker internal error: " + (e && e.message || e), {
        status: 500,
        headers: CORS,
      });
    }
  },
};

async function routeRequest(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    if (url.pathname.startsWith("/control/")) {
      return handleControl(request, env, url);
    }

    // Starting Lineup persistent state (2026-07-13) — same per-team Durable
    // Object as /control/, different storage key. Unlike the fire-once L3
    // channel, this is durable "current starting six" state the display page
    // (hockey/startinglineup/) reads on load + polls, and the control page
    // (hockey/startinglineup/control/) writes slot-by-slot. Reusing the
    // existing ControlChannel class (not a new DO) means redeploying needs
    // NO new migration in wrangler.toml — just `wrangler deploy` again.
    if (url.pathname.startsWith("/lineup/")) {
      return handleControl(request, env, url);
    }

    // ---- existing box-score / stats / standings CORS proxy (unchanged) ----
    const target = url.searchParams.get("url");
    if (!target) return new Response("missing ?url", { status: 400, headers: CORS });

    // Allowlist of exact endpoints this proxy will fetch on someone's behalf —
    // intentionally narrow, not a general CORS bypass. `www.nzihl.com` /
    // `www.nzwihl.com` is the original box-score host; box scores were later
    // switched to scrape `admin.esportsdesk.com` instead. `stats_1team.cfm`
    // backs the (currently parked) season-totals demo; `standings.cfm` backs
    // the season-record pill in the header (Mat, 2026-07-06).
    const ALLOWED = [
      /^https:\/\/www\.(nzihl|nzwihl)\.com\//i,
      /^https:\/\/admin\.esportsdesk\.com\/leagues\/hockey_boxscores\.cfm\?/i,
      /^https:\/\/admin\.esportsdesk\.com\/leagues\/stats_1team\.cfm\?/i,
      /^https:\/\/admin\.esportsdesk\.com\/leagues\/standings\.cfm\?/i,
      // 2026-07-13 (playoff-readiness audit): schedules.cfm and stats_hockey.cfm were
      // NEVER on this allowlist, so every client-side fetch through the worker for
      // them has always 403'd with this Worker's own "forbidden" response (not an
      // esportsdesk-side failure) -- caught live via hockey/preflight/'s "NZIHL/NZWIHL
      // leaders"+"schedule" system cards (permanently red FAILED) and the club board's
      // FINAL-status chip (silently never populating, caught by an empty catch{}).
      // stats_hockey.cfm also backs the league-wide scoring-rank descriptor noted as a
      // "v1 simplification" in the Scoring Leaders project. Added here; needs a
      // `wrangler deploy` from summary/ to actually take effect (see DEPLOY.md).
      /^https:\/\/admin\.esportsdesk\.com\/leagues\/schedules\.cfm\?/i,
      /^https:\/\/admin\.esportsdesk\.com\/leagues\/stats_hockey\.cfm\?/i,
    ];
    if (!ALLOWED.some((re) => re.test(target)))
      return new Response("forbidden", { status: 403, headers: CORS });

    // 2026-07-20: this fetch had no timeout at all -- if admin.esportsdesk.com hangs instead
    // of erroring, the old code just hangs too, for however long the platform lets it, tying
    // up this Worker invocation and leaving the client waiting far longer than its own 8s
    // client-side abort should ever need to cover. Fail fast and clean instead.
    const UPSTREAM_TIMEOUT_MS = 10000;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), UPSTREAM_TIMEOUT_MS);
    try {
      const upstream = await fetch(target, {
        headers: { "User-Agent": "Mozilla/5.0 (NZIHL Broadcast Game Summary)" },
        cf: { cacheTtl: 0, cacheEverything: false },
        signal: ctrl.signal,
      });
      const body = await upstream.text();
      return new Response(body, {
        status: upstream.status,
        headers: { ...CORS, "Content-Type": "text/html; charset=utf-8" },
      });
    } catch (e) {
      const timedOut = e && e.name === "AbortError";
      return new Response((timedOut ? "upstream timeout after " + UPSTREAM_TIMEOUT_MS + "ms: " : "upstream error: ") + target,
        { status: timedOut ? 504 : 502, headers: CORS });
    } finally {
      clearTimeout(t);
    }
}

// ============================================================
// CONTROL CHANNEL — routes /control/<slug> to a per-team Durable Object.
// ============================================================
async function handleControl(request, env, url) {
  const parts = url.pathname.split("/").filter(Boolean); // ["control"|"lineup", "<slug>"]
  const slug = (parts[1] || "").toLowerCase();
  if (!slug) return json({ error: "missing team slug — use /control/<slug> or /lineup/<slug>" }, 400);
  if (!env.CONTROL) {
    // Durable Object binding not deployed yet — degrade with a clear,
    // recognisable error the phone/overlay pages can detect and show a
    // "worker not deployed yet" notice for, per the brief.
    return json({ error: "control channel not deployed", code: "NO_DO_BINDING" }, 501);
  }
  // 2026-07-20: this call had zero error handling -- any exception thrown inside the
  // Durable Object (a storage hiccup, an edge case in state handling, anything) propagated
  // straight out uncaught, breaking CORS and the JSON contract the phone/overlay pages expect.
  // Both Player L3 (pollControl(), every 750ms on 2 live overlay pages) and Starting Lineup
  // route through here, so this single try/catch is the highest-leverage fix in this file.
  try {
    const id = env.CONTROL.idFromName(slug);
    const stub = env.CONTROL.get(id);
    const doResp = await stub.fetch(request);
    const body = await doResp.text();
    return new Response(body, {
      status: doResp.status,
      headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
    });
  } catch (e) {
    console.error("[worker] control channel error for slug \"" + slug + "\":", e && e.stack || e);
    return json({ error: "control channel error: " + (e && e.message || e), code: "DO_ERROR" }, 502);
  }
}

// ============================================================
// Durable Object: one instance per team slug, holding the live
// queue/fire/clear state for that team's Player Lower Thirds.
//
// State shape (persisted in DO storage under key "state"):
//   {
//     status: "idle" | "queued" | "fired",
//     player: { team_slug, role, number, name, position } | null,
//     fact: string | null,
//     include_fact: boolean,
//     fire_id: string | null,      // unique per fire, lets the overlay
//                                   // detect "this is a NEW fire" vs a
//                                   // stale poll re-reading the same one
//     fired_at: epoch_ms | null,
//     expires_at: epoch_ms | null, // fired_at + 10000, absolute so it
//                                   // survives an overlay page refresh
//     interrupted_at: epoch_ms | null,  // set when the overlay reports a
//                                   // fire got blocked/killed by an auto
//                                   // goal/penalty banner — phone shows
//                                   // "interrupted — still queued" while
//                                   // this is recent
//     updated_at: epoch_ms,
//   }
//
// Actions (POST body {action, token, ...}), all require token except reads:
//   "queue"      — phone taps a pill. body: {player, fact, include_fact}
//   "fire"       — phone taps FIRE. body: {player, fact, include_fact}
//                  (re-sent so any last-second edits/toggle state ride
//                  along, per the brief). Always succeeds at the state
//                  layer — the OVERLAY is the one that knows whether an
//                  auto banner is currently live, so collision rejection
//                  happens client-side: the overlay sees the new fire_id,
//                  checks its own banner-busy flag, and either renders the
//                  L3 or immediately posts "interrupt" back (below).
//   "clear"      — phone taps CLEAR, or wants to deselect. Resets to idle.
//   "interrupt"  — OVERLAY reports a fire was blocked (auto banner was
//                  already live when the fire arrived) or an already-live
//                  L3 was just killed mid-display by a new auto banner.
//                  Reverts to "queued" (keeps player/fact for one-tap
//                  re-fire) and stamps interrupted_at.
// ============================================================
export class ControlChannel {
  constructor(state, env) {
    this.storage = state.storage;
    this.env = env;
  }

  defaultState() {
    return {
      status: "idle",
      player: null,
      fact: null,
      include_fact: false,
      fire_id: null,
      fired_at: null,
      expires_at: null,
      interrupted_at: null,
      updated_at: Date.now(),
    };
  }

  async readState() {
    let s = (await this.storage.get("state")) || this.defaultState();
    // Self-healing auto-expiry: if a fired L3's hold has elapsed, revert to
    // "queued" (not "idle") so the player stays selected for instant
    // re-fire, matching "player stays queued afterward" in the brief. This
    // runs on every read/write so a phone/overlay that reconnects after
    // the 10s window sees correct state without needing a cron trigger.
    const now = Date.now();
    if (s.status === "fired" && s.expires_at && now > s.expires_at) {
      s = { ...s, status: "queued", fire_id: null, fired_at: null, expires_at: null, updated_at: now };
      await this.storage.put("state", s);
    }
    return s;
  }

  async fetch(request) {
    if (new URL(request.url).pathname.startsWith("/lineup/")) {
      return this.handleLineup(request);
    }
    if (request.method === "GET") {
      return json(await this.readState());
    }
    if (request.method !== "POST") {
      return json({ error: "method not allowed" }, 405);
    }

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return json({ error: "invalid JSON body" }, 400);
    }
    const { action, token } = body || {};
    if (token !== CONTROL_TOKEN) {
      return json({ error: "unauthorized" }, 401);
    }

    const cur = await this.readState();
    const now = Date.now();
    let next;

    if (action === "queue") {
      next = {
        status: "queued",
        player: body.player || null,
        fact: body.fact ?? null,
        include_fact: !!body.include_fact,
        fire_id: null,
        fired_at: null,
        expires_at: null,
        interrupted_at: null,
        updated_at: now,
      };
    } else if (action === "fire") {
      next = {
        status: "fired",
        player: body.player || cur.player,
        fact: body.fact ?? cur.fact,
        include_fact: body.include_fact ?? cur.include_fact,
        fire_id: (crypto.randomUUID ? crypto.randomUUID() : String(now) + Math.random()),
        fired_at: now,
        expires_at: now + 10000,
        interrupted_at: null,
        updated_at: now,
      };
    } else if (action === "clear") {
      next = this.defaultState();
      next.updated_at = now;
    } else if (action === "interrupt") {
      next = {
        ...cur,
        status: cur.player ? "queued" : "idle",
        fire_id: null,
        fired_at: null,
        expires_at: null,
        interrupted_at: now,
        updated_at: now,
      };
    } else {
      return json({ error: "unknown action: " + action }, 400);
    }

    await this.storage.put("state", next);
    return json(next);
  }

  // ==========================================================
  // STARTING LINEUP (2026-07-13) — persistent per-team state under a
  // SEPARATE storage key ("lineup"), fully independent of the fire-once
  // L3 "state" above. Shape:
  //   { slots: { LF|CF|RF|LD|RD|GK: {number, name, position, photo} },
  //     updated_at: epoch_ms | null }
  // Unset slots are simply absent. `photo` is a nzihl-player-photos
  // manifest-relative path (or null), resolved by the control page at
  // set time so the display page never needs the manifest.
  //
  // Actions (POST {action, token, ...}; reads open, writes token-gated,
  // same trust model as the L3 channel):
  //   "set_slot" — {slot, player}  player=null clears that slot
  //   "set"      — {slots}         replace the whole lineup at once
  //   "clear"    — reset to empty
  // ==========================================================
  async readLineup() {
    return (await this.storage.get("lineup")) || { slots: {}, updated_at: null };
  }

  async handleLineup(request) {
    if (request.method === "GET") {
      return json(await this.readLineup());
    }
    if (request.method !== "POST") {
      return json({ error: "method not allowed" }, 405);
    }
    let body;
    try {
      body = await request.json();
    } catch (e) {
      return json({ error: "invalid JSON body" }, 400);
    }
    const { action, token } = body || {};
    if (token !== CONTROL_TOKEN) {
      return json({ error: "unauthorized" }, 401);
    }
    const SLOTS = ["LF", "CF", "RF", "LD", "RD", "GK"];
    const cur = await this.readLineup();
    const now = Date.now();
    let next;

    if (action === "set_slot") {
      if (!SLOTS.includes(body.slot)) {
        return json({ error: "unknown slot: " + body.slot }, 400);
      }
      next = { slots: { ...cur.slots }, updated_at: now };
      if (body.player) next.slots[body.slot] = body.player;
      else delete next.slots[body.slot];
    } else if (action === "set") {
      const slots = {};
      SLOTS.forEach((s) => {
        if (body.slots && body.slots[s]) slots[s] = body.slots[s];
      });
      next = { slots, updated_at: now };
    } else if (action === "clear") {
      next = { slots: {}, updated_at: now };
    } else {
      return json({ error: "unknown action: " + action }, 400);
    }

    await this.storage.put("lineup", next);
    return json(next);
  }
}
