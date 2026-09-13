/**
 * Cloudflare Worker — okuma API'si
 *
 * Supabase'in onunde duruyor. Iki isi var:
 *   1. service_role anahtarini tarayiciya hic gostermemek
 *   2. edge'de cache'leyip Supabase'i bosuna yormamak
 *
 * Uc uc nokta:
 *   GET /api/snapshot?symbol=ASELS   -> son metrikler + anlik fiyat + VIOP
 *   GET /api/history?symbol=ASELS&days=60
 *   GET /api/health
 *
 * Secret'lar (wrangler secret put ile):
 *   SUPABASE_URL
 *   SUPABASE_SERVICE_KEY
 * Degisken (wrangler.toml icinde):
 *   ALLOWED_ORIGIN  — panelin adresi, "*" birakma
 */

const CACHE_SECONDS = 60; // veri zaten ~15 dk gecikmeli, 60 sn fazlasiyla taze

function cors(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function json(body, env, status = 200, cacheSeconds = CACHE_SECONDS) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": `public, max-age=${cacheSeconds}`,
      ...cors(env),
    },
  });
}

/** PostgREST'e sorgu. Anahtar burada kalir, disari cikmaz. */
async function sb(env, path) {
  const res = await fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    headers: {
      apikey: env.SUPABASE_SERVICE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}`,
      Accept: "application/json",
    },
  });
  if (!res.ok) {
    // Supabase'in hata metnini disari sizdirmiyoruz, sadece kodu
    throw new Error(`supabase ${res.status}`);
  }
  return res.json();
}

/** Sembolu temizle — PostgREST sorgusuna serbest metin gitmesin. */
function cleanSymbol(raw) {
  const s = (raw || "ASELS").toUpperCase();
  return /^[A-Z]{3,6}$/.test(s) ? s : "ASELS";
}

async function snapshot(env, symbol) {
  const [metrics, quote, viop] = await Promise.all([
    sb(env, `latest_metrics?symbol=eq.${symbol}`),
    sb(env, `latest_quote?symbol=eq.${symbol}`),
    sb(env, `latest_viop?underlying=eq.${symbol}&order=volume_tl.desc&limit=6`),
  ]);
  return {
    symbol,
    metrics: metrics[0] || null,
    quote: quote[0] || null,
    viop: viop || [],
    served_at: new Date().toISOString(),
  };
}

async function history(env, symbol, days) {
  const n = Math.min(Math.max(parseInt(days, 10) || 60, 5), 500);
  const rows = await sb(
    env,
    `daily_metrics_ext?symbol=eq.${symbol}` +
      `&select=date,close,ret_pct,z_score,atr14,vol_percentile,volume` +
      `&order=date.desc&limit=${n}`
  );
  return { symbol, days: n, rows: rows.reverse() }; // eskiden yeniye
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }
    if (request.method !== "GET") {
      return json({ error: "method not allowed" }, env, 405, 0);
    }

    const symbol = cleanSymbol(url.searchParams.get("symbol"));

    try {
      switch (url.pathname) {
        case "/api/health":
          return json({ ok: true, time: new Date().toISOString() }, env, 200, 0);

        case "/api/snapshot":
          return json(await snapshot(env, symbol), env);

        case "/api/history":
          return json(
            await history(env, symbol, url.searchParams.get("days")),
            env,
            200,
            300 // gunluk veri gun icinde degismiyor, 5 dk cache
          );

        default:
          return json({ error: "not found" }, env, 404, 0);
      }
    } catch (err) {
      return json({ error: String(err.message || err) }, env, 502, 0);
    }
  },
};
