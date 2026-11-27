// MAHJONG LEAGUE の Worker。静的ファイル（dist/）に加えて、次の3つだけを受け持つ。
//  /api/stats.php   集計（公開時に書き出した JSON を返す。公開済みの季の分しか無い）
//  /data/kifu/<季>-<連番>.json   牌譜（R2 にある季ごとのまとめから1半荘ぶんを取り出す。未公開の季は返さない）
//  /api/submit.php など   キャラクリエイトは停止中

interface Env {
  ASSETS: { fetch(req: Request | string): Promise<Response> };
  KIFU: any; // R2Bucket
  DB: any; // D1Database
}

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

async function publishedSeason(env: Env, origin: string): Promise<number> {
  const r = await env.ASSETS.fetch(new Request(`${origin}/_meta.json`));
  if (!r.ok) return 0;
  return Number(((await r.json()) as any).published_season) || 0;
}

async function stats(url: URL, env: Env): Promise<Response> {
  const type = url.searchParams.get("type") || "players";
  if (!/^[a-z_]+$/.test(type)) return json({ ok: false, error: "unknown type" }, 400);
  const sp = url.searchParams.get("season");
  const season = sp && /^\d+$/.test(sp) ? sp : "all";
  const pub = await publishedSeason(env, url.origin);
  if (season !== "all" && Number(season) > pub) return json({ ok: false, error: "not published" }, 404);
  const r = await env.ASSETS.fetch(new Request(`${url.origin}/_api/stats/${type}-${season}.json`));
  if (!r.ok) return json({ ok: false, error: "unknown type" }, 400);
  const data: any = await r.json();
  if (type === "players" && Array.isArray(data.rows)) {
    const minHands = Math.max(0, Number(url.searchParams.get("min_hands") || 50));
    const league = url.searchParams.get("league");
    data.rows = data.rows.filter((p: any) => Number(p.hands) >= minHands && (!league || p.league === league));
  }
  return json(data);
}

async function kifu(url: URL, env: Env): Promise<Response> {
  const m = url.pathname.match(/^\/data\/kifu\/(\d+)-(\d+)\.json$/);
  if (!m) return new Response("not found", { status: 404 });
  const season = Number(m[1]);
  if (season > (await publishedSeason(env, url.origin))) return new Response("not found", { status: 404 });
  const idxObj = await env.KIFU.get(`kifu/${season}.idx.json`);
  if (!idxObj) return new Response("not found", { status: 404 });
  const idx = (await idxObj.json()) as Record<string, [number, number]>;
  const pos = idx[`${m[1]}-${m[2]}`];
  if (!pos) return new Response("not found", { status: 404 });
  const obj = await env.KIFU.get(`kifu/${season}.pack`, { range: { offset: pos[0], length: pos[1] } });
  if (!obj) return new Response("not found", { status: 404 });
  return new Response(obj.body, { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=3600" } });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/api/stats.php") return stats(url, env);
    if (url.pathname.startsWith("/data/kifu/")) return kifu(url, env);
    if (url.pathname.startsWith("/api/")) {
      return json({ ok: false, error: "この機能は現在停止中です（キャラクリエイトは再開準備中）" }, 503);
    }
    return env.ASSETS.fetch(req);
  },
};
