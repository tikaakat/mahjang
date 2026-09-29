// MAHJONG LEAGUE フロントエンド（ビルド不要の静的サイト）
// データは run_season.py が出力する data/ 以下のJSONを直接読む。
const BASE = window.MAHJONG_DATA_BASE || "data/";
const LEAGUES = ["A", "B", "C", "D"];
const TITLES = ["鳳凰位", "十段位", "王位", "マスターズ"];
const TITLE_MARK = { "鳳凰位": "鳳", "十段位": "十", "王位": "王", "マスターズ": "M" };
const TITLE_DESC = {
  "鳳凰位": "鳳凰戦Aリーグ上位3名と前年鳳凰位による決定戦（半荘16回戦）",
  "十段位": "レート上位32名によるシード付きトーナメント",
  "王位": "全雀士参加の抽選トーナメント（各卓1半荘・上位2名勝ち上がり）",
  "マスターズ": "全雀士参加の抽選トーナメント（各卓2半荘合計）",
};
const STYLE_LABELS = {
  speed_weight: "牌効率", dora_weight: "ドラ", yakuhai_weight: "役牌", flush_weight: "染め手",
  tanyao_weight: "タンヤオ", call_weight: "鳴き", riichi_weight: "リーチ", defense_weight: "守備", push_weight: "押し",
};
const LEAGUE_ZONES = { A: { down: 3 }, B: { up: 3, down: 3 }, C: { up: 3, down: 4 }, D: { up: 4 } };
const SERIES = ["#1f6b4f", "#b3372f", "#2c5aa0", "#a8801f"];

