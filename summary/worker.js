// NZIHL Game Summary — CORS pass-through Worker (Cloudflare)
// Fetches an nzihl/nzwihl box-score page server-side and returns it with CORS
// headers so the static Game Summary page can read and parse it.
//
// Deploy (no local tooling needed):
//   1. dash.cloudflare.com → Workers & Pages → Create → Create Worker
//   2. Name it e.g. "nzihl-box" → Deploy → "Edit code"
//   3. Replace the sample with THIS file → Deploy
//   4. Copy the URL (https://nzihl-box.<your-subdomain>.workers.dev)
//   5. Paste that URL into summary.html  (const WORKER = "…")
//
// Usage:  https://nzihl-box.<sub>.workers.dev/?url=<encoded nzihl box-score URL>

export default {
  async fetch(request) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Cache-Control": "no-store",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const target = new URL(request.url).searchParams.get("url");
    if (!target) return new Response("missing ?url", { status: 400, headers: cors });

    // Only allow the two league sites — this is a box-score proxy, nothing else.
    if (!/^https:\/\/www\.(nzihl|nzwihl)\.com\//i.test(target))
      return new Response("forbidden", { status: 403, headers: cors });

    try {
      const upstream = await fetch(target, {
        headers: { "User-Agent": "Mozilla/5.0 (NZIHL Broadcast Game Summary)" },
        cf: { cacheTtl: 0, cacheEverything: false },
      });
      const body = await upstream.text();
      return new Response(body, {
        status: upstream.status,
        headers: { ...cors, "Content-Type": "text/html; charset=utf-8" },
      });
    } catch (e) {
      return new Response("upstream error: " + e, { status: 502, headers: cors });
    }
  },
};