// ------------------------------------------------------------
// データ読み込み
// ------------------------------------------------------------
const cache = new Map();
async function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(BASE + path, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${path} を読み込めませんでした (${r.status})`);
      return r.json();
    }));
  }
  return cache.get(path);
}
const getIndex = () => getJSON("index.json");
async function getPlayers() {
  const list = await getJSON("players.json");
  if (!list._byId) list._byId = Object.fromEntries(list.map((p) => [p.id, p]));
  return list;
}

// ------------------------------------------------------------
// 表示ヘルパー
// ------------------------------------------------------------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pt = (v) => `<span class="num ${v > 0 ? "plus" : v < 0 ? "minus" : ""}">${v > 0 ? "+" : ""}${Number(v).toFixed(1)}</span>`;
const playerLink = (id, name) => `<a href="#/player/${encodeURIComponent(id)}">${esc(name || id)}</a>`;
const qs = () => new URLSearchParams(location.hash.split("?")[1] || "");

const HONORS = ["東", "南", "西", "北", "白", "發", "中"];
const SUIT_CLASS = ["m", "p", "s"];
const SUIT_CHAR = ["萬", "筒", "索"];
const KANJI_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];
function tileName(t) {
  return t >= 27 ? HONORS[t - 27] : `${(t % 9) + 1}${SUIT_CLASS[Math.floor(t / 9)]}`;
}
function tile(t, extra = "", small = false) {
  const sz = small ? " sm" : "";
  if (t >= 27) {
    const cls = { 31: "haku", 32: "hatsu", 33: "chun" }[t] || "";
    return `<span class="tile z ${cls}${sz} ${extra}" title="${HONORS[t - 27]}">${HONORS[t - 27]}</span>`;
  }
  const suit = Math.floor(t / 9), n = t % 9;
  const face = suit === 0 ? KANJI_NUM[n] : String(n + 1);
  return `<span class="tile ${SUIT_CLASS[suit]}${sz} ${extra}" title="${tileName(t)}"><span class="n">${face}</span><small>${SUIT_CHAR[suit]}</small></span>`;
}
const tilesHTML = (arr, small = false) => `<span class="tiles">${arr.map((t) => tile(t, "", small)).join("")}</span>`;
function meldHTML(m, small = true) {
  const tiles = m.tiles.map((t, i) => {
    const side = m.kind !== "ankan" && i === 0 ? "side" : "";
    const hidden = m.kind === "ankan" && (i === 0 || i === 3);
    return hidden ? `<span class="tile${small ? " sm" : ""}" style="background:var(--tile-edge)"></span>` : tile(t, side, small);
  });
  return `<span class="meld">${tiles.join("")}</span>`;
}

function setActiveNav(key) {
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === key));
}
function seasonSelect(current, selected, onchangeHash) {
  const opts = [];
  for (let s = current; s >= 1; s--) opts.push(`<option value="${s}" ${s === selected ? "selected" : ""}>第${s}期</option>`);
  return `<select aria-label="期を選択" onchange="location.hash='${onchangeHash}'.replace('{s}', this.value)">${opts.join("")}</select>`;
}

// ------------------------------------------------------------
// ページ: トップ
// ------------------------------------------------------------
async function pageHome() {
  setActiveNav("home");
  const idx = await getIndex();
  if (!idx.current_season) return `<h1>MAHJONG LEAGUE</h1><p class="muted">まだシーズンが行われていません。</p>`;
  const s = idx.current_season;
  const [standings, players] = await Promise.all([getJSON(`standings/season_${s}.json`), getPlayers()]);
  const holders = TITLES.map((t) => {
    const h = idx.titleholders[t];
    const reign = h ? s - h.since + 1 : 0;
    return `<a class="card title-card" data-mark="${TITLE_MARK[t]}" href="#/title/${encodeURIComponent(t)}" style="color:inherit">
      <div class="t-name">${t}</div>
      <div class="holder">${h ? esc(h.name) : "空位"}</div>
      <div class="since">${h ? `第${h.since}期〜（${reign}期連続）` : ""}</div>
    </a>`;
  }).join("");
  const leaders = LEAGUES.map((lg) => {
    const rows = standings.filter((r) => r.league === lg && r.rank).slice(0, 3);
    return `<div class="card"><h3><a href="#/league?season=${s}&lg=${lg}">${lg}リーグ</a></h3>
      ${rows.map((r) => `<div class="row"><b>${r.rank}</b> ${playerLink(r.id, r.name)}<span class="spacer"></span>${pt(r.points)}</div>`).join("")}</div>`;
  }).join("");
  const recent = idx.title_history.filter((h) => h.season === s).map((h) => `
    <tr><td><a href="#/title/${encodeURIComponent(h.title)}?season=${h.season}">${h.title}</a></td>
    <td>${playerLink(h.winner_id, h.winner_name)}</td>
    <td><span class="pill ${h.event === "奪取" ? "gold" : ""}">${h.event}</span></td>
    <td class="hide-sm">${h.previous_name ? esc(h.previous_name) : "—"}</td></tr>`).join("");
  const topElo = [...players].filter((p) => !p.retired).sort((a, b) => b.elo - a.elo).slice(0, 10);
  return `
    <div class="section-title"><h1>第${s}期</h1><span class="kicker">MAHJONG LEAGUE</span></div>
    <div class="grid grid-4">${holders}</div>
    <h2>鳳凰戦 第${s}期 上位</h2>
    <div class="grid grid-4">${leaders}</div>
    <div class="grid grid-2">
      <div><h2>第${s}期 タイトル戦</h2>
        <div class="table-wrap"><table><thead><tr><th>タイトル</th><th>獲得者</th><th></th><th class="hide-sm">前保持者</th></tr></thead><tbody>${recent}</tbody></table></div>
      </div>
      <div><h2>レーティング上位</h2>
        <div class="table-wrap"><table><thead><tr><th></th><th>雀士</th><th>所属</th><th class="num">レート</th></tr></thead><tbody>
        ${topElo.map((p, i) => `<tr><td class="rank">${i + 1}</td><td>${playerLink(p.id, p.display_name)}</td><td>${p.league}</td><td class="num">${p.elo.toFixed(0)}</td></tr>`).join("")}
        </tbody></table></div>
      </div>
    </div>`;
}

// ------------------------------------------------------------
// ページ: 鳳凰戦
// ------------------------------------------------------------
async function pageLeague() {
  setActiveNav("league");
  const idx = await getIndex();
  if (!idx.current_season) return `<p class="muted">データがありません。</p>`;
  const q = qs();
  const s = Number(q.get("season")) || idx.current_season;
  const lg = LEAGUES.includes(q.get("lg")) ? q.get("lg") : "A";
  const standings = await getJSON(`standings/season_${s}.json`);
  const rows = standings.filter((r) => r.league === lg);
  const zones = LEAGUE_ZONES[lg];
  const ranked = rows.filter((r) => r.rank);
  const n = ranked.length;
  const moveTag = (r) => ({
    promoted: `<span class="pill up">昇級</span>`, relegated: `<span class="pill down">降級</span>`,
    retired: `<span class="pill retired">引退</span>`,
  }[r.movement] || "") + (r.new ? ` <span class="pill new">新人</span>` : "") + (r.exempt ? ` <span class="pill gold">鳳凰位（免除）</span>` : "");
  const body = rows.map((r) => {
    let zone = "";
    if (r.rank && lg === "A" && r.rank <= 3) zone = "zone-final";
    else if (r.rank && zones.up && r.rank <= zones.up) zone = "zone-up";
    else if (r.rank && zones.down && r.rank > n - zones.down) zone = "zone-down";
    const g = r.games || 0;
    const avg = g ? (r.placements.reduce((a, c, i) => a + c * (i + 1), 0) / g).toFixed(2) : "—";
    return `<tr class="${zone}"><td class="rank">${r.rank ?? "—"}</td><td>${playerLink(r.id, r.name)} ${moveTag(r)}</td>
      <td class="num">${pt(r.points)}</td><td class="num hide-sm">${g}</td>
      <td class="num hide-sm">${r.placements.join(" / ")}</td><td class="num">${avg}</td><td class="num hide-sm">${Math.round(r.elo)}</td></tr>`;
  }).join("");
  return `
    <div class="row"><h1>鳳凰戦</h1><span class="spacer"></span>${seasonSelect(idx.current_season, s, `#/league?season={s}&lg=${lg}`)}</div>
    <p class="muted">通年リーグ。各節4人卓で半荘4回戦、年間合計ポイントで順位を決めます。Aリーグ上位3名が鳳凰位決定戦へ。</p>
    <nav class="tabs">${LEAGUES.map((x) => `<a class="${x === lg ? "active" : ""}" href="#/league?season=${s}&lg=${x}">${x}リーグ</a>`).join("")}</nav>
    <div class="table-wrap"><table>
      <thead><tr><th>順位</th><th>雀士</th><th class="num">ポイント</th><th class="num hide-sm">半荘</th><th class="num hide-sm">1/2/3/4着</th><th class="num">平均着順</th><th class="num hide-sm">レート</th></tr></thead>
      <tbody>${body}</tbody></table></div>
    <p class="legend"><span><i style="background:var(--gold)"></i>決定戦進出</span><span><i style="background:var(--up)"></i>昇級圏</span><span><i style="background:var(--down)"></i>降級圏</span></p>`;
}

// ------------------------------------------------------------
// ページ: タイトル一覧・タイトル戦詳細
// ------------------------------------------------------------
async function pageTitles() {
  setActiveNav("titles");
  const idx = await getIndex();
  const blocks = TITLES.map((t) => {
    const hist = idx.title_history.filter((h) => h.title === t).sort((a, b) => b.season - a.season);
    const counts = {};
    hist.forEach((h) => { counts[h.winner_id] = (counts[h.winner_id] || 0) + 1; });
    return `<div class="card"><div class="row"><h2 style="margin:0">${t}</h2><span class="spacer"></span><a href="#/title/${encodeURIComponent(t)}">最新の${t}戦 →</a></div>
      <p class="muted">${TITLE_DESC[t]}</p>
      <div class="table-wrap"><table><thead><tr><th>期</th><th>獲得者</th><th></th><th class="num">通算</th></tr></thead><tbody>
      ${hist.map((h) => `<tr><td><a href="#/title/${encodeURIComponent(t)}?season=${h.season}">第${h.season}期</a></td><td>${playerLink(h.winner_id, h.winner_name)}</td>
        <td><span class="pill ${h.event === "奪取" ? "gold" : ""}">${h.event}</span></td><td class="num">${counts[h.winner_id]}期</td></tr>`).join("") || `<tr><td colspan="4" class="muted">まだ開催されていません</td></tr>`}
      </tbody></table></div></div>`;
  }).join("");
  return `<h1>タイトル戦</h1><div class="grid grid-2">${blocks}</div>`;
}

async function pageTitle(name) {
  setActiveNav("titles");
  const idx = await getIndex();
  const s = Number(qs().get("season")) || idx.current_season;
  const [titles, matches, players] = await Promise.all([
    getJSON(`titles/season_${s}.json`), getJSON(`matches/season_${s}.json`), getPlayers(),
  ]);
  const t = titles.find((x) => x.title === name);
  if (!t) return `<p class="muted">第${s}期の${esc(name)}戦は見つかりません。</p>`;
  const nm = (id) => players._byId[id]?.display_name || id;
  const finalStage = t.stages[t.stages.length - 1];
  const finalGames = matches.filter((m) => m.event.kind === "title" && m.event.title === name && m.event.stage === finalStage.name)
    .sort((a, b) => a.event.game - b.event.game);
  const ids = finalStage.tables[0].members;

  // 決勝の累積ポイント推移
  const cum = Object.fromEntries(ids.map((id) => [id, [0]]));
  finalGames.forEach((g) => ids.forEach((id) => {
    const i = g.seats.indexOf(id);
    const arr = cum[id];
    arr.push(Math.round((arr[arr.length - 1] + (i >= 0 ? g.points[i] : 0)) * 10) / 10);
  }));
  const chart = lineChart(ids.map((id, k) => ({ name: nm(id), values: cum[id], color: SERIES[k % 4] })), finalGames.length);

  const gameRows = finalGames.map((g) => `<tr><td><a href="#/game/${g.id}">第${g.event.game}戦</a>${g.has_kifu ? ` <a class="pill" href="#/kifu/${g.id}">牌譜</a>` : ""}</td>
    ${ids.map((id) => { const i = g.seats.indexOf(id); return `<td class="num">${i >= 0 ? pt(g.points[i]) : "—"}</td>`; }).join("")}</tr>`).join("");
  const stages = t.stages.slice(0, -1).map((st) => `
    <div class="stage"><h3>${esc(st.name)}<span class="muted">（各卓${st.games}半荘${st.byes?.length ? `・シード${st.byes.length}名` : ""}）</span></h3>
    <div class="stage-tables">${st.tables.map((tb, i) => `<div class="ttable"><div class="muted">${i + 1}卓</div>
      ${tb.members.map((id) => `<div class="m ${tb.advanced.includes(id) ? "adv" : ""}"><span>${playerLink(id, nm(id))}</span>${pt(tb.totals[id])}</div>`).join("")}</div>`).join("")}
    </div></div>`).join("");
  const seasons = idx.title_history.filter((h) => h.title === name).map((h) => h.season);
  return `
    <div class="row"><h1>第${s}期 ${esc(name)}戦</h1><span class="spacer"></span>
      <select aria-label="期を選択" onchange="location.hash='#/title/${encodeURIComponent(name)}?season='+this.value">
      ${seasons.sort((a, b) => b - a).map((x) => `<option value="${x}" ${x === s ? "selected" : ""}>第${x}期</option>`).join("")}</select></div>
    <p class="muted">${TITLE_DESC[name]}</p>
    <div class="card"><div class="row"><span class="pill gold">${t.event}</span>
      <b style="font-size:1.2rem">${playerLink(t.winner_id, t.winner_name)}</b>${t.previous_name ? `<span class="muted">（前${esc(name)}：${esc(t.previous_name)}）</span>` : ""}</div>
      <h3 style="margin-top:12px">${esc(finalStage.name)} 最終成績</h3>
      <div class="table-wrap"><table><thead><tr><th>順位</th><th>雀士</th><th class="num">合計</th></tr></thead><tbody>
      ${t.final_standings.map((r, i) => `<tr><td class="rank">${i + 1}</td><td>${playerLink(r.id, r.name)}</td><td class="num">${pt(r.points)}</td></tr>`).join("")}
      </tbody></table></div>
      <h3 style="margin-top:16px">ポイント推移</h3>${chart}
      <div class="legend">${ids.map((id, k) => `<span><i style="background:${SERIES[k % 4]}"></i>${esc(nm(id))}</span>`).join("")}</div>
      <div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>半荘</th>${ids.map((id) => `<th class="num">${esc(nm(id))}</th>`).join("")}</tr></thead><tbody>${gameRows}</tbody></table></div>
    </div>
    ${stages ? `<h2>予選・本戦</h2>${stages}` : ""}`;
}

function lineChart(series, n) {
  const W = 640, H = 240, L = 44, R = 12, T = 12, B = 26;
  const all = series.flatMap((s) => s.values);
  let lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  if (hi - lo < 10) { hi += 5; lo -= 5; }
  const x = (i) => L + (i / Math.max(1, n)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const step = niceStep((hi - lo) / 4);
  let grid = "";
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
  }
  let xt = "";
  for (let i = 1; i <= n; i++) if (n <= 8 || i % 2 === 0 || i === n) xt += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${i}</text>`;
  const lines = series.map((s) => `<polyline fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linejoin="round" points="${s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}"/>
    <circle cx="${x(s.values.length - 1)}" cy="${y(s.values[s.values.length - 1])}" r="3.5" fill="${s.color}"/>`).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="累積ポイント推移">${grid}
    <line class="axis" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>${xt}${lines}</svg>`;
}
function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  for (const m of [1, 2, 5, 10]) if (raw <= m * p) return m * p;
  return 10 * p;
}

// ------------------------------------------------------------
// ページ: 雀士名鑑・プロフィール
// ------------------------------------------------------------
async function pagePlayers() {
  setActiveNav("players");
  const players = await getPlayers();
  const q = qs();
  const filter = q.get("f") || "active";
  const sort = q.get("sort") || "elo";
  let list = players.filter((p) => (filter === "retired" ? p.retired : filter === "all" ? true : !p.retired));
  const key = {
    elo: (p) => -p.elo, peak: (p) => -p.peak_elo, games: (p) => -p.games, pts: (p) => -p.total_points,
    league: (p) => "ABCD".indexOf(p.league) * 10000 - p.elo, age: (p) => p.initial_age + p.total_seasons,
  }[sort] || ((p) => -p.elo);
  list = [...list].sort((a, b) => key(a) - key(b));
  const link = (f, s) => `#/players?f=${f}&sort=${s}`;
  const rows = list.map((p) => {
    const avg = p.games ? (p.placements.reduce((a, c, i) => a + c * (i + 1), 0) / p.games).toFixed(2) : "—";
    return `<tr><td>${playerLink(p.id, p.display_name)} ${p.retired ? `<span class="pill retired">引退</span>` : ""}</td>
      <td>${p.league}</td><td class="num">${p.initial_age + p.total_seasons}</td><td class="num">${p.elo.toFixed(0)}</td>
      <td class="num hide-sm">${p.peak_elo.toFixed(0)}</td><td class="num hide-sm">${p.games}</td><td class="num">${avg}</td><td class="num hide-sm">${pt(p.total_points)}</td></tr>`;
  }).join("");
  const th = (s, label, cls = "num") => `<th class="${cls}"><a href="${link(filter, s)}">${label}${sort === s ? " ▼" : ""}</a></th>`;
  return `<h1>雀士名鑑</h1>
    <div class="row" style="margin-bottom:10px">
      <input type="search" id="psearch" placeholder="名前で検索" oninput="document.querySelectorAll('#ptable tbody tr').forEach(r=>r.style.display=r.textContent.includes(this.value)?'':'none')">
      <nav class="tabs" style="border:none;margin:0">
        ${[["active", "現役"], ["retired", "引退"], ["all", "すべて"]].map(([f, l]) => `<a class="${f === filter ? "active" : ""}" href="${link(f, sort)}">${l}</a>`).join("")}
      </nav></div>
    <div class="table-wrap"><table id="ptable"><thead><tr><th>雀士</th>${th("league", "所属", "")}${th("age", "年齢")}${th("elo", "レート")}
      ${th("peak", "最高", "num hide-sm")}${th("games", "半荘", "num hide-sm")}<th class="num">平均着順</th>${th("pts", "通算pt", "num hide-sm")}</tr></thead>
      <tbody>${rows}</tbody></table></div>`;
}

function radar(params) {
  const keys = Object.keys(STYLE_LABELS);
  const W = 300, C = 150, Rr = 105;
  const pts = (scale) => keys.map((k, i) => {
    const a = -Math.PI / 2 + (i / keys.length) * Math.PI * 2;
    const v = scale === null ? Math.min(12, params[k] || 0) / 12 : scale;
    return [C + Math.cos(a) * Rr * v, C + Math.sin(a) * Rr * v];
  });
  const rings = [0.25, 0.5, 0.75, 1].map((s) => `<polygon points="${pts(s).map((p) => p.join(",")).join(" ")}" fill="none" class="grid-line"/>`).join("");
  const labels = keys.map((k, i) => {
    const a = -Math.PI / 2 + (i / keys.length) * Math.PI * 2;
    return `<text x="${C + Math.cos(a) * (Rr + 22)}" y="${C + Math.sin(a) * (Rr + 22) + 4}" text-anchor="middle">${STYLE_LABELS[k]}</text>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${W}" style="max-width:320px" role="img" aria-label="打ち筋">
    ${rings}<polygon points="${pts(null).map((p) => p.join(",")).join(" ")}" fill="var(--accent)" fill-opacity=".25" stroke="var(--accent)" stroke-width="2"/>${labels}</svg>`;
}

// 局単位の通算成績（和了率・放銃率など）
function statTiles(p) {
  const st = p.stats || {};
  const hands = st.hands || 0;
  const g = p.games || 0;
  const pct = (a, b) => (b ? `${((a / b) * 100).toFixed(1)}<small>%</small>` : "—");
  const num = (v) => (v ? Math.round(v).toLocaleString() : "—");
  const avgPlace = g ? (p.placements.reduce((a, c, i) => a + c * (i + 1), 0) / g).toFixed(2) : "—";
  const tiles = [
    ["和了率", pct(st.wins, hands), `${st.wins || 0}回 / ${hands}局`],
    ["放銃率", pct(st.dealins, hands), `${st.dealins || 0}回`],
    ["立直率", pct(st.riichi, hands), `${st.riichi || 0}回`],
    ["ツモ率", pct(st.tsumo, st.wins), "和了のうち"],
    ["平均打点", num(st.wins ? st.win_value / st.wins : 0), `最高 ${num(st.max_value)}`],
    ["平均放銃打点", num(st.dealins ? st.dealin_value / st.dealins : 0), ""],
    ["流局時聴牌率", pct(st.draw_tenpai, st.draws), `${st.draws || 0}回の流局`],
    ["平均着順", avgPlace, `${g}半荘`],
    ["トップ率", pct(p.placements?.[0] || 0, g), `ラス率 ${g ? ((p.placements[3] / g) * 100).toFixed(1) : "—"}%`],
    ["役満", st.yakuman ? `${st.yakuman}<small>回</small>` : "—", ""],
  ];
  return `<div class="stat-grid">${tiles.map(([label, value, sub]) => `
    <div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${value}</div>
    <div class="stat-sub">${sub}</div></div>`).join("")}</div>`;
}

// 半荘ごとのレート推移（期の切れ目に区切り線）
function rateChart(p) {
  const trace = p.elo_trace || [];
  if (trace.length < 2) return `<p class="muted">まだ推移を表示できるだけの対局がありません。</p>`;
  const W = 640, H = 260, L = 58, R = 12, T = 12, B = 30;
  const xs = trace.map((t) => t[1]), ys = trace.map((t) => t[2]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let lo = Math.min(...ys, 1500), hi = Math.max(...ys, 1500);
  const pad = Math.max(10, (hi - lo) * 0.1); lo -= pad; hi += pad;
  const x = (v) => L + ((v - x0) / Math.max(1, x1 - x0)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const step = niceStep((hi - lo) / 4);
  let grid = "";
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v)}</text>`;
  }
  let seasons = "";
  trace.forEach((t, i) => {
    if (i === 0 || trace[i - 1][0] !== t[0]) {
      seasons += `<line class="axis" stroke-dasharray="3 3" x1="${x(t[1])}" x2="${x(t[1])}" y1="${T}" y2="${H - B}"/>
        <text x="${x(t[1]) + 4}" y="${H - 8}">第${t[0]}期</text>`;
    }
  });
  const base = `<line class="axis" stroke-dasharray="2 4" x1="${L}" x2="${W - R}" y1="${y(1500)}" y2="${y(1500)}"/>`;
  const last = trace[trace.length - 1];
  return `<svg class="chart chart-lg" viewBox="0 0 ${W} ${H}" role="img" aria-label="レート推移">${grid}${base}${seasons}
    <polyline fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" points="${trace.map((t) => `${x(t[1])},${y(t[2])}`).join(" ")}"/>
    <circle cx="${x(last[1])}" cy="${y(last[2])}" r="3.5" fill="var(--accent)"/></svg>
    <p class="muted" style="font-size:.8rem;margin:4px 0 0">横軸は通算の半荘数（直近${trace.length}半荘）。点線は初期値1500。</p>`;
}

async function pagePlayer(id) {
  setActiveNav("players");
  const [players, idx] = await Promise.all([getPlayers(), getIndex()]);
  const p = players._byId[id];
  if (!p) return `<p class="muted">雀士が見つかりません。</p>`;
  const age = p.initial_age + p.total_seasons;
  const master = p.parent_a_id ? players._byId[p.parent_a_id] : null;
  const disciples = players.filter((x) => x.parent_a_id === p.id);
  const founder = players._byId[p.clan_root_id];
  const titles = idx.title_history.filter((h) => h.winner_id === p.id);
  const tcount = {};
  titles.forEach((h) => { tcount[h.title] = (tcount[h.title] || 0) + 1; });
  const current = Object.entries(idx.titleholders).filter(([, v]) => v && v.id === p.id).map(([k]) => k);
  const g = p.games || 0;
  const rate = (i) => (g ? ((p.placements[i] / g) * 100).toFixed(1) : "0.0");
  const avg = g ? (p.placements.reduce((a, c, i) => a + c * (i + 1), 0) / g).toFixed(2) : "—";
  const career = [...(p.career || [])].sort((a, b) => b.season - a.season).map((c) => `
    <tr><td><a href="#/league?season=${c.season}&lg=${c.league}">第${c.season}期</a></td><td>${c.league}リーグ</td>
    <td class="num">${c.rank ?? "免除"}</td><td class="num">${pt(c.points)}</td>
    <td class="num hide-sm">${c.elo != null ? Math.round(c.elo) : "—"}</td>
    <td>${titles.filter((h) => h.season === c.season).map((h) => `<span class="pill gold">${h.title}</span>`).join(" ")}</td></tr>`).join("");
  return `
    <div class="row"><h1>${esc(p.display_name)}</h1>${current.map((t) => `<span class="pill gold">${t}</span>`).join(" ")}
      ${p.retired ? `<span class="pill retired">引退（第${p.retired_season ?? "?"}期）</span>` : `<span class="pill">${p.league}リーグ</span>`}</div>
    <div class="grid grid-2">
      <div class="card"><dl class="kv">
        <dt>年齢</dt><dd>${age}歳</dd>
        <dt>レート</dt><dd>${p.elo.toFixed(0)}（最高 ${p.peak_elo.toFixed(0)}）</dd>
        <dt>通算</dt><dd>${g}半荘 ${pt(p.total_points)}pt・平均着順 ${avg}</dd>
        <dt>着順率</dt><dd><div class="bar" title="1着${rate(0)}% / 2着${rate(1)}% / 3着${rate(2)}% / 4着${rate(3)}%">
          <span style="width:${rate(0)}%;background:var(--gold)"></span><span style="width:${rate(1)}%;background:var(--accent)"></span>
          <span style="width:${rate(2)}%;background:var(--ink-2)"></span><span style="width:${rate(3)}%;background:var(--red)"></span></div>
          <span class="muted" style="font-size:.8rem">1着${rate(0)}%・2着${rate(1)}%・3着${rate(2)}%・4着${rate(3)}%</span></dd>
        <dt>師匠</dt><dd>${master ? playerLink(master.id, master.display_name) : "なし（開祖）"}</dd>
        <dt>一門</dt><dd>${founder ? `<a href="#/clan/${encodeURIComponent(p.clan_root_id)}">${esc(founder.display_name)}一門</a>` : "—"}（第${p.generation}世代）</dd>
        <dt>弟子</dt><dd>${disciples.length ? disciples.map((d) => playerLink(d.id, d.display_name)).join("、") : "なし"}</dd>
        <dt>タイトル</dt><dd>${Object.keys(tcount).length ? Object.entries(tcount).map(([t, n]) => `${t}${n}期`).join("・") : "なし"}</dd>
        ${p.created ? `<dt>出自</dt><dd><span class="pill new">投稿キャラ</span>${p.creator ? ` <span class="muted">by ${esc(p.creator)}</span>` : ""}</dd>` : ""}
        ${p.awakened_param ? `<dt>覚醒</dt><dd><span class="pill gold">${STYLE_LABELS[p.awakened_param] || "技量"}</span></dd>` : ""}
      </dl></div>
      <div class="card"><h3>打ち筋</h3>${radar(p.params)}</div>
    </div>
    <h2>成績</h2>
    ${statTiles(p)}
    <h2>レート推移</h2>
    <div class="card">${rateChart(p)}</div>
    <h2>経歴</h2>
    <div class="table-wrap"><table><thead><tr><th>期</th><th>所属</th><th class="num">順位</th><th class="num">ポイント</th><th class="num hide-sm">期末レート</th><th>タイトル</th></tr></thead>
    <tbody>${career || `<tr><td colspan="6" class="muted">まだ対局がありません</td></tr>`}</tbody></table></div>`;
}

// ------------------------------------------------------------
// ページ: 一門
// ------------------------------------------------------------
async function pageClans() {
  setActiveNav("clans");
  const [players, idx] = await Promise.all([getPlayers(), getIndex()]);
  const clans = {};
  players.forEach((p) => { (clans[p.clan_root_id] ||= []).push(p); });
  const titleCount = {};
  idx.title_history.forEach((h) => { const r = players._byId[h.winner_id]?.clan_root_id; if (r) titleCount[r] = (titleCount[r] || 0) + 1; });
  const list = Object.entries(clans).map(([root, members]) => ({
    root, members, active: members.filter((m) => !m.retired).length, titles: titleCount[root] || 0,
    best: Math.max(...members.map((m) => m.peak_elo)),
  })).filter((c) => c.members.length > 1 || c.titles).sort((a, b) => b.titles - a.titles || b.active - a.active);
  return `<h1>一門</h1><p class="muted">師弟関係でつながる系統。弟子は師匠の打ち筋を受け継ぎます（弟子が2人以上いる、またはタイトル経験のある系統を表示）。</p>
    <div class="table-wrap"><table><thead><tr><th>一門</th><th class="num">現役</th><th class="num">総数</th><th class="num">タイトル</th><th class="num hide-sm">最高レート</th></tr></thead><tbody>
    ${list.map((c) => `<tr><td><a href="#/clan/${encodeURIComponent(c.root)}">${esc(players._byId[c.root]?.display_name || c.root)}一門</a></td>
      <td class="num">${c.active}</td><td class="num">${c.members.length}</td><td class="num">${c.titles}</td><td class="num hide-sm">${c.best.toFixed(0)}</td></tr>`).join("")}
    </tbody></table></div>`;
}

async function pageClan(root) {
  setActiveNav("clans");
  const players = await getPlayers();
  const members = players.filter((p) => p.clan_root_id === root);
  const children = {};
  members.forEach((p) => { if (p.id !== root && p.parent_a_id) (children[p.parent_a_id] ||= []).push(p); });
  const node = (id, depth = 0) => {
    const p = players._byId[id];
    if (!p || depth > 30) return "";
    const kids = (children[id] || []).map((c) => node(c.id, depth + 1)).join("");
    return `<li>${playerLink(p.id, p.display_name)} <span class="muted">${p.retired ? "引退" : p.league + "リーグ"}・レート${p.elo.toFixed(0)}</span>${kids ? `<ul>${kids}</ul>` : ""}</li>`;
  };
  return `<h1>${esc(players._byId[root]?.display_name || root)}一門</h1><div class="card tree"><ul>${node(root)}</ul></div>`;
}

// ------------------------------------------------------------
// ページ: 対局結果・牌譜ビューア
// ------------------------------------------------------------
async function findGame(id) {
  const season = id.split("-")[0];
  const matches = await getJSON(`matches/season_${season}.json`);
  return matches.find((m) => m.id === id);
}

function eventLabel(ev) {
  if (ev.kind === "league") return `鳳凰戦 第${ev.season}期 ${ev.league}リーグ 第${ev.section}節 ${ev.table}卓 第${ev.game}戦`;
  return `第${ev.season}期 ${ev.title}戦 ${ev.stage}${ev.table ? ` ${ev.table}卓` : ""} 第${ev.game}戦`;
}

function roundLine(r, names) {
  if (r.type === "draw" || r.type === "nagashi") {
    const t = r.tenpai.map((x, i) => (x ? esc(names[i]) : null)).filter(Boolean);
    return `${r.type === "nagashi" ? "流し満貫" : "流局"}（聴牌: ${t.length ? t.join("・") : "なし"}）`;
  }
  const w = r.win;
  const how = r.type === "tsumo" ? "ツモ" : `ロン（放銃: ${esc(names[r.loser])}）`;
  return `<b>${esc(names[r.winner])}</b> ${how} ${tile(r.tile, "", true)} <span class="pill gold">${w.label}</span>
    <span class="muted">${w.yaku.map(([n, h]) => (h >= 13 ? n : `${n} ${h}翻`)).join("・")}</span>`;
}

async function pageGame(id) {
  const g = await findGame(id);
  if (!g) return `<p class="muted">対局が見つかりません。</p>`;
  const rows = g.rounds.map((r) => `<tr><td>${r.round}${r.honba ? ` ${r.honba}本場` : ""}</td><td>${roundLine(r, g.names)}</td>
    ${r.deltas.map((d) => `<td class="num hide-sm">${d ? pt(d / 1000) : ""}</td>`).join("")}</tr>`).join("");
  const order = [0, 1, 2, 3].sort((a, b) => g.placement[a] - g.placement[b]);
  return `<h1>対局結果</h1><p class="muted">${esc(eventLabel(g.event))}</p>
    ${g.has_kifu ? `<p><a class="pill gold" href="#/kifu/${g.id}">牌譜を再生する</a></p>` : ""}
    <div class="table-wrap"><table><thead><tr><th>着順</th><th>雀士</th><th class="num">持ち点</th><th class="num">ポイント</th></tr></thead><tbody>
    ${order.map((i) => `<tr><td class="rank">${g.placement[i]}</td><td>${playerLink(g.seats[i], g.names[i])}</td><td class="num">${g.final_scores[i].toLocaleString()}</td><td class="num">${pt(g.points[i])}</td></tr>`).join("")}
    </tbody></table></div>
    <h2>局の推移</h2>
    <div class="table-wrap"><table><thead><tr><th>局</th><th>結果</th>${g.names.map((n) => `<th class="num hide-sm">${esc(n)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

// 牌譜の状態を先頭から step 手目まで再現する
function replay(round, step) {
  const hands = round.haipai.map((h) => [...h]);
  const rivers = [[], [], [], []];
  const melds = [[], [], [], []];
  const riichi = [false, false, false, false];
  let pendingRiichi = -1, last = null, actor = round.oya, desc = "配牌";
  const remove = (arr, t, n = 1) => { for (let k = 0; k < n; k++) { const i = arr.indexOf(t); if (i >= 0) arr.splice(i, 1); } };
  for (let i = 0; i < step && i < round.seq.length; i++) {
    const ev = round.seq[i];
    const code = ev[0], a = Number(ev[1]);
    const parts = ev.slice(3).split(" ");
    const t = parseInt(parts[0], 10);
    actor = a;
    if (code === "t") { hands[a].push(t); last = { a, t, kind: "draw" }; desc = `${tileName(t)}をツモ`; }
    else if (code === "d") {
      remove(hands[a], t);
      rivers[a].push({ t, tg: ev.endsWith("*"), riichi: pendingRiichi === a, called: false });
      if (pendingRiichi === a) { riichi[a] = true; pendingRiichi = -1; }
      last = { a, t, kind: "discard" }; desc = `${tileName(t)}を切る${ev.endsWith("*") ? "（ツモ切り）" : ""}`;
    } else if (code === "r") { pendingRiichi = a; desc = "リーチ宣言"; }
    else if (code === "c" || code === "p" || code === "m") {
      const target = Number(parts[1]);
      const consumed = parts[2].split(",").map(Number);
      consumed.forEach((x) => remove(hands[a], x));
      const rv = rivers[target];
      if (rv.length) rv[rv.length - 1].called = true;
      const kind = { c: "chi", p: "pon", m: "minkan" }[code];
      melds[a].push({ kind, tiles: [t, ...consumed].sort((x, y) => x - y) });
      desc = `${{ c: "チー", p: "ポン", m: "大明槓" }[code]} ${tileName(t)}`;
    } else if (code === "a") { remove(hands[a], t, 4); melds[a].push({ kind: "ankan", tiles: [t, t, t, t] }); desc = `暗槓 ${tileName(t)}`; }
    else if (code === "k") {
      remove(hands[a], t);
      const m = melds[a].find((x) => x.kind === "pon" && x.tiles[0] === t);
      if (m) { m.kind = "kakan"; m.tiles = [t, t, t, t]; }
      desc = `加槓 ${tileName(t)}`;
    }
  }
  return { hands, rivers, melds, riichi, last, actor, desc };
}

async function pageKifu(id) {
  const k = await getJSON(`kifu/${id}.json`);
  const state = { r: 0, step: 0, timer: null };
  const winds = ["東", "南", "西", "北"];
  const render = () => {
    const round = k.rounds[state.r];
    const st = replay(round, state.step);
    const done = state.step >= round.seq.length;
    const seats = [0, 1, 2, 3].map((s) => {
      const wind = winds[(s - round.oya + 4) % 4];
      const hand = [...st.hands[s]];
      let drawn = null;
      if (st.last && st.last.kind === "draw" && st.last.a === s) { drawn = st.last.t; hand.splice(hand.indexOf(drawn), 1); }
      hand.sort((a, b) => a - b);
      const river = st.rivers[s].map((d, i) => tile(d.t, `${d.riichi ? "side" : ""} ${d.called ? "called" : ""} ${d.tg ? "tsumogiri" : ""} ${st.last && st.last.kind === "discard" && st.last.a === s && i === st.rivers[s].length - 1 ? "hi" : ""}`, true)).join("");
      return `<div class="seat ${st.actor === s && !done ? "turn" : ""}">
        <div class="seat-head"><span class="wind">${wind}</span><b>${esc(k.names[s])}</b>${st.riichi[s] ? `<span class="pill gold">リーチ</span>` : ""}<span class="score">${round.scores[s].toLocaleString()}</span></div>
        <div class="row"><span class="tiles">${hand.map((t) => tile(t)).join("")}${drawn !== null ? `<span style="width:8px"></span>${tile(drawn, "hi")}` : ""}</span>${st.melds[s].map((m) => meldHTML(m)).join("")}</div>
        <div class="river">${river}</div></div>`;
    }).join("");
    const res = done ? `<div class="result-box">${roundLine(round.result, k.names)}
        ${round.result.hand ? `<div style="margin-top:6px">${tilesHTML(round.result.hand.closed)}${round.result.hand.melds.map((m) => meldHTML(m)).join("")}</div>` : ""}
        <div class="muted">${round.result.deltas.map((d, i) => `${esc(k.names[i])} ${d > 0 ? "+" : ""}${d}`).join(" / ")}</div></div>` : "";
    document.getElementById("kifu").innerHTML = `
      <div class="row" style="margin-bottom:8px"><b>${round.round}${round.honba ? ` ${round.honba}本場` : ""}</b>
        <span class="muted">供託${round.kyotaku}</span><span class="muted">ドラ表示</span>${tile(round.dora, "", true)}
        <span class="spacer"></span><select id="kround">${k.rounds.map((r, i) => `<option value="${i}" ${i === state.r ? "selected" : ""}>${r.round}${r.honba ? ` ${r.honba}本場` : ""}</option>`).join("")}</select></div>
      <div class="board">${seats}</div>
      ${res}
      <div class="controls">
        <button data-k="first" aria-label="局の最初へ">⏮</button><button data-k="prev" aria-label="1手戻る">◀</button>
        <button data-k="play" class="primary">${state.timer ? "停止" : "再生"}</button>
        <button data-k="next" aria-label="1手進む">▶</button><button data-k="last" aria-label="局の最後へ">⏭</button>
        <span class="status">${state.step}/${round.seq.length}手 ${done ? "終局" : `${esc(k.names[st.actor])}: ${st.desc}`}</span>
        <button data-k="nextround">次の局 →</button>
      </div>`;
    document.getElementById("kround").onchange = (e) => { state.r = Number(e.target.value); state.step = 0; render(); };
    document.querySelectorAll("#kifu .controls button").forEach((b) => { b.onclick = () => act(b.dataset.k); });
  };
  const act = (kind) => {
    const round = k.rounds[state.r];
    if (kind === "first") state.step = 0;
    if (kind === "prev") state.step = Math.max(0, state.step - 1);
    if (kind === "next") state.step = Math.min(round.seq.length, state.step + 1);
    if (kind === "last") state.step = round.seq.length;
    if (kind === "nextround" && state.r < k.rounds.length - 1) { state.r += 1; state.step = 0; }
    if (kind === "play") {
      if (state.timer) { clearInterval(state.timer); state.timer = null; }
      else state.timer = setInterval(() => {
        const rd = k.rounds[state.r];
        if (state.step < rd.seq.length) state.step += 1;
        else if (state.r < k.rounds.length - 1) { state.r += 1; state.step = 0; }
        else { clearInterval(state.timer); state.timer = null; }
        if (!document.getElementById("kifu")) { clearInterval(state.timer); state.timer = null; return; }
        render();
      }, 450);
    }
    render();
  };
  setTimeout(render, 0);
  return `<div class="row"><h1>牌譜</h1><span class="spacer"></span><a href="#/game/${k.id}">対局結果へ</a></div>
    <p class="muted">${esc(eventLabel(k.event))}</p><div id="kifu"></div>`;
}


// ------------------------------------------------------------
// API（server/api）。未設置の環境ではエラーメッセージを出す
// ------------------------------------------------------------
const API = window.MAHJONG_API_BASE || "api/";
async function api(path, options) {
  const r = await fetch(API + path, { cache: "no-store", ...options });
  let body = null;
  try { body = await r.json(); } catch { /* HTMLのエラーページなど */ }
  if (!r.ok || !body || body.ok === false) throw new Error((body && body.error) || `API に接続できませんでした (${r.status})`);
  return body;
}
const apiUnavailable = (e) => `<div class="card"><b>集計サーバーに接続できません</b><p class="muted">${esc(e.message)}</p>
  <p class="muted">この機能はサーバー（PHP＋MySQL）を設置すると使えます。README の「サーバー設置」を参照してください。</p></div>`;

// ------------------------------------------------------------
// ページ: 記録（集計一覧）
// ------------------------------------------------------------
const STAT_TABS = [
  ["players", "個人成績"], ["yakuman", "役満"], ["big_hands", "高打点"], ["yaku", "役の出現率"],
  ["titles", "タイトル獲得"], ["scores", "半荘最高・最低"],
];
function gameRef(r) {
  const where = r.kind === "league" ? `${r.league}リーグ` : `${r.title}${r.stage ? " " + r.stage : ""}`;
  return `<a href="#/game/${r.game_id}">第${r.season}期 ${esc(where)}</a>`;
}
async function pageStats() {
  setActiveNav("stats");
  const idx = await getIndex();
  const q = qs();
  const tab = STAT_TABS.some(([k]) => k === q.get("tab")) ? q.get("tab") : "players";
  const season = q.get("season") || "";
  const sortKey = q.get("sort") || "win_rate";
  const seasonOpts = [`<option value="">通算</option>`];
  for (let x = idx.current_season; x >= 1; x--) seasonOpts.push(`<option value="${x}" ${String(x) === season ? "selected" : ""}>第${x}期</option>`);
  const head = `<h1>記録</h1>
    <nav class="tabs">${STAT_TABS.map(([k, l]) => `<a class="${k === tab ? "active" : ""}" href="#/stats?tab=${k}&season=${season}">${l}</a>`).join("")}</nav>
    ${tab !== "titles" ? `<div class="row" style="margin-bottom:10px"><select aria-label="期" onchange="location.hash='#/stats?tab=${tab}&season='+this.value">${seasonOpts.join("")}</select></div>` : ""}`;
  let body;
  try {
    const sq = season ? `&season=${season}` : "";
    if (tab === "players") {
      const minHands = season ? 30 : 100;
      const d = await api(`stats.php?type=players&min_hands=${minHands}${sq}`);
      const rows = d.rows.map((r) => {
        const games = +r.games;
        return { ...r, win_rate: r.wins / r.hands, dealin_rate: r.dealins / r.hands, riichi_rate: r.riichis / r.hands,
          tsumo_rate: r.wins ? r.tsumos / r.wins : 0, avg_place: games ? (+r.p1 + 2 * r.p2 + 3 * r.p3 + 4 * r.p4) / games : 0,
          top_rate: games ? r.p1 / games : 0, avg_value: +r.avg_value || 0, points: +r.points };
      });
      const cols = [["win_rate", "和了率", "%"], ["dealin_rate", "放銃率", "%", true], ["riichi_rate", "立直率", "%"],
        ["tsumo_rate", "ツモ率", "%"], ["avg_value", "平均打点", "n"], ["top_rate", "トップ率", "%"], ["avg_place", "平均着順", "f", true],
        ["points", "ポイント", "p"], ["games", "半荘", "n"]];
      const col = cols.find((c) => c[0] === sortKey) || cols[0];
      rows.sort((a, b) => (col[3] ? a[col[0]] - b[col[0]] : b[col[0]] - a[col[0]]));
      const fmt = (v, t) => t === "%" ? (v * 100).toFixed(1) : t === "f" ? v.toFixed(2) : t === "p" ? pt(v) : Math.round(v).toLocaleString();
      body = `<p class="muted">${season ? "30" : "100"}局以上打った雀士が対象。列名をクリックで並べ替え（放銃率・平均着順は小さい順）。</p>
        <div class="table-wrap"><table><thead><tr><th></th><th>雀士</th>${cols.map(([k, l]) =>
          `<th class="num"><a href="#/stats?tab=players&season=${season}&sort=${k}">${l}${k === col[0] ? " ▼" : ""}</a></th>`).join("")}</tr></thead><tbody>
        ${rows.map((r, i) => `<tr><td class="rank">${i + 1}</td><td>${playerLink(r.id, r.name)} <span class="muted">${r.league || "引退"}</span></td>
          ${cols.map(([k, , t]) => `<td class="num">${fmt(r[k], t)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    } else if (tab === "yakuman" || tab === "big_hands") {
      const d = await api(`stats.php?type=${tab}${sq}`);
      body = d.rows.length ? `<div class="table-wrap"><table><thead><tr><th>対局</th><th>局</th><th>和了者</th><th>役</th><th class="num">打点</th><th class="hide-sm">放銃</th></tr></thead><tbody>
        ${d.rows.map((r) => `<tr><td>${gameRef(r)}</td><td>${esc(r.round_name)}</td><td>${playerLink(r.winner_id, r.winner_name)}</td>
          <td>${tab === "big_hands" ? `<span class="pill gold">${esc(r.label)}</span> ` : ""}<span class="muted">${esc(r.yaku)}</span></td>
          <td class="num">${(+r.value).toLocaleString()}</td><td class="hide-sm">${r.type === "tsumo" ? "ツモ" : esc(r.loser_name || "")}</td></tr>`).join("")}
        </tbody></table></div>` : `<p class="muted">まだ記録がありません。</p>`;
    } else if (tab === "yaku") {
      const d = await api(`stats.php?type=yaku${sq}`);
      const max = Math.max(1, ...d.rows.map((r) => +r.n));
      body = `<p class="muted">和了 ${d.wins.toLocaleString()} 回のうち、各役が付いた割合（ドラを除く）。</p>
        <div class="table-wrap"><table><thead><tr><th>役</th><th class="num">回数</th><th class="num">出現率</th><th class="hide-sm" style="width:40%"></th></tr></thead><tbody>
        ${d.rows.map((r) => `<tr><td>${esc(r.name)}</td><td class="num">${(+r.n).toLocaleString()}</td><td class="num">${((r.n / Math.max(1, d.wins)) * 100).toFixed(2)}%</td>
          <td class="hide-sm"><div class="bar"><span style="width:${(r.n / max) * 100}%;background:var(--accent)"></span></div></td></tr>`).join("")}</tbody></table></div>`;
    } else if (tab === "titles") {
      const d = await api("stats.php?type=titles");
      const by = {};
      d.rows.forEach((r) => { (by[r.id] ||= { id: r.id, name: r.name, retired: +r.retired, total: 0, t: {} }); by[r.id].t[r.title] = +r.n; by[r.id].total += +r.n; });
      const list = Object.values(by).sort((a, b) => b.total - a.total);
      body = `<div class="table-wrap"><table><thead><tr><th></th><th>雀士</th>${TITLES.map((t) => `<th class="num">${t}</th>`).join("")}<th class="num">合計</th></tr></thead><tbody>
        ${list.map((p, i) => `<tr><td class="rank">${i + 1}</td><td>${playerLink(p.id, p.name)} ${p.retired ? `<span class="pill retired">引退</span>` : ""}</td>
          ${TITLES.map((t) => `<td class="num">${p.t[t] || ""}</td>`).join("")}<td class="num"><b>${p.total}</b></td></tr>`).join("")}</tbody></table></div>`;
    } else {
      const d = await api(`stats.php?type=scores${sq}`);
      const tbl = (rows) => `<div class="table-wrap"><table><thead><tr><th>雀士</th><th class="num">持ち点</th><th>対局</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td>${playerLink(r.player_id, r.name)}</td><td class="num">${(+r.final_score).toLocaleString()}</td><td>${gameRef(r)}</td></tr>`).join("")}</tbody></table></div>`;
      body = `<div class="grid grid-2"><div><h2>最高得点</h2>${tbl(d.high)}</div><div><h2>最低得点</h2>${tbl(d.low)}</div></div>`;
    }
  } catch (e) {
    body = apiUnavailable(e);
  }
  return head + body;
}

// ------------------------------------------------------------
// ページ: キャラクリエイト
// ------------------------------------------------------------
const PARAM_MIN = 0.5, PARAM_MAX = 10, PARAM_BUDGET = 45;
const PRESETS = {  // mahjong_league/creation.py と同じ値
  balanced: ["バランス", { speed_weight: 6, dora_weight: 4, yakuhai_weight: 4, flush_weight: 3, tanyao_weight: 4, call_weight: 5, riichi_weight: 6, defense_weight: 7, push_weight: 6 }],
  attack: ["攻撃型", { speed_weight: 8, dora_weight: 6, yakuhai_weight: 4, flush_weight: 3, tanyao_weight: 4, call_weight: 4, riichi_weight: 9, defense_weight: 2, push_weight: 5 }],
  defense: ["守備型", { speed_weight: 6, dora_weight: 3, yakuhai_weight: 3, flush_weight: 2, tanyao_weight: 3, call_weight: 3, riichi_weight: 5, defense_weight: 10, push_weight: 10 }],
  caller: ["鳴き屋", { speed_weight: 7, dora_weight: 4, yakuhai_weight: 8, flush_weight: 5, tanyao_weight: 7, call_weight: 9, riichi_weight: 1, defense_weight: 2, push_weight: 2 }],
  flush: ["染め手", { speed_weight: 4, dora_weight: 4, yakuhai_weight: 6, flush_weight: 10, tanyao_weight: 1, call_weight: 8, riichi_weight: 3, defense_weight: 5, push_weight: 4 }],
};
const STATUS_LABEL = { pending: "受付済み", exported: "新人リーグ出場中", entered: "入門", not_selected: "落選" };

async function pageCreate() {
  setActiveNav("create");
  const idx = await getIndex();
  let newcomer = null;
  for (const s of [idx.current_season + 1, idx.current_season]) {
    try { newcomer = await getJSON(`newcomer_league/for_season_${s}.json`); break; } catch { /* まだ無い */ }
  }
  const sliders = Object.entries(STYLE_LABELS).map(([k, l]) => `
    <label class="slider"><span>${l}</span><input type="range" min="${PARAM_MIN}" max="${PARAM_MAX}" step="0.5" name="${k}" value="${PRESETS.balanced[1][k]}"><output>${PRESETS.balanced[1][k]}</output></label>`).join("");
  const nlTable = newcomer && newcomer.standings.length ? `
    <h2>新人リーグ（第${newcomer.season}期入門枠 ${newcomer.slots}名）</h2>
    <div class="table-wrap"><table><thead><tr><th>順位</th><th>雀士</th><th class="num">ポイント</th><th class="num hide-sm">1/2/3/4着</th><th></th></tr></thead><tbody>
    ${newcomer.standings.map((r) => `<tr class="${r.winner ? "zone-up" : ""}"><td class="rank">${r.rank}</td><td>${esc(r.name)} ${r.auto ? `<span class="muted">（自動）</span>` : r.creator ? `<span class="muted">by ${esc(r.creator)}</span>` : ""}</td>
      <td class="num">${pt(r.points)}</td><td class="num hide-sm">${r.placements.join(" / ")}</td><td>${r.winner ? `<span class="pill up">入門</span>` : ""}</td></tr>`).join("")}
    </tbody></table></div>` : "";
  setTimeout(bindCreateForm, 0);
  return `<h1>キャラクリエイト</h1>
    <p class="muted">自分だけの雀士を投稿できます。投稿は次の新人リーグ（4人打ち・1人12半荘）に出場し、上位に入るとDリーグに入門します。入門時には既存の雀士が師匠に付きます。技量は入門時に決まり、若いうちに伸びます。</p>
    <div class="grid grid-2">
      <form id="create-form" class="card" autocomplete="off">
        <div class="row"><label style="flex:1">雀士名（12文字まで）<br><input name="name" maxlength="12" required style="width:100%"></label></div>
        <div class="row" style="margin-top:8px"><label style="flex:1">投稿者名（任意）<br><input name="creator" maxlength="12" style="width:100%"></label></div>
        <input name="website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">
        <h3 style="margin-top:14px">打ち筋</h3>
        <div class="row" style="margin-bottom:8px">${Object.entries(PRESETS).map(([k, [l]]) => `<button type="button" data-preset="${k}">${l}</button>`).join("")}</div>
        <div class="sliders">${sliders}</div>
        <p id="budget" class="muted"></p>
        <button type="submit" class="primary">投稿する</button>
        <p id="create-msg" role="status"></p>
      </form>
      <div class="card"><h3>打ち筋のプレビュー</h3><div id="create-radar"></div>
        <p class="muted" style="font-size:.85rem">合計は${PARAM_BUDGET}まで。超えた場合は比率を保ったまま自動で縮めます。</p></div>
    </div>
    <h2>最近の投稿</h2><div id="submissions"><p class="loading">読み込み中…</p></div>
    ${nlTable}`;
}

function bindCreateForm() {
  const form = document.getElementById("create-form");
  if (!form) return;
  const inputs = [...form.querySelectorAll('input[type="range"]')];
  const read = () => Object.fromEntries(inputs.map((i) => [i.name, Number(i.value)]));
  const update = () => {
    const vals = read();
    const total = Object.values(vals).reduce((a, b) => a + b, 0);
    inputs.forEach((i) => { i.nextElementSibling.textContent = i.value; });
    const over = total > PARAM_BUDGET;
    document.getElementById("budget").innerHTML = `合計 <b class="${over ? "minus" : ""}">${total.toFixed(1)}</b> / ${PARAM_BUDGET}${over ? "（投稿時に比率を保って縮めます）" : ""}`;
    document.getElementById("create-radar").innerHTML = radar(vals);
  };
  inputs.forEach((i) => i.addEventListener("input", update));
  let preset = "balanced";
  form.querySelectorAll("[data-preset]").forEach((b) => b.addEventListener("click", () => {
    preset = b.dataset.preset;
    inputs.forEach((i) => { i.value = PRESETS[preset][1][i.name]; });
    update();
  }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("create-msg");
    const fd = new FormData(form);
    msg.textContent = "送信中…";
    try {
      const res = await api("submit.php", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: fd.get("name"), creator: fd.get("creator"), website: fd.get("website"), type: preset, params: read() }) });
      msg.innerHTML = `<span class="plus">投稿を受け付けました（受付番号 ${res.id}）。次の新人リーグに出場します。</span>`;
      form.reset(); update(); loadSubmissions();
    } catch (err) {
      msg.innerHTML = `<span class="minus">${esc(err.message)}</span>`;
    }
  });
  update();
  loadSubmissions();
}

async function loadSubmissions() {
  const box = document.getElementById("submissions");
  if (!box) return;
  try {
    const d = await api("submissions.php");
    box.innerHTML = d.submissions.length ? `<div class="table-wrap"><table><thead><tr><th>受付</th><th>雀士</th><th class="hide-sm">投稿者</th><th>状況</th></tr></thead><tbody>
      ${d.submissions.map((s) => `<tr><td class="muted">${esc(s.created_at)}</td>
        <td>${s.player_id ? playerLink(s.player_id, s.name) : esc(s.name)}</td><td class="hide-sm">${esc(s.creator || "")}</td>
        <td><span class="pill ${s.status === "entered" ? "up" : s.status === "not_selected" ? "retired" : ""}">${STATUS_LABEL[s.status] || s.status}</span>
        ${s.result_rank ? `<span class="muted">新人リーグ${s.result_rank}位</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="muted">まだ投稿はありません。</p>`;
  } catch (e) {
    box.innerHTML = apiUnavailable(e);
  }
}

// ------------------------------------------------------------
// ページ: ルール
// ------------------------------------------------------------
async function pageRules() {
  setActiveNav("rules");
  const idx = await getIndex();
  const r = idx.rules || {};
  const yn = (b) => (b ? "あり" : "なし");
  return `<h1>ルール</h1><div class="card"><dl class="kv">
    <dt>準拠</dt><dd>${esc(r.name || "日本プロ麻雀連盟 公式ルール")}</dd>
    <dt>対局</dt><dd>${r.game_length === "east" ? "東風戦" : "半荘戦"}・${(r.start_score || 30000).toLocaleString()}点持ち${(r.return_score || 30000).toLocaleString()}点返し</dd>
    <dt>順位点</dt><dd>${(r.uma || [15, 5, -5, -15]).map((u) => (u > 0 ? "+" : "") + u).join(" / ")}（千点）</dd>
    <dt>一発・裏ドラ・槓ドラ</dt><dd>${yn(r.ippatsu)}・${yn(r.ura_dora)}・${yn(r.kan_dora)}（赤ドラなし）</dd>
    <dt>数え役満</dt><dd>${r.kazoe_yakuman ? "あり" : "なし（11翻以上は三倍満）"}・役満の複合${yn(r.double_yakuman)}</dd>
    <dt>流し満貫</dt><dd>${yn(r.nagashi_mangan)}</dd>
    <dt>途中流局</dt><dd>なし</dd>
    <dt>飛び</dt><dd>${r.tobi ? "あり" : "なし（マイナスでも続行）"}</dd>
    <dt>アガリ止め</dt><dd>${yn(r.agari_yame)}</dd>
    <dt>ダブロン</dt><dd>なし（頭ハネ）</dd>
    <dt>喰いタン・後付け</dt><dd>あり・あり</dd>
    <dt>責任払い</dt><dd>${r.pao ? "大三元・大四喜・四槓子" : "なし"}</dd>
    <dt>同点</dt><dd>${r.tie_split_uma ? "順位点を等分" : "起家に近い順"}</dd>
  </dl></div>
  <h2>リーグとタイトル</h2>
  <div class="card"><dl class="kv">
    <dt>鳳凰戦</dt><dd>A〜Dの通年リーグ。昇降級あり（A⇔B 3名、B⇔C 3名、C⇔D 4名）。Dリーグで2年連続マイナスは引退。</dd>
    ${TITLES.map((t) => `<dt>${t}</dt><dd>${TITLE_DESC[t]}</dd>`).join("")}
    <dt>師弟制度</dt><dd>新人は既存の雀士に弟子入りし、師匠の打ち筋を受け継いで入門します（稀に新たな一門の開祖に）。</dd>
  </dl></div>`;
}

// ------------------------------------------------------------
// ルーター
// ------------------------------------------------------------
const routes = [
  [/^#?\/?$/, pageHome],
  [/^#\/league/, pageLeague],
  [/^#\/titles/, pageTitles],
  [/^#\/title\/([^?]+)/, (m) => pageTitle(decodeURIComponent(m[1]))],
  [/^#\/players/, pagePlayers],
  [/^#\/player\/([^?]+)/, (m) => pagePlayer(decodeURIComponent(m[1]))],
  [/^#\/clans/, pageClans],
  [/^#\/clan\/([^?]+)/, (m) => pageClan(decodeURIComponent(m[1]))],
  [/^#\/game\/([^?]+)/, (m) => pageGame(m[1])],
  [/^#\/kifu\/([^?]+)/, (m) => pageKifu(m[1])],
  [/^#\/rules/, pageRules],
  [/^#\/stats/, pageStats],
  [/^#\/create/, pageCreate],
];

async function router() {
  const app = document.getElementById("app");
  const hash = location.hash || "#/";
  for (const [re, fn] of routes) {
    const m = hash.match(re);
    if (m) {
      app.innerHTML = `<p class="loading">読み込み中…</p>`;
      try {
        app.innerHTML = await fn(m);
      } catch (e) {
        app.innerHTML = `<div class="card"><b>表示できませんでした</b><p class="muted">${esc(e.message)}</p></div>`;
      }
      window.scrollTo(0, 0);
      return;
    }
  }
  app.innerHTML = `<p class="muted">ページが見つかりません。</p>`;
}
window.addEventListener("hashchange", router);
router();
