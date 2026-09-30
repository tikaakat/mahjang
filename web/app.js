// MAHJONG LEAGUE フロントエンド（ビルド不要の静的サイト）
// 画面構成・見た目はオセロ版（CIRCUIT OTHELLO LEAGUE）に合わせている。
// データは run_season.py が出力する data/ 以下のJSONを直接読む（記録・投稿だけ server/api を使う）。
const BASE = window.MAHJONG_DATA_BASE || "data/";
const API = window.MAHJONG_API_BASE || "api/";
const LEAGUES = ["A", "B", "C", "D"];
const LEAGUE_CAPACITY = { A: 12, B: 16, C: 20, D: 28 }; // mahjong_league/league.py と一致させること
const LEAGUE_ZONES = { A: { down: 2 }, B: { up: 2, down: 3 }, C: { up: 3, down: 4 }, D: { up: 4 } };
const TITLES = ["鳳凰位", "麒麟位", "霊亀位", "応龍位"];
const TITLE_SHORT = { "鳳凰位": "鳳凰", "麒麟位": "麒麟", "霊亀位": "霊亀", "応龍位": "応龍" };
const TITLE_EVENT_NAME = { "鳳凰位": "鳳凰位決定戦", "麒麟位": "麒麟戦", "霊亀位": "霊亀戦", "応龍位": "応龍戦" };
// 旧名称（第1季の途中まで）で残っているデータの表示用
const OLD_TITLE_NAME = { "十段位": "麒麟位", "王位": "霊亀位", "マスターズ": "応龍位" };
const titleName = (t) => OLD_TITLE_NAME[t] || t;
// タイトル → ルール（mahjong_sim/rules.py の TITLE_RULE と一致させること）
const TITLE_RULE = { "鳳凰位": "houou", "麒麟位": "kirin", "霊亀位": "reiki", "応龍位": "ouryu" };
const TITLE_DESC = {
  "鳳凰位": "鳳凰戦Aリーグ上位3名と前年鳳凰位による決定戦（半荘16回戦）",
  "麒麟位": "レート上位32名によるシード付きトーナメント",
  "霊亀位": "全雀士参加の抽選トーナメント（各卓1半荘・上位2名勝ち上がり）",
  "応龍位": "全雀士参加の抽選トーナメント（各卓2半荘合計）",
};
const RESULT_TITLE_TABS = { hououi: "鳳凰位", kirin: "麒麟位", reiki: "霊亀位", ouryu: "応龍位" };
// ルールの要約（index.json の rules[キー] から）
function ruleSummary(r) {
  if (!r) return "";
  const yn = (b) => (b ? "あり" : "なし");
  const oka = (r.return_score - r.start_score) * 4 / 1000;
  const uma = r.uma_mode === "sinking" ? "沈みウマ（原点以上の人数で変動：1人浮き +12/−1/−3/−8、2人浮き +8/+4/−4/−8、3人浮き +8/+3/+1/−12）"
    : r.uma_mode === "win_loss" ? "なし（1着 +1・4着 −1 のみ。素点は数えない）"
    : r.uma.map((u) => (u > 0 ? "+" : "") + u).join(" / ");
  return `<dl class="params-grid">
    <dt>持ち点・返し</dt><dd>${r.start_score.toLocaleString()}点持ち ${r.return_score.toLocaleString()}点返し</dd>
    <dt>オカ</dt><dd>${oka ? `あり（トップに +${oka}）` : "なし"}</dd>
    <dt>ウマ（順位点）</dt><dd>${uma}</dd>
    <dt>一発・裏ドラ</dt><dd>${yn(r.ippatsu)}・${yn(r.ura_dora)}</dd>
    <dt>槓ドラ・赤ドラ</dt><dd>${yn(r.kan_dora)}・${r.aka ? "あり（赤五萬・赤五筒・赤五索 各1枚）" : "なし"}</dd>
    <dt>数え役満</dt><dd>${r.kazoe_yakuman ? "あり" : "なし（11翻以上は三倍満）"}</dd>
    <dt>ノーテン罰符</dt><dd>${r.noten_penalty ? `あり（場に${r.noten_penalty}点）` : "なし"}</dd>
    <dt>連荘</dt><dd>${r.draw_renchan === false ? "和了のみ（流局は親流れ）" : "和了・流局時の親の聴牌"}</dd>
    <dt>流し満貫</dt><dd>${yn(r.nagashi_mangan)}</dd>
  </dl>`;
}
const isWinLoss = (idx, title) => idx.rules?.[TITLE_RULE[title]]?.uma_mode === "win_loss";
// 応龍戦（1着+1・4着-1）は整数の勝ち点で表示する
const ptOf = (v, winLoss) => (winLoss ? `<span class="${v > 0 ? "plus" : v < 0 ? "minus" : ""}">${v > 0 ? "+" : ""}${Math.round(v * 10) / 10}</span>` : pt(v));
const STYLE_LABELS = {
  speed_weight: "牌効率", dora_weight: "ドラ", yakuhai_weight: "役牌", flush_weight: "染め手",
  tanyao_weight: "タンヤオ", call_weight: "鳴き", riichi_weight: "リーチ", defense_weight: "守備", push_weight: "押し返し",
};
// 打ち筋9項目の意味（mahjong_sim/ai.py の打牌・鳴き・リーチ判断での使われ方）
const STYLE_DESC = {
  speed_weight: "受け入れ枚数（有効牌の多さ）を重視する。高いほど最速の形を選ぶ。",
  dora_weight: "ドラを手に残そうとする。",
  yakuhai_weight: "役牌の対子・刻子を大事にし、ポンしやすくなる。",
  flush_weight: "1色に寄せて染め手（混一色・清一色）を狙う。",
  tanyao_weight: "么九牌を先に切ってタンヤオに寄せる。",
  call_weight: "チー・ポンをしやすい。低いと門前で進める。",
  riichi_weight: "聴牌したらリーチをかけやすい。低いとダマテンが増える。",
  defense_weight: "他家のリーチや仕掛けに対して、危険牌を切らない強さ（降りの基本の強さ）。",
  push_weight: "自分の手が良いとき（聴牌・一向聴や高い手）に、守備を弱めて押し返す度合い。",
};
const SERIES = ["#4ff0ff", "#ffb648", "#ff7a7a", "#7ee787"];

// ------------------------------------------------------------
// データ読み込み
// ------------------------------------------------------------
const cache = new Map();
function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(BASE + path, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${path} を読み込めませんでした (${r.status})`);
      return r.json();
    }));
  }
  return cache.get(path);
}
const tryJSON = (path) => getJSON(path).catch(() => null);
const getIndex = () => getJSON("index.json");
async function getPlayers() {
  const list = await getJSON("players.json");
  if (!list._byId) list._byId = Object.fromEntries(list.map((p) => [p.id, p]));
  return list;
}
// 雀士ごとの詳細（最近の対局・対戦相手別・半荘ごとのレート推移）。無ければ一覧の情報だけで表示する
async function getDetail(id) {
  const d = await tryJSON(`players/${encodeURIComponent(id)}.json`);
  if (d) return d;
  return (await getPlayers())._byId[id] || null;
}
async function api(path, options) {
  const r = await fetch(API + path, { cache: "no-store", ...options });
  let body = null;
  try { body = await r.json(); } catch { /* HTMLのエラーページなど */ }
  if (!r.ok || !body || body.ok === false) throw new Error((body && body.error) || `API に接続できませんでした (${r.status})`);
  return body;
}
const apiUnavailable = (e) => `<div class="empty">集計サーバーに接続できません<br><span class="small">${esc(e.message)}</span></div>`;

// ------------------------------------------------------------
// 表示ヘルパー
// ------------------------------------------------------------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sign = (v, d = 1) => `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}`;
const pt = (v) => `<span class="${v > 0 ? "plus" : v < 0 ? "minus" : ""}">${sign(v)}</span>`;
const pct = (a, b, d = 1) => (b ? `${((a / b) * 100).toFixed(d)}%` : "-");
const avgPlace = (pl, g) => (g ? (pl.reduce((a, c, i) => a + c * (i + 1), 0) / g) : null);
const ageOf = (p) => p.initial_age + p.total_seasons;
const plink = (id, name) => `<span class="link" data-id="${esc(id)}">${esc(name || id)}</span>`;
const secTitle = (label) => `<h4 class="sec">${label}</h4>`;
function leagueTag(lg) {
  const isTitle = TITLES.includes(lg);
  return `<span class="league-tag${isTitle ? " title-tag" : ""}">${esc(lg)}</span>`;
}
function seasonNav(season, maxSeason, prefix, minSeason = 1) {
  return `<div class="season-nav">
    <button data-go="${prefix}/${season - 1}" ${season <= minSeason ? "disabled" : ""}>◀ 前季</button>
    <span class="label">第${season}季</span>
    <button data-go="${prefix}/${season + 1}" ${season >= maxSeason ? "disabled" : ""}>次季 ▶</button>
  </div>`;
}
// 連続した季をまとめて「第1〜3季・第5季」のように表す
function seasonRanges(seasons) {
  const s = [...new Set(seasons)].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < s.length; i++) {
    let j = i;
    while (j + 1 < s.length && s[j + 1] === s[j] + 1) j++;
    out.push(i === j ? `第${s[i]}季` : `第${s[i]}〜${s[j]}季`);
    i = j;
  }
  return out.join("・");
}

// 現在のタイトル保持者（id → [タイトル]）
let HOLDERS = {};
function setHolders(idx) {
  HOLDERS = {};
  for (const [t, h] of Object.entries(idx.titleholders || {})) if (h) (HOLDERS[h.id] ||= []).push(t);
}
// 段位規定：初段から始まり、九段が最高。段位は下がらない。
// 昇段ポイント（季ごと）＝所属リーグの参加点 ＋ 順位ボーナス ＋ タイトル獲得（防衛を含む）
//   参加点：A 6 / B 4 / C 2 / D 1　順位ボーナス：A（1位 +4、3位以内 +2）、B〜D（1位 +2、3位以内 +1）
//   タイトル：鳳凰位 +8、その他 +5
// 累計ポイントの目安：二段 3 / 三段 7 / 四段 12 / 五段 18 / 六段 26 / 七段 36 / 八段 50 / 九段 70（九段はタイトル経験者のみ）
const DAN_NAMES = ["初段", "二段", "三段", "四段", "五段", "六段", "七段", "八段", "九段"];
const DAN_THRESHOLDS = [0, 3, 7, 12, 18, 26, 36, 50, 70];
const LEAGUE_ENTRY_POINTS = { A: 6, B: 4, C: 2, D: 1 };
// 季ごとの昇段ポイントの内訳から、段位の推移（昇段履歴）を組み立てる
function danHistory(p, titleHistory) {
  const bySeason = new Map();
  const add = (season, label, pts) => {
    if (!bySeason.has(season)) bySeason.set(season, { items: [], titles: 0 });
    bySeason.get(season).items.push({ label, pts });
    return bySeason.get(season);
  };
  for (const c of p.career || []) {
    add(c.season, `${c.league}リーグ参加`, LEAGUE_ENTRY_POINTS[c.league] || 0);
    if (c.rank === 1) add(c.season, `${c.league}リーグ1位`, c.league === "A" ? 4 : 2);
    else if (c.rank && c.rank <= 3) add(c.season, `${c.league}リーグ${c.rank}位`, c.league === "A" ? 2 : 1);
  }
  for (const h of titleHistory) {
    if (h.winner_id !== p.id) continue;
    const t = titleName(h.title);
    add(h.season, `${t}${{ "初代": "獲得", "奪取": "奪取", "防衛": "防衛" }[h.event] || "獲得"}`, t === "鳳凰位" ? 8 : 5).titles += 1;
  }
  const rows = [], promotions = [];
  let total = 0, titles = 0, level = 0, capped = false;
  for (const season of [...bySeason.keys()].sort((x, y) => x - y)) {
    const g = bySeason.get(season);
    const sum = g.items.reduce((a, i) => a + i.pts, 0);
    total += sum;
    titles += g.titles;
    let lvl = 0;
    DAN_THRESHOLDS.forEach((t, i) => { if (total >= t) lvl = i; });
    capped = false;
    if (lvl === DAN_NAMES.length - 1 && !titles) { lvl = DAN_NAMES.length - 2; capped = true; } // 九段はタイトル経験者のみ
    if (lvl > level) { promotions.push({ season, from: level, to: lvl, total, items: g.items }); level = lvl; }
    rows.push({ season, items: g.items, sum, total, level });
  }
  return { rows, promotions, total, level, titles, capped };
}
function danOf(p, titleHistory) {
  const h = danHistory(p, titleHistory);
  return { level: h.level, name: DAN_NAMES[h.level], pts: h.total };
}
let DANS = {};
function setDans(players, idx) {
  DANS = {};
  for (const p of players) DANS[p.id] = danOf(p, idx.title_history || []);
}
// 昇段履歴と昇段理由（個体ページ）
function danHistoryHtml(p, idx) {
  const h = danHistory(p, idx.title_history || []);
  const itemsText = (items) => items.map((i) => `${esc(i.label)} +${i.pts}`).join("、");
  let html = `<div class="note">初段からスタートし、九段が最高です。段位は下がりません（規定は「？」のルール画面）。</div>`;
  if (!h.promotions.length) {
    html += `<div class="dim small" style="padding:4px 0;">まだ昇段していません（${DAN_NAMES[h.level]}・累計${h.total}pt）</div>`;
  } else {
    const rows = [...h.promotions].reverse().map((m) => `<div class="list-row"><span><b style="color:var(--amber);">${DAN_NAMES[m.from]} → ${DAN_NAMES[m.to]}</b>
        <span class="dim small">第${m.season}季</span><br><span class="dim small">${itemsText(m.items)}で累計${m.total}pt（${DAN_NAMES[m.to]}は${DAN_THRESHOLDS[m.to]}pt〜）</span></span></div>`);
    html += collapsibleList(rows, 5, "件");
  }
  if (h.capped) html += `<div class="note">九段の条件（${DAN_THRESHOLDS[8]}pt）に達していますが、九段にはタイトル獲得経験が必要なため、八段のままです。</div>`;
  if (h.rows.length) {
    const seasonRows = [...h.rows].reverse().map((r) => `<div class="list-row"><span>第${r.season}季 <span class="dim small">${itemsText(r.items)}</span></span>
        <span class="num">+${r.sum} <span class="dim small">累計${r.total}pt</span></span></div>`);
    html += collapsible(seasonRows.join(""), "季ごとのポイント");
  }
  return html;
}
// 個体ページの見出しに出す段位の枠（タイトル保持者はタイトルも並べる）
function danBlock(id) {
  const d = DANS[id];
  if (!d) return "";
  const titles = TITLES.filter((t) => (HOLDERS[id] || []).includes(t));
  const next = d.level >= DAN_NAMES.length - 1 ? "最高段位"
    : d.level === 7 && d.pts >= DAN_THRESHOLDS[8] ? "九段にはタイトル獲得が必要"
    : `次の${DAN_NAMES[d.level + 1]}まで あと${DAN_THRESHOLDS[d.level + 1] - d.pts}pt`;
  return `<div class="dan-row">${titles.map((t) => `<span class="crown big">${esc(t)}</span>`).join("")}<span class="dan-box">${d.name}</span></div>
      <div class="dim small">昇段ポイント ${d.pts}pt（${next}）</div>`;
}
// 名前の右に付ける表示：タイトル保持者はタイトル（橙のハイライト）、それ以外は段位（橙の枠・橙の文字）
function nameTag(id) {
  const titles = TITLES.filter((t) => (HOLDERS[id] || []).includes(t));
  if (titles.length) {
    const label = titles.length === 1 ? TITLE_SHORT[titles[0]] : ["", "", "二冠", "三冠", "四冠"][titles.length];
    return `<span class="crown">${esc(label)}</span>`;
  }
  const d = DANS[id];
  return d ? `<span class="dan-tag">${d.name}</span>` : "";
}
const MOVEMENT_MARKS = {
  promoted: '<span class="movement-mark" style="color:var(--up);" title="昇級">昇↑</span>',
  relegated: '<span class="movement-mark" style="color:var(--down);" title="降級">降↓</span>',
  retired: '<span class="movement-mark dim" title="引退">退</span>',
  new: '<span class="movement-mark" style="color:var(--new);" title="新規参入">新</span>',
};
const movementMark = (m) => MOVEMENT_MARKS[m] || "";

// 同率順位（1位、1位、3位…）
function competitionRanks(rows, keyFn) {
  const ranks = [];
  let rank = 0, prev;
  rows.forEach((r, i) => {
    const k = keyFn(r);
    if (i === 0 || k !== prev) rank = i + 1;
    prev = k;
    ranks.push(rank);
  });
  return ranks;
}
let _seq = 0;
function collapsible(restHtml, label) {
  const uid = "cl" + (_seq++);
  return `<div class="collapsible-toggle" data-target="${uid}"><span class="collapsible-arrow">▶</span><span data-show-text="${esc(label)}">${esc(label)}</span></div>
    <div id="${uid}" class="hidden">${restHtml}</div>`;
}
// 上位 topN 件は常時表示、残りは折りたたむ表
function collapsibleTable(headHtml, rows, rowFn, topN, keyFn) {
  const ranks = keyFn ? competitionRanks(rows, keyFn) : rows.map((_, i) => i + 1);
  const table = (list, offset) => `<div class="scroll-x"><table>${headHtml}<tbody>${list.map((r, i) => rowFn(r, ranks[offset + i])).join("")}</tbody></table></div>`;
  let html = table(rows.slice(0, topN), 0);
  if (rows.length > topN) html += collapsible(table(rows.slice(topN), topN), `他${rows.length - topN}件を表示`);
  return html;
}
function collapsibleList(items, topN, unit) {
  let html = items.slice(0, topN).join("");
  if (items.length > topN) html += collapsible(items.slice(topN).join(""), `他${items.length - topN}${unit}を表示`);
  return html;
}

// ---------------- 牌 ----------------
const HONORS = ["東", "南", "西", "北", "白", "發", "中"];
const SUIT_CLASS = ["m", "p", "s"];
const SUIT_CHAR = ["萬", "筒", "索"];
const KANJI_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九"];
// 牌譜の牌番号：0-33 が通常の牌、34・35・36 が赤五萬・赤五筒・赤五索
const kindOf = (t) => (t >= 34 ? [4, 13, 22][t - 34] : t);
const byKind = (a, b) => kindOf(a) - kindOf(b) || a - b;
const tileName = (t) => (t >= 34 ? `赤5${SUIT_CLASS[t - 34]}` : t >= 27 ? HONORS[t - 27] : `${(t % 9) + 1}${SUIT_CLASS[Math.floor(t / 9)]}`);
// 筒子・索子は実物に近い図柄（丸・竹）をSVGで描く。座標は幅30×高さ40の牌面
const PIN_COLORS = { b: "#1f4f96", r: "#c0392b", g: "#1d6b3e" };
const PIN_LAYOUT = [
  [[15, 20, 10, "r"]],
  [[15, 11, 6, "b"], [15, 29, 6, "g"]],
  [[8, 8, 5, "b"], [15, 20, 5, "r"], [22, 32, 5, "g"]],
  [[9, 11, 5, "b"], [21, 11, 5, "g"], [9, 29, 5, "g"], [21, 29, 5, "b"]],
  [[8, 9, 4.6, "b"], [22, 9, 4.6, "g"], [15, 20, 4.6, "r"], [8, 31, 4.6, "g"], [22, 31, 4.6, "b"]],
  [[9, 8, 4.4, "g"], [21, 8, 4.4, "g"], [9, 21, 4.4, "r"], [21, 21, 4.4, "r"], [9, 32, 4.4, "r"], [21, 32, 4.4, "r"]],
  [[7, 6, 3.8, "g"], [15, 10, 3.8, "g"], [23, 14, 3.8, "g"], [9, 24, 3.8, "r"], [21, 24, 3.8, "r"], [9, 34, 3.8, "r"], [21, 34, 3.8, "r"]],
  [[9, 6, 3.9, "b"], [21, 6, 3.9, "b"], [9, 15.3, 3.9, "b"], [21, 15.3, 3.9, "b"], [9, 24.7, 3.9, "b"], [21, 24.7, 3.9, "b"], [9, 34, 3.9, "b"], [21, 34, 3.9, "b"]],
  [[7, 8, 3.8, "b"], [15, 8, 3.8, "b"], [23, 8, 3.8, "b"], [7, 20, 3.8, "r"], [15, 20, 3.8, "r"], [23, 20, 3.8, "r"], [7, 32, 3.8, "g"], [15, 32, 3.8, "g"], [23, 32, 3.8, "g"]],
];
// 索子：[x, y, 長さ, 色]（竹は縦向き、幅は共通）
const SOU_LAYOUT = [
  null,
  [[15, 11, 14, "g"], [15, 29, 14, "g"]],
  [[15, 11, 14, "g"], [9, 29, 14, "g"], [21, 29, 14, "g"]],
  [[9, 11, 14, "g"], [21, 11, 14, "g"], [9, 29, 14, "g"], [21, 29, 14, "g"]],
  [[8, 11, 14, "g"], [22, 11, 14, "g"], [15, 20, 14, "r"], [8, 29, 14, "g"], [22, 29, 14, "g"]],
  [[7, 11, 14, "g"], [15, 11, 14, "g"], [23, 11, 14, "g"], [7, 29, 14, "g"], [15, 29, 14, "g"], [23, 29, 14, "g"]],
  [[15, 6, 9, "r"], [7, 20, 9, "g"], [15, 20, 9, "g"], [23, 20, 9, "g"], [7, 33, 9, "g"], [15, 33, 9, "g"], [23, 33, 9, "g"]],
  [[5, 11, 14, "g"], [11.7, 11, 14, "g"], [18.3, 11, 14, "g"], [25, 11, 14, "g"], [5, 29, 14, "g"], [11.7, 29, 14, "g"], [18.3, 29, 14, "g"], [25, 29, 14, "g"]],
  [[7, 7, 10, "g"], [15, 7, 10, "r"], [23, 7, 10, "g"], [7, 20, 10, "g"], [15, 20, 10, "r"], [23, 20, 10, "g"], [7, 33, 10, "g"], [15, 33, 10, "r"], [23, 33, 10, "g"]],
];
function pinSVG(n, aka = false) {
  return PIN_LAYOUT[n].map(([x, y, r, c]) => {
    const col = aka ? PIN_COLORS.r : PIN_COLORS[c];
    return `<circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="${col}" stroke-width="${r * 0.32}"/><circle cx="${x}" cy="${y}" r="${r * 0.38}" fill="${col}"/>`
      + (n === 0 ? `<circle cx="${x}" cy="${y}" r="${r * 0.7}" fill="none" stroke="${PIN_COLORS.g}" stroke-width="1"/>` : "");
  }).join("");
}
function stick(x, y, len, c) {
  const col = PIN_COLORS[c], w = 4.2, top = y - len / 2;
  return `<rect x="${x - w / 2}" y="${top}" width="${w}" height="${len}" rx="1.6" fill="${col}"/>`
    + `<line x1="${x}" y1="${top + 1.2}" x2="${x}" y2="${top + len - 1.2}" stroke="#fff" stroke-opacity="0.55" stroke-width="0.8"/>`
    + `<line x1="${x - w / 2}" y1="${y}" x2="${x + w / 2}" y2="${y}" stroke="#fff" stroke-opacity="0.8" stroke-width="0.9"/>`;
}
function souSVG(n, aka = false) {
  if (n === 0) { // 一索は鳥（孔雀）の図柄：扇形の尾羽、緑の胴、赤い頭とくちばし
    const G = PIN_COLORS.g, R = PIN_COLORS.r, B = PIN_COLORS.b;
    const feathers = [-50, -25, 0, 25, 50].map((a) => {
      const rad = (a - 90) * Math.PI / 180, x = 13 + Math.cos(rad) * 11, y = 22 + Math.sin(rad) * 11;
      return `<line x1="13" y1="22" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${G}" stroke-width="1.6"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.3" fill="${B}" stroke="${G}" stroke-width="0.8"/>`;
    }).join("");
    return `${feathers}
      <ellipse cx="15" cy="25" rx="6.5" ry="5" fill="${G}"/>
      <path d="M11 26 q4 -4 9 -1" fill="none" stroke="#9fd18b" stroke-width="1"/>
      <path d="M19 23 q3 -4 3 -8" fill="none" stroke="${G}" stroke-width="2.6" stroke-linecap="round"/>
      <circle cx="22.3" cy="13.8" r="2.6" fill="${R}"/>
      <path d="M24.6 13.4 l3 0.9 l-3 0.9 z" fill="#d9a21b"/>
      <circle cx="22.8" cy="13.2" r="0.6" fill="#fff"/>
      <line x1="13" y1="29.5" x2="12" y2="35" stroke="${R}" stroke-width="1.2"/><line x1="17" y1="29.5" x2="18" y2="35" stroke="${R}" stroke-width="1.2"/>
      <line x1="10" y1="35" x2="14" y2="35" stroke="${R}" stroke-width="1"/><line x1="16" y1="35" x2="20" y2="35" stroke="${R}" stroke-width="1"/>`;
  }
  return SOU_LAYOUT[n].map(([x, y, len, c]) => stick(x, y, len, aka ? "r" : c)).join("");
}
function tile(t, extra = "", small = false) {
  const sz = small ? " sm" : "";
  const aka = t >= 34;
  if (aka) { t = kindOf(t); extra += " aka"; }
  if (t >= 27) {
    const cls = { 31: "haku", 32: "hatsu", 33: "chun" }[t] || "";
    return `<span class="tile z ${cls}${sz} ${extra}" title="${HONORS[t - 27]}">${HONORS[t - 27]}</span>`;
  }
  const suit = Math.floor(t / 9), n = t % 9;
  if (suit === 0) {
    return `<span class="tile m${sz} ${extra}" title="${tileName(t)}"><span class="n">${KANJI_NUM[n]}</span><small>${SUIT_CHAR[0]}</small></span>`;
  }
  const art = suit === 1 ? pinSVG(n, aka) : souSVG(n, aka);
  return `<span class="tile ${SUIT_CLASS[suit]} art${sz} ${extra}" title="${tileName(t)}"><svg viewBox="0 0 30 40" aria-hidden="true">${art}</svg></span>`;
}
const tilesHTML = (arr, small = false) => `<span class="tiles">${arr.map((t) => tile(t, "", small)).join("")}</span>`;
function meldHTML(m, small = true) {
  const tiles = m.tiles.map((t, i) => {
    if (m.kind === "ankan" && (i === 0 || i === 3)) return `<span class="tile back${small ? " sm" : ""}"></span>`;
    return tile(t, m.kind !== "ankan" && i === 0 ? "side" : "", small);
  });
  return `<span class="meld">${tiles.join("")}</span>`;
}

// ------------------------------------------------------------
// タブ構成（オセロ版と同じ2階層）
//   subLabels方式＝サブタブごとに別URL / subViews方式＝1つのタブ内で表示だけ切り替える
// ------------------------------------------------------------
const TITLES_VIEWS = ["current", ...TITLES];
const TITLES_VIEW_LABELS = { current: "現在の保持者", ...Object.fromEntries(TITLES.map((t) => [t, "歴代" + t])) };
let _titlesView = "current";
const HOF_VIEWS = ["ranking", "records", "retired", "awakened"];
const HOF_VIEW_LABELS = { ranking: "総合ランキング", records: "記録集", retired: "引退者一覧", awakened: "覚醒者一覧" };
let _hofView = "ranking";

const TAB_GROUPS = {
  newcomer_group: {
    tabs: ["newcomer_create", "newcomer", "newcomer_history"],
    subLabels: { newcomer_create: "キャラクリエイト", newcomer: "結果", newcomer_history: "歴代記録" },
  },
  leagues: { tabs: ["leagues", "clans"], subLabels: { leagues: "鳳凰戦リーグ表", clans: "一門" } },
  results: {
    tabs: ["houou", "hououi", "kirin", "reiki", "ouryu", "awards", "matches"],
    subLabels: { houou: "鳳凰戦リーグ", hououi: "鳳凰位決定戦", kirin: "麒麟戦", reiki: "霊亀戦", ouryu: "応龍戦", awards: "表彰", matches: "対局記録" },
  },
  titles: {
    tabs: ["titles"],
    subViews: () => TITLES_VIEWS.map((v) => ({ key: v, label: TITLES_VIEW_LABELS[v] })),
    active: () => _titlesView,
    onSubView: (k) => { _titlesView = k; render("titles"); },
  },
  hof: {
    tabs: ["hof"],
    subViews: () => HOF_VIEWS.map((v) => ({ key: v, label: HOF_VIEW_LABELS[v] })),
    active: () => _hofView,
    onSubView: (k) => { _hofView = k; render("hof"); },
  },
};
const IMPLICIT_GROUP = { individual: "leagues", game: "results", kifu: "results" };
function groupOf(tab) {
  for (const [k, g] of Object.entries(TAB_GROUPS)) if (g.tabs.includes(tab)) return k;
  return IMPLICIT_GROUP[tab] || null;
}
function renderSubtabs(groupKey, activeTab) {
  const wrap = document.getElementById("subtabs");
  const g = TAB_GROUPS[groupKey];
  let items = [];
  if (g && g.subViews) items = g.subViews().map((v) => `<button class="subtab-btn${v.key === g.active() ? " active" : ""}" data-view="${v.key}">${v.label}</button>`);
  else if (g) items = g.tabs.map((t) => `<button class="subtab-btn${t === activeTab ? " active" : ""}" data-go="${t}">${g.subLabels[t]}</button>`);
  wrap.classList.toggle("hidden", items.length <= 1);
  wrap.innerHTML = items.join("");
  wrap.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => g.onSubView(b.dataset.view)));
}
function showTab(tab) {
  const groupKey = groupOf(tab);
  document.querySelectorAll("#primary-tabs .tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.group === groupKey));
  renderSubtabs(groupKey, tab);
}
document.querySelectorAll("#primary-tabs .tab-btn").forEach((b) => b.addEventListener("click", () => navigateTo(TAB_GROUPS[b.dataset.group].tabs[0])));

// ------------------------------------------------------------
// 共通の操作（モーダル・折りたたみ・リンク・お気に入り・更新チェック）
// ------------------------------------------------------------
function openModal(title, bodyHtml) {
  document.getElementById("modal-content").innerHTML = `<h3 style="margin:0 0 10px; color:var(--amber); font-size:0.9rem;">${esc(title)}</h3>${bodyHtml}`;
  document.getElementById("modal-overlay").classList.remove("hidden");
}
const closeModal = () => document.getElementById("modal-overlay").classList.add("hidden");
document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-overlay").addEventListener("click", (e) => { if (e.target.id === "modal-overlay") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
document.getElementById("rules-help-btn").addEventListener("click", async () => openModal("ルール", await rulesHtml()));

document.addEventListener("click", (e) => {
  const toggle = e.target.closest(".collapsible-toggle");
  if (toggle) {
    const body = document.getElementById(toggle.dataset.target);
    if (!body) return;
    const hidden = body.classList.toggle("hidden");
    toggle.querySelector(".collapsible-arrow").textContent = hidden ? "▶" : "▼";
    const label = toggle.querySelector("span:last-child");
    label.textContent = hidden ? label.dataset.showText : "閉じる";
    return;
  }
  const go = e.target.closest("[data-go]");
  if (go && !go.disabled) { navigateTo(go.dataset.go); return; }
  const who = e.target.closest("tr[data-id], .link[data-id], .title-card[data-id]");
  if (who && document.getElementById("panel").contains(who)) navigateTo("individual/" + who.dataset.id);
});

// お気に入り：星を付けた雀士のIDをこの端末（localStorage）だけに保存し、一覧で強調表示する
const FAVORITES_KEY = "mahjong_league_favorites_v1";
function favIds() {
  try { return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]")); } catch { return new Set(); }
}
function toggleFavorite(id) {
  const ids = favIds();
  if (ids.has(id)) ids.delete(id); else ids.add(id);
  try { localStorage.setItem(FAVORITES_KEY, JSON.stringify([...ids])); } catch { /* 保存できなくても致命的ではない */ }
  applyFavorites();
}
function applyFavorites() {
  const ids = favIds();
  document.querySelectorAll("#panel tr[data-id]").forEach((el) => el.classList.toggle("fav-highlight", ids.has(el.dataset.id)));
  const btn = document.getElementById("ind-fav-toggle");
  if (btn) {
    const fav = ids.has(btn.dataset.fav);
    btn.classList.toggle("is-fav", fav);
    btn.textContent = fav ? "★ お気に入り登録済み" : "☆ お気に入りに追加";
  }
}

// 開いたままのタブでも、新しい季が反映されたらバナーで知らせる（表示は勝手に書き換えない）
let _seenSeason = null;
async function checkForUpdates() {
  try {
    const r = await fetch(BASE + "index.json", { cache: "no-store" });
    const s = (await r.json()).current_season;
    if (_seenSeason === null) _seenSeason = s;
    else if (s !== _seenSeason) document.getElementById("fresh-banner").classList.remove("hidden");
  } catch { /* 通信できないときは次回に任せる */ }
}
document.getElementById("fresh-reload").addEventListener("click", () => location.reload());
checkForUpdates();
setInterval(checkForUpdates, 60000);

// ------------------------------------------------------------
// リーグ：今季（次の季）の所属
// ------------------------------------------------------------
async function viewLeagues() {
  const [idx, players] = await Promise.all([getIndex(), getPlayers()]);
  const next = idx.current_season + 1;
  const houou = idx.titleholders?.["鳳凰位"];
  const dRows = (idx.leagues?.D || []).length;
  const dVacancy = Math.max(0, LEAGUE_CAPACITY.D - dRows);
  let pending = [], ready = false;
  if (dVacancy > 0) {
    const nl = await tryJSON(`newcomer_league/for_season_${next}.json`);
    if (nl) { ready = true; pending = (nl.standings || []).filter((s) => s.winner); }
  }
  let html = `<h3 class="view-title">第${next}季 鳳凰戦・リーグ表</h3>`;
  for (const lg of LEAGUES) {
    const members = (idx.leagues?.[lg] || []).map((id) => players._byId[id]).filter(Boolean);
    const holder = houou && members.find((p) => p.id === houou.id);
    const rows = members.filter((p) => p !== holder);
    const vacancy = lg === "D" ? dVacancy : 0;
    html += `<div class="league-block"><h3>${lg}リーグ（${rows.length}名${vacancy ? `+欠員${vacancy}` : ""}${holder ? "+鳳凰位" : ""}）</h3>`;
    if (holder) {
      html += `<table style="margin-bottom:4px;"><tbody><tr data-id="${esc(holder.id)}">
        <td class="rank-num">-</td><td>${esc(holder.display_name)}${nameTag(holder.id)} <span class="chip gold">リーグ免除</span></td>
        <td class="num">${ageOf(holder)}歳</td><td class="num elo-val">${Math.round(holder.elo)}</td></tr></tbody></table>`;
    }
    html += `<table><thead><tr><th>#</th><th>名前</th><th class="num">年齢</th><th class="num">レート</th></tr></thead><tbody>`;
    rows.forEach((p, i) => {
      html += `<tr data-id="${esc(p.id)}"><td class="rank-num">${i + 1}</td>
        <td>${esc(p.display_name)}${nameTag(p.id)}${p.created ? ' <span class="chip cyan">投稿</span>' : ""}</td>
        <td class="num">${ageOf(p)}歳</td><td class="num elo-val">${Math.round(p.elo)}</td></tr>`;
    });
    for (let i = 0; i < vacancy; i++) {
      const nc = pending[i];
      html += nc
        ? `<tr style="opacity:0.75;"><td class="rank-num">${movementMark("new")}</td><td>${esc(nc.name)}<span class="small" style="color:var(--cyan); margin-left:4px;">（新人リーグ選抜）</span></td><td class="num">-</td><td class="num">-</td></tr>`
        : `<tr style="opacity:0.5;"><td class="rank-num">-</td><td class="dim">${ready ? "新弟子（自動生成予定）" : "新人リーグ結果待ち"}</td><td class="num">-</td><td class="num">-</td></tr>`;
    }
    html += "</tbody></table></div>";
  }
  html += `<div class="note">並びは、上のリーグから降級してきた雀士、残留した雀士（前季の順位順）、下のリーグから昇級してきた雀士の順。昇降級の結果は「結果」タブの鳳凰戦リーグで見られます。</div>`;
  return html;
}

// ------------------------------------------------------------
// 一門
// ------------------------------------------------------------
async function viewClans() {
  const [players, idx] = await Promise.all([getPlayers(), getIndex()]);
  const clans = {};
  players.forEach((p) => (clans[p.clan_root_id] ||= []).push(p));
  const titleCount = {};
  idx.title_history.forEach((h) => { const r = players._byId[h.winner_id]?.clan_root_id; if (r) titleCount[r] = (titleCount[r] || 0) + 1; });
  const list = Object.entries(clans).map(([root, members]) => ({
    root, members, active: members.filter((m) => !m.retired).length, titles: titleCount[root] || 0,
    best: Math.max(...members.map((m) => m.peak_elo)),
  })).filter((c) => c.members.length > 1).sort((a, b) => b.titles - a.titles || b.active - a.active || b.best - a.best);
  if (!list.length) return `<div class="empty">まだ弟子を持つ一門はありません</div>`;
  return `<h3 class="view-title">一門</h3>
    <div class="note">師弟関係でつながる系統。弟子は師匠の打ち筋を受け継ぎます（弟子のいる系統だけを表示）。</div>
    <table><thead><tr><th>一門</th><th class="num">現役</th><th class="num">総数</th><th class="num">タイトル</th><th class="num">最高レート</th></tr></thead><tbody>
    ${list.map((c) => `<tr data-go="clans/${esc(c.root)}"><td>${esc(players._byId[c.root]?.display_name || c.root)}一門</td>
      <td class="num">${c.active}</td><td class="num">${c.members.length}</td><td class="num">${c.titles ? c.titles + "期" : "-"}</td><td class="num elo-val">${Math.round(c.best)}</td></tr>`).join("")}
    </tbody></table>`;
}
async function viewClan(root) {
  const players = await getPlayers();
  const members = players.filter((p) => p.clan_root_id === root);
  const children = {};
  members.forEach((p) => { if (p.id !== root && p.parent_a_id) (children[p.parent_a_id] ||= []).push(p); });
  const node = (id, depth = 0) => {
    const p = players._byId[id];
    if (!p || depth > 40) return "";
    const kids = (children[id] || []).map((c) => node(c.id, depth + 1)).join("");
    return `<li>${plink(p.id, p.display_name)}${nameTag(p.id)} <span class="dim small">${p.retired ? "引退" : p.league + "リーグ"}・レート${Math.round(p.elo)}</span>${kids ? `<ul>${kids}</ul>` : ""}</li>`;
  };
  return `<div class="back-link" data-go="clans">← 一門一覧に戻る</div>
    <h3 class="view-title">${esc(players._byId[root]?.display_name || root)}一門（${members.length}名）</h3>
    <div class="tree"><ul>${node(root)}</ul></div>`;
}

// ------------------------------------------------------------
// 結果：鳳凰戦（季ごとの成績表）
// ------------------------------------------------------------
async function viewHouou(season) {
  const idx = await getIndex();
  if (!idx.current_season) return `<div class="empty">まだ記録がありません</div>`;
  const s = Math.min(Math.max(1, season || idx.current_season), idx.current_season);
  const standings = await getJSON(`standings/season_${s}.json`);
  const winners = Object.fromEntries(idx.title_history.filter((h) => h.season === s).map((h) => [h.winner_id, h.title]));
  let html = seasonNav(s, idx.current_season, "houou") + `<h3 class="view-title">鳳凰戦リーグ 成績（A〜D）</h3>`;
  for (const lg of LEAGUES) {
    const rows = standings.filter((r) => r.league === lg);
    if (!rows.length) continue;
    const ranked = rows.filter((r) => r.rank);
    const n = ranked.length, z = LEAGUE_ZONES[lg];
    html += `<div class="league-block"><h3>${lg}リーグ</h3>`;
    const ex = rows.find((r) => r.exempt);
    if (ex) html += `<table style="margin-bottom:4px;"><tbody><tr data-id="${esc(ex.id)}"><td class="rank-num">-</td>
      <td>${esc(ex.name)}${nameTag(ex.id)} <span class="chip gold">リーグ免除</span></td><td class="num elo-val">${Math.round(ex.elo)}</td></tr></tbody></table>`;
    html += `<div class="scroll-x"><table><thead><tr><th>#</th><th>名前</th><th class="num">pt</th><th class="num">半荘</th><th class="num hide-sm">1/2/3/4着</th><th class="num">平均着順</th></tr></thead><tbody>`;
    ranked.forEach((r) => {
      let zone = "";
      if (lg === "A" && r.rank <= 3) zone = "zone-final";
      else if (z.up && r.rank <= z.up) zone = "zone-up";
      else if (z.down && r.rank > n - z.down) zone = "zone-down";
      const avg = avgPlace(r.placements, r.games);
      const won = winners[r.id] ? `<span class="chip gold">${esc(winners[r.id])}</span>` : "";
      html += `<tr class="${zone}" data-id="${esc(r.id)}"><td class="rank-num">${r.rank}</td>
        <td>${movementMark(r.new ? "new" : "")}${movementMark(r.movement)}${esc(r.name)}${nameTag(r.id)}${won}</td>
        <td class="num">${pt(r.points)}</td><td class="num">${r.games}</td><td class="num hide-sm dim">${r.placements.join("/")}</td>
        <td class="num">${avg ? avg.toFixed(2) : "-"}</td></tr>`;
    });
    html += "</tbody></table></div></div>";
  }
  html += `<div class="legend"><span><i style="background:var(--amber)"></i>鳳凰位決定戦進出</span><span><i style="background:var(--up)"></i>昇級</span><span><i style="background:var(--down)"></i>降級</span></div>
    <div class="note">1節4半荘。年間の合計ポイントで順位を決めます。Dリーグで2年連続マイナスの雀士は引退。</div>`;
  return html;
}

// ------------------------------------------------------------
// 結果：タイトル戦（鳳凰位決定戦・麒麟戦・霊亀戦・応龍戦）
// ------------------------------------------------------------
async function viewTitleResult(tab, season) {
  const name = RESULT_TITLE_TABS[tab];
  const [idx, players] = await Promise.all([getIndex(), getPlayers()]);
  if (!idx.current_season) return `<div class="empty">まだ記録がありません</div>`;
  const s = Math.min(Math.max(1, season || idx.current_season), idx.current_season);
  const [titles, matches] = await Promise.all([getJSON(`titles/season_${s}.json`), getJSON(`matches/season_${s}.json`)]);
  const nav = seasonNav(s, idx.current_season, tab);
  const t = titles.find((x) => titleName(x.title) === name);
  if (!t) return nav + `<div class="empty">第${s}季の${TITLE_EVENT_NAME[name]}は行われていません</div>`;
  const nm = (id) => players._byId[id]?.display_name || id;
  const finalStage = t.stages[t.stages.length - 1];
  const finalGames = matches.filter((m) => m.event.kind === "title" && titleName(m.event.title) === name && m.event.stage === finalStage.name)
    .sort((a, b) => a.event.game - b.event.game);
  const ids = finalStage.tables[0].members;
  const cum = Object.fromEntries(ids.map((id) => [id, [0]]));
  finalGames.forEach((g) => ids.forEach((id) => {
    const i = g.seats.indexOf(id), arr = cum[id];
    arr.push(Math.round((arr[arr.length - 1] + (i >= 0 ? g.points[i] : 0)) * 10) / 10);
  }));
  // この季に実際に使われたルール（第1季は旧ルール）
  const ruleKey = finalGames[0]?.event.rule || TITLE_RULE[name];
  const rule = idx.rules?.[ruleKey];
  const wl = rule?.uma_mode === "win_loss";
  const P = (v) => ptOf(v, wl);
  const rawOf = (id) => {
    let sum = 0;
    finalGames.forEach((g) => { const i = g.seats.indexOf(id); if (i >= 0) sum += (g.final_scores[i] - 30000) / 1000; });
    return Math.round(sum * 10) / 10;
  };
  const eventChip = t.event === "奪取" ? '<span class="chip gold">奪取</span>' : t.event === "防衛" ? '<span class="chip cyan">防衛</span>' : '<span class="chip">初代</span>';
  let html = nav + `<h3 class="view-title">${TITLE_EVENT_NAME[name]}</h3>
    <div class="note">${TITLE_DESC[name]}</div>
    ${rule ? collapsible(`<div style="font-size:0.78rem; margin-bottom:8px;">${ruleSummary(rule)}</div>`, `ルール：${rule.name}`) : ""}
    <div style="text-align:center; margin:14px 0;">
      <div class="dim small">第${s}季 ${esc(name)}</div>
      <div style="font-size:1.1rem; font-weight:700; margin-top:4px;">${plink(t.winner_id, t.winner_name)} ${eventChip}</div>
      ${t.previous_name ? `<div class="dim small">前${esc(name)}：${esc(t.previous_name)}</div>` : ""}
    </div>
    ${secTitle(`${esc(finalStage.name)} 最終成績`)}
    <table><thead><tr><th>#</th><th>名前</th><th class="num">${wl ? "勝ち点" : "合計pt"}</th><th class="num">${wl ? "素点（同点時の順位）" : "素点"}</th>${wl ? '<th class="num">1着/4着</th>' : ""}</tr></thead><tbody>
    ${t.final_standings.map((r, i) => {
      const pl = [0, 0, 0, 0];
      finalGames.forEach((g) => { const k = g.seats.indexOf(r.id); if (k >= 0) pl[g.placement[k] - 1] += 1; });
      return `<tr data-id="${esc(r.id)}"><td class="rank-num">${i + 1}</td><td>${esc(r.name)}</td><td class="num">${P(r.points)}</td>
        <td class="num">${pt(r.raw ?? rawOf(r.id))}</td>${wl ? `<td class="num dim">${pl[0]}/${pl[3]}</td>` : ""}</tr>`;
    }).join("")}
    </tbody></table>
    ${wl ? `<div class="note">応龍戦は1着 +1・4着 −1 だけを数えます。勝ち点が並んだときは素点の合計で順位を決めます。</div>` : ""}
    ${secTitle(wl ? "勝ち点の推移" : "ポイント推移")}${lineChart(ids.map((id, k) => ({ name: nm(id), values: cum[id], color: SERIES[k % 4] })), finalGames.length)}
    <div class="legend">${ids.map((id, k) => `<span><i style="background:${SERIES[k % 4]}"></i>${esc(nm(id))}</span>`).join("")}</div>
    ${secTitle("半荘ごとの成績")}
    <div class="scroll-x"><table><thead><tr><th>半荘</th>${ids.map((id) => `<th class="num">${esc(nm(id))}</th>`).join("")}</tr></thead><tbody>
    ${finalGames.map((g) => `<tr data-go="game/${g.id}"><td>第${g.event.game}戦${g.has_kifu ? ' <span class="chip cyan">牌譜</span>' : ""}</td>
      ${ids.map((id) => { const i = g.seats.indexOf(id); return `<td class="num">${i >= 0 ? (wl ? `${g.placement[i]}着 <span class="dim small">${g.final_scores[i].toLocaleString()}</span>` : pt(g.points[i])) : "-"}</td>`; }).join("")}</tr>`).join("")}
    </tbody></table></div>`;
  const stages = t.stages.slice(0, -1);
  if (stages.length) {
    html += secTitle("予選・本戦") + stages.map((st) => `<div class="stage"><h4>${esc(st.name)}<span class="dim small">（各卓${st.games}半荘${st.byes?.length ? `・シード${st.byes.length}名` : ""}）</span></h4>
      <div class="stage-tables">${st.tables.map((tb, i) => `<div class="ttable"><div class="dim small">${i + 1}卓</div>
        ${tb.members.map((id) => `<div class="m ${tb.advanced.includes(id) ? "adv" : ""}"><span>${plink(id, nm(id))}</span><span>${P(tb.totals[id])}${wl && tb.raw ? ` <span class="dim small">(${sign(tb.raw[id])})</span>` : ""}</span></div>`).join("")}</div>`).join("")}
      </div></div>`).join("");
  }
  return html;
}

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  for (const m of [1, 2, 5, 10]) if (raw <= m * p) return m * p;
  return 10 * p;
}
function lineChart(series, n) {
  const W = 360, H = 170, L = 34, R = 8, T = 8, B = 20;
  const all = series.flatMap((s) => s.values);
  let lo = Math.min(0, ...all), hi = Math.max(0, ...all);
  if (hi - lo < 10) { hi += 5; lo -= 5; }
  const x = (i) => L + (i / Math.max(1, n)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const step = niceStep((hi - lo) / 4);
  let grid = "";
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${v}</text>`;
  }
  let xt = "";
  for (let i = 1; i <= n; i++) if (n <= 8 || i % 2 === 0 || i === n) xt += `<text x="${x(i)}" y="${H - 5}" text-anchor="middle">${i}</text>`;
  const lines = series.map((s) => `<polyline fill="none" stroke="${s.color}" stroke-width="1.8" stroke-linejoin="round" points="${s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}"/>
    <circle cx="${x(s.values.length - 1)}" cy="${y(s.values[s.values.length - 1])}" r="2.5" fill="${s.color}"/>`).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="累積ポイント推移">${grid}
    <line class="axis" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>${xt}${lines}</svg>`;
}

// ------------------------------------------------------------
// 結果：表彰
// ------------------------------------------------------------
function awardCategories(d) {
  const f2 = (v) => v.toFixed(2), p1 = (v) => (v * 100).toFixed(1) + "%";
  return [
    { key: "points", label: "獲得ポイント", fmt: (p) => pt(p.points), keyFn: (p) => p.points },
    { key: "tops", label: "トップ回数", fmt: (p) => `${p.tops}回（${p.games}半荘）`, keyFn: (p) => p.tops },
    { key: "avg_place", label: `平均着順（${d.min_games_for_rate}半荘以上）`, fmt: (p) => `${f2(p.avg_place)}（${p.games}半荘）`, keyFn: (p) => p.avg_place },
    { key: "win_rate", label: `和了率（${d.min_hands_for_rate}局以上）`, fmt: (p) => `${p1(p.win_rate)}（${p.wins}/${p.hands}局）`, keyFn: (p) => p.win_rate },
    { key: "dealin_rate", label: `放銃率の低さ（${d.min_hands_for_rate}局以上）`, fmt: (p) => `${p1(p.dealin_rate)}（${p.dealins}/${p.hands}局）`, keyFn: (p) => p.dealin_rate },
    { key: "max_value", label: "最高打点", fmt: (p) => `${p.max_value.toLocaleString()}点`, keyFn: (p) => p.max_value },
    { key: "yakuman", label: "役満", fmt: (p) => `${p.yakuman}回`, keyFn: (p) => p.yakuman },
    { key: "streak", label: "連続連対（2着以内）", fmt: (p) => `${p.best_streak}連続`, keyFn: (p) => p.best_streak },
    { key: "games", label: "対局数", fmt: (p) => `${p.games}半荘`, keyFn: (p) => p.games },
    { key: "elo_end", label: "季末レート", fmt: (p) => `${Math.round(p.elo)}`, keyFn: (p) => p.elo },
  ];
}
async function viewAwards(season) {
  const idx = await getIndex();
  if (!idx.current_season) return `<div class="empty">まだ記録がありません</div>`;
  const s = Math.min(Math.max(1, season || idx.current_season), idx.current_season);
  const d = await tryJSON(`awards/season_${s}.json`);
  let html = seasonNav(s, idx.current_season, "awards") + `<h3 class="view-title">第${s}季の表彰</h3>`;
  if (!d) return html + `<div class="empty">この季の表彰データがありません</div>`;
  html += `<div class="note">鳳凰戦とタイトル戦のすべての半荘が対象。</div>`;
  for (const c of awardCategories(d)) {
    const list = d[c.key] || [];
    html += `<h4 class="cat">${c.label}</h4>`;
    html += list.length
      ? collapsibleTable('<thead><tr><th>#</th><th>名前</th><th class="num">成績</th></tr></thead>', list,
        (p, rank) => `<tr data-id="${esc(p.id)}"><td class="rank-num">${rank}</td><td>${esc(p.name)}${nameTag(p.id)}</td><td class="num">${c.fmt(p)}</td></tr>`, 3, c.keyFn)
      : `<div class="dim small">該当者なし</div>`;
  }
  return html;
}

// ------------------------------------------------------------
// 結果：対局記録（名前で検索）
// ------------------------------------------------------------
let _matchQuery = "";
function matchLabel(ev) {
  if (ev.kind === "league") return `${ev.league}リーグ 第${ev.section}節`;
  return `${TITLE_EVENT_NAME[titleName(ev.title)] || ev.title} ${ev.stage}`;
}
async function viewMatches(season) {
  const idx = await getIndex();
  if (!idx.current_season) return `<div class="empty">まだ記録がありません</div>`;
  const s = Math.min(Math.max(1, season || idx.current_season), idx.current_season);
  afterRender(() => bindMatchSearch(s));
  return seasonNav(s, idx.current_season, "matches") + `
    <div style="margin-bottom:10px;"><input type="search" id="matches-search" placeholder="対局者名で検索..." value="${esc(_matchQuery)}" style="width:100%;"></div>
    <div id="matches-list" class="loading">読み込み中...</div>`;
}
async function bindMatchSearch(season) {
  const input = document.getElementById("matches-search");
  if (!input) return;
  const matches = await getJSON(`matches/season_${season}.json`);
  const draw = () => {
    const q = input.value.trim();
    _matchQuery = q;
    const hit = (q ? matches.filter((m) => m.names.some((n) => n.includes(q))) : matches).slice().reverse();
    const row = (m) => {
      const order = [0, 1, 2, 3].sort((a, b) => m.placement[a] - m.placement[b]);
      return `<div class="list-row" data-go="game/${m.id}"><span>${leagueTag(m.event.kind === "league" ? m.event.league : TITLE_SHORT[titleName(m.event.title)] || m.event.title)}${esc(matchLabel(m.event).replace(/^[A-D]リーグ /, ""))} 第${m.event.game}戦${m.has_kifu ? ' <span class="chip cyan">牌譜</span>' : ""}<br>
        <span class="dim small">${order.map((i) => `${m.placement[i]}着 ${esc(m.names[i])}`).join("　")}</span></span><span class="dim small">${m.id}</span></div>`;
    };
    const box = document.getElementById("matches-list");
    if (!box) return;
    box.className = "";
    box.innerHTML = hit.length
      ? `<div class="note">${hit.length}件${hit.length > 100 ? "（新しい順に100件まで表示）" : ""}</div>` + hit.slice(0, 100).map(row).join("")
      : `<div class="empty">${q ? "該当する対局が見つかりません" : "対局記録がありません"}</div>`;
  };
  let timer = null;
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(draw, 250); });
  draw();
}

// ------------------------------------------------------------
// 個体（雀士）ページ
// ------------------------------------------------------------
function radar(params) {
  const keys = Object.keys(STYLE_LABELS);
  const S = 240, C = S / 2, Rr = 82;
  const pts = (scale) => keys.map((k, i) => {
    const a = -Math.PI / 2 + (i / keys.length) * Math.PI * 2;
    const v = scale === null ? Math.min(12, params[k] || 0) / 12 : scale;
    return [C + Math.cos(a) * Rr * v, C + Math.sin(a) * Rr * v];
  });
  const rings = [0.25, 0.5, 0.75, 1].map((s) => `<polygon points="${pts(s).map((p) => p.join(",")).join(" ")}" fill="none" stroke="#182238"/>`).join("");
  const spokes = pts(1).map(([x, y]) => `<line x1="${C}" y1="${C}" x2="${x}" y2="${y}" stroke="#182238"/>`).join("");
  const labels = keys.map((k, i) => {
    const a = -Math.PI / 2 + (i / keys.length) * Math.PI * 2;
    return `<text x="${C + Math.cos(a) * (Rr + 20)}" y="${C + Math.sin(a) * (Rr + 20) + 4}" text-anchor="middle" fill="#dce6f0" font-size="10">${STYLE_LABELS[k]}</text>`;
  }).join("");
  return `<svg viewBox="0 0 ${S} ${S}" style="width:100%; max-width:280px;" role="img" aria-label="打ち筋">${rings}${spokes}
    <polygon points="${pts(null).map((p) => p.join(",")).join(" ")}" fill="rgba(79,240,255,0.25)" stroke="#4ff0ff" stroke-width="2"/>${labels}</svg>`;
}

// 成績詳細（試合数・トータル・素点・順位点・平均点数・最高点数・連対率・ラス回避率・飛び率・着順）
// r = { games, total, scoreSum, scoreMax, busts, pl: [1着,2着,3着,4着] }
function detailGrid(r) {
  const g = r.games;
  if (!g) return `<div class="dim small">対局記録なし</div>`;
  const raw = Math.round((r.scoreSum - 30000 * g) / 100) / 10;
  const uma = Math.round((r.total - raw) * 10) / 10;
  const pc = (a) => `${((a / g) * 100).toFixed(2)}<small>%</small>`;
  const cells = [
    ["試合数", `${g}<small>試合</small>`], ["トータル", pt(r.total)],
    ["素点", pt(raw)], ["順位点", pt(uma)],
    ["平均点数", `${Math.round(r.scoreSum / g).toLocaleString()}<small>点</small>`], ["最高点数", r.scoreMax == null ? "-" : `${r.scoreMax.toLocaleString()}<small>点</small>`],
    ["連対率", pc(r.pl[0] + r.pl[1])], ["ラス回避率", pc(g - r.pl[3])],
    ["飛び率", pc(r.busts)], ["平均着順", `${avgPlace(r.pl, g).toFixed(2)}<small>位</small>`],
    ...r.pl.map((c, i) => [`${"一二三四"[i]}位 <span class="dim">（${c}回）</span>`, pc(c)]),
  ];
  return `<div class="detail-grid">${cells.map(([l, v]) => `<div class="dg-cell"><span class="dg-label">${l}</span><span class="dg-value">${v}</span></div>`).join("")}</div>`;
}
// 通算成績：半荘単位（着順・素点・順位点）と局単位（和了・放銃・立直など）をひとつの表にまとめる
function careerStats(p) {
  const st = p.stats || {}, hands = st.hands || 0, g = p.games || 0, pl = p.placements || [0, 0, 0, 0];
  if (!g) return `<div class="dim small">対局記録なし</div>`;
  const num = (v) => (v ? Math.round(v).toLocaleString() : "-");
  const total = p.total_points || 0;
  const raw = st.score_sum ? Math.round((st.score_sum - 30000 * g) / 100) / 10 : null;
  const pc = (a, b = g) => (b ? `${((a / b) * 100).toFixed(2)}<small>%</small>` : "-");
  const cells = [
    ["試合数", `${g}<small>試合</small>`], ["トータル", pt(total)],
    ["素点", raw == null ? "-" : pt(raw)], ["順位点", raw == null ? "-" : pt(Math.round((total - raw) * 10) / 10)],
    ["平均点数", st.score_sum ? `${Math.round(st.score_sum / g).toLocaleString()}<small>点</small>` : "-"], ["最高点数", st.score_max == null ? "-" : `${st.score_max.toLocaleString()}<small>点</small>`],
    ["連対率", pc(pl[0] + pl[1])], ["ラス回避率", pc(g - pl[3])],
    ["飛び率", st.score_sum ? pc(st.busts || 0) : "-"], ["平均着順", `${avgPlace(pl, g).toFixed(2)}<small>位</small>`],
    ...pl.map((c, i) => [`${"一二三四"[i]}位 <span class="dim">（${c}回）</span>`, pc(c)]),
    ["和了率", pc(st.wins, hands)], ["放銃率", pc(st.dealins, hands)],
    ["平均打点", num(st.wins ? st.win_value / st.wins : 0)], ["平均放銃打点", num(st.dealins ? st.dealin_value / st.dealins : 0)],
    ["立直率", pc(st.riichi, hands)], ["ツモ率", pc(st.tsumo, st.wins)],
    ["流局時聴牌率", pc(st.draw_tenpai, st.draws)], ["最高打点", num(st.max_value)],
    ["役満", st.yakuman ? `${st.yakuman}<small>回</small>` : "-"], ["局数", `${hands.toLocaleString()}<small>局</small>`],
  ];
  return `<div class="detail-grid">${cells.map(([l, v]) => `<div class="dg-cell"><span class="dg-label">${l}</span><span class="dg-value">${v}</span></div>`).join("")}</div>
    <div class="note">和了率・放銃率・立直率などは、打った局数に対する割合。</div>`;
}

// 半荘ごとのレート推移（季の切れ目に区切り線）
function rateChart(p) {
  let trace = p.elo_trace || [];
  if (trace.length < 2 && (p.elo_history || []).length >= 2) trace = p.elo_history.map(([s, e], i) => [s, i + 1, e]);
  if (trace.length < 2) return `<div class="dim small">グラフ化するにはデータが足りません</div>`;
  const W = 360, H = 150, L = 36, R = 8, T = 8, B = 20;
  const xs = trace.map((t) => t[1]), ys = trace.map((t) => t[2]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let lo = Math.min(...ys, 1500), hi = Math.max(...ys, 1500);
  const pad = Math.max(10, (hi - lo) * 0.1); lo -= pad; hi += pad;
  const x = (v) => L + ((v - x0) / Math.max(1, x1 - x0)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const step = niceStep((hi - lo) / 4);
  let grid = "";
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    grid += `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 4}" y="${y(v) + 3}" text-anchor="end">${Math.round(v)}</text>`;
  }
  let seasons = "";
  trace.forEach((t, i) => {
    if (i === 0 || trace[i - 1][0] !== t[0]) {
      seasons += `<line class="axis" stroke-dasharray="3 3" x1="${x(t[1])}" x2="${x(t[1])}" y1="${T}" y2="${H - B}"/><text x="${x(t[1]) + 3}" y="${H - 6}">第${t[0]}季</text>`;
    }
  });
  const last = trace[trace.length - 1];
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="レート推移">${grid}
    <line class="axis" stroke-dasharray="2 4" x1="${L}" x2="${W - R}" y1="${y(1500)}" y2="${y(1500)}"/>${seasons}
    <polyline fill="none" stroke="var(--cyan)" stroke-width="1.6" stroke-linejoin="round" points="${trace.map((t) => `${x(t[1])},${y(t[2])}`).join(" ")}"/>
    <circle cx="${x(last[1])}" cy="${y(last[2])}" r="2.5" fill="var(--cyan)"/></svg>
    <div class="note">横軸は通算の半荘数（直近${trace.length}半荘）。点線は初期値1500。</div>`;
}

function lineageHtml(p, players) {
  const ancestors = [];
  let cur = p;
  while (cur && cur.parent_a_id && ancestors.length < 30) {
    cur = players._byId[cur.parent_a_id];
    if (cur) ancestors.push(cur);
  }
  const item = (a) => `${plink(a.id, a.display_name)}${a.retired ? '<span class="dim small">（引退）</span>' : ""}<span class="dim small" style="margin-left:6px;">レート ${Math.round(a.elo)}${a.retired ? "（引退時）" : ""}</span>`;
  let html = ancestors.length
    ? `<div style="padding:4px 0;">師匠：${item(ancestors[0])}</div>` + (ancestors.length > 1
      ? collapsible(`<div style="padding-left:10px; border-left:1px solid var(--navy-700);">${ancestors.slice(1).map((a) => `<div style="padding:3px 0;">${item(a)}</div>`).join("")}</div>`, `さらに遡る（${ancestors.length}代前まで）`)
      : "")
    : `<div style="padding:4px 0;" class="dim">師匠：なし（一門の開祖）</div>`;
  const disciples = players.filter((x) => x.parent_a_id === p.id);
  html += disciples.length
    ? `<div style="padding:4px 0;">弟子（${disciples.length}名）：<div style="margin-top:4px;">${disciples.map((c) => `<span style="display:inline-block; margin:2px 10px 2px 0;">${plink(c.id, c.display_name)}${c.retired ? '<span class="dim small">（引退）</span>' : ""}<span class="dim small" style="margin-left:4px;">最高 ${Math.round(c.peak_elo)}</span></span>`).join("")}</div></div>`
    : `<div style="padding:4px 0;" class="dim">弟子：まだいません</div>`;
  const founder = players._byId[p.clan_root_id];
  if (founder && founder.id !== p.id) html += `<div style="padding:4px 0;">一門：${esc(founder.display_name)}一門（第${p.generation}世代）</div>`;
  return `<div style="font-size:0.8rem;">${html}</div>`;
}

function opponentsHtml(p, players) {
  const rows = Object.entries(p.opponents || {}).map(([id, [n, above, below]]) => ({ id, n, above, below, name: players._byId[id]?.display_name || id }))
    .sort((a, b) => b.n - a.n || b.above - a.above);
  if (!rows.length) return `<div class="dim small">対局記録なし</div>`;
  const head = '<thead><tr><th>対戦相手</th><th class="num">同卓</th><th class="num">上位</th><th class="num">下位</th><th class="num">上位率</th></tr></thead>';
  return collapsibleTable(head, rows, (o) => `<tr data-id="${esc(o.id)}"><td>${esc(o.name)}${nameTag(o.id)}</td><td class="num">${o.n}</td>
    <td class="num" style="color:var(--cyan);">${o.above}</td><td class="num" style="color:var(--minus);">${o.below}</td><td class="num">${pct(o.above, o.above + o.below, 0)}</td></tr>`, 5)
    + `<div class="note">同じ半荘で自分が相手より上の着順だった回数（上位）と下だった回数（下位）。</div>`;
}

function titleRecordHtml(p, idx) {
  const won = idx.title_history.filter((h) => h.winner_id === p.id);
  const finals = idx.title_history.filter((h) => (h.final_standings || []).some((r) => r.id === p.id));
  const byTitle = (list) => TITLES.map((t) => [t, list.filter((h) => h.title === t).map((h) => h.season)]).filter(([, s]) => s.length);
  const wonHtml = won.length
    ? byTitle(won).map(([t, s]) => `<div style="padding:4px 0;">${esc(t)}：${s.length}期（${seasonRanges(s)}）</div>`).join("") + `<div style="padding:6px 0 0; color:var(--amber); font-size:0.78rem;">獲得合計：${won.length}期</div>`
    : `<div class="dim small">タイトル獲得歴なし</div>`;
  const finHtml = finals.length
    ? byTitle(finals).map(([t, s]) => `<div style="padding:4px 0;">${esc(TITLE_EVENT_NAME[t])}：${s.length}回（${seasonRanges(s)}）</div>`).join("") + `<div style="padding:6px 0 0; color:var(--amber); font-size:0.78rem;">決勝進出合計：${finals.length}回</div>`
    : `<div class="dim small">決勝進出の記録なし</div>`;
  return { wonHtml: `<div style="font-size:0.8rem;">${wonHtml}</div>`, finHtml: `<div style="font-size:0.8rem;">${finHtml}</div>` };
}

async function awardsOfHtml(id, idx) {
  const d = idx.current_season ? await tryJSON(`awards/season_${idx.current_season}.json`) : null;
  if (!d) return `<div class="dim small">記録なし</div>`;
  const rows = awardCategories(d).map((c) => {
    const list = d[c.key] || [];
    const i = list.findIndex((p) => p.id === id);
    const none = c.key === "yakuman" || c.key === "max_value" ? "-" : "対象外";
    const cell = i === -1 ? `<span class="dim">${none}</span>` : `<span class="elo-val">${competitionRanks(list, c.keyFn)[i]}位</span>（${c.fmt(list[i])}）`;
    return `<tr><td class="dim">${c.label}</td><td class="num">${cell}</td></tr>`;
  }).join("");
  return `<div class="note">第${d.season}季（最新季）。対象外は、その部門の条件（${d.min_games_for_rate}半荘以上・${d.min_hands_for_rate}局以上）に届いていないもの。</div><table><tbody>${rows}</tbody></table>`;
}

function careerHtml(p, idx) {
  const rows = [...(p.career || [])].reverse();
  if (!rows.length) return `<div class="dim small">記録なし</div>`;
  const items = rows.map((c) => {
    const won = idx.title_history.filter((h) => h.winner_id === p.id && h.season === c.season).map((h) => h.title);
    const rank = c.rank ? `${c.rank}位` : "リーグ免除";
    return `<div class="list-row" data-go="houou/${c.season}"><span>${movementMark(c.movement)}第${c.season}季 ${leagueTag(c.league)}${rank}${won.map((t) => ` <span class="chip gold">${esc(t)}</span>`).join("")}</span>
      <span>${pt(c.points)}pt <span class="dim small">季末 ${c.elo != null ? Math.round(c.elo) : "-"}</span></span></div>`;
  });
  const aCount = rows.filter((c) => c.league === "A").length;
  return (aCount ? `<div class="note">Aリーグ通算在籍：${aCount}季</div>` : "") + collapsibleList(items, 5, "季");
}

function recentHtml(p) {
  const games = [...(p.recent_games || [])].reverse();
  if (!games.length) return `<div class="dim small">対局記録なし</div>`;
  const items = games.map((g) => `<div class="list-row" data-go="game/${g.id}">
    <span>第${g.season}季 ${esc(g.label)}<br><span class="dim small">vs ${g.others.map(esc).join("・")}</span></span>
    <span style="text-align:right;"><b style="color:${g.placement === 1 ? "var(--amber)" : g.placement === 4 ? "var(--minus)" : "var(--text-main)"}">${g.placement}着</b> ${pt(g.points)}<br><span class="dim small">${g.score.toLocaleString()}点</span></span></div>`);
  return collapsibleList(items, 5, "局");
}

async function viewIndividual(id) {
  const [idx, players, p] = await Promise.all([getIndex(), getPlayers(), getDetail(id)]);
  if (!p) return `<div class="empty">雀士が見つかりません</div>`;
  const hasClan = players.some((x) => x.clan_root_id === p.clan_root_id && x.id !== p.id);
  const { wonHtml, finHtml } = titleRecordHtml(p, idx);
  let html = `<div class="back-link" data-go="leagues">← 一覧に戻る</div>
    <div style="text-align:center; margin-bottom:14px;">
      <div style="margin-bottom:6px;">${p.retired ? `<span class="dim small">（第${p.retired_season ?? "?"}季に引退）</span>` : leagueTag(p.league + "リーグ")}</div>
      <h3 style="margin:0; font-size:1.1rem; font-family:'Noto Sans JP',sans-serif;">${esc(p.display_name)}${nameTag(p.id)}</h3>
      <div class="dim" style="font-size:0.75rem; margin-top:2px;">通算${p.total_seasons}季　${ageOf(p)}歳${p.created ? `　<span class="chip cyan">投稿キャラ${p.creator ? `（${esc(p.creator)}）` : ""}</span>` : ""}</div>
      ${danBlock(p.id)}
      <div style="margin-top:6px;">レート <span class="elo-val" style="font-size:1.1rem;">${Math.round(p.elo)}</span>
        <span style="font-size:0.72rem; color:var(--amber); margin-left:8px;">最高 ${Math.round(p.peak_elo)}</span></div>
      <div style="margin-top:8px;"><button id="ind-fav-toggle" class="fav-toggle" data-fav="${esc(p.id)}">☆ お気に入りに追加</button></div>
      ${hasClan ? `<div style="margin-top:6px;"><span class="back-link" data-go="clans/${esc(p.clan_root_id)}" style="margin-bottom:0;">一門を見る →</span></div>` : ""}
      ${p.awakened_param ? `<div style="margin-top:8px;"><span class="awakened-badge">★ 覚醒：「${esc(STYLE_LABELS[p.awakened_param] || "技量")}」突破</span></div>` : ""}
    </div>
    <div style="display:flex; justify-content:center; margin-bottom:6px;">${radar(p.params || {})}</div>
    ${secTitle("系譜")}${lineageHtml(p, players)}
    ${secTitle("通算成績")}${careerStats(p)}
    ${secTitle("昇段履歴")}${danHistoryHtml(p, idx)}
    ${secTitle("対戦相手別成績")}${opponentsHtml(p, players)}
    ${secTitle("タイトル獲得歴")}${wonHtml}
    ${secTitle("タイトル戦決勝進出")}${finHtml}
    ${secTitle("レート推移")}${rateChart(p)}
    ${secTitle("今季の表彰")}<div id="ind-awards" class="dim small">読み込み中...</div>
    ${secTitle("シーズンごとの成績")}${careerHtml(p, idx)}
    ${secTitle("最近の対局")}${recentHtml(p)}`;
  afterRender(async () => {
    document.getElementById("ind-fav-toggle")?.addEventListener("click", () => toggleFavorite(p.id));
    applyFavorites();
    const box = document.getElementById("ind-awards");
    if (box) { box.className = ""; box.innerHTML = await awardsOfHtml(p.id, idx); }
  });
  return html;
}

// ------------------------------------------------------------
// 対局結果・牌譜ビューア
// ------------------------------------------------------------
async function findGame(id) {
  const matches = await getJSON(`matches/season_${id.split("-")[0]}.json`);
  return matches.find((m) => m.id === id);
}
function eventLabel(ev) {
  if (ev.kind === "league") return `第${ev.season}季 鳳凰戦 ${ev.league}リーグ 第${ev.section}節 ${ev.table}卓 第${ev.game}戦`;
  return `第${ev.season}季 ${TITLE_EVENT_NAME[titleName(ev.title)] || ev.title} ${ev.stage}${ev.table ? ` ${ev.table}卓` : ""} 第${ev.game}戦`;
}
function roundLine(r, names) {
  if (r.type === "draw" || r.type === "nagashi") {
    const t = r.tenpai.map((x, i) => (x ? esc(names[i]) : null)).filter(Boolean);
    return `${r.type === "nagashi" ? "流し満貫" : "流局"}<span class="dim small">（聴牌: ${t.length ? t.join("・") : "なし"}）</span>`;
  }
  const w = r.win;
  const how = r.type === "tsumo" ? "ツモ" : `ロン<span class="dim small">（放銃: ${esc(names[r.loser])}）</span>`;
  return `<b>${esc(names[r.winner])}</b> ${how} ${tile(r.tile, "", true)} <span class="chip gold">${w.label}</span>
    <div class="dim small">${w.yaku.map(([n, h]) => (h >= 13 ? n : `${n} ${h}翻`)).join("・")}</div>`;
}
async function viewGame(id) {
  const [g, idx] = await Promise.all([findGame(id), getIndex()]);
  if (!g) return `<div class="empty">対局が見つかりません</div>`;
  const rule = idx.rules?.[g.event.rule];
  const P = (v) => ptOf(v, rule?.uma_mode === "win_loss");
  const order = [0, 1, 2, 3].sort((a, b) => g.placement[a] - g.placement[b]);
  return `<div class="back-link" onclick="history.back()">← 戻る</div>
    <h3 class="view-title">対局結果</h3><div class="note">${esc(eventLabel(g.event))}</div>
    ${g.has_kifu ? `<div style="margin:8px 0;"><button class="btn primary" data-go="kifu/${g.id}">牌譜を再生する</button></div>` : ""}
    <table><thead><tr><th>着順</th><th>名前</th><th class="num">持ち点</th><th class="num">pt</th></tr></thead><tbody>
    ${order.map((i) => `<tr data-id="${esc(g.seats[i])}"><td class="rank-num">${g.placement[i]}</td><td>${esc(g.names[i])}</td><td class="num">${g.final_scores[i].toLocaleString()}</td><td class="num">${P(g.points[i])}</td></tr>`).join("")}
    </tbody></table>
    ${rule ? `<div class="note">ルール：${esc(rule.name)}</div>` : ""}
    ${secTitle("局の推移")}
    <div class="scroll-x"><table><thead><tr><th>局</th><th>結果</th>${g.names.map((n) => `<th class="num hide-sm">${esc(n)}</th>`).join("")}</tr></thead><tbody>
    ${g.rounds.map((r, i) => `<tr ${g.has_kifu ? `data-go="kifu/${g.id}/${i}"` : ""}><td style="white-space:nowrap;">${r.round}${r.honba ? `<br><span class="dim small">${r.honba}本場</span>` : ""}</td><td>${roundLine(r, g.names)}</td>
      ${r.deltas.map((d) => `<td class="num hide-sm">${d ? pt(d / 1000) : ""}</td>`).join("")}</tr>`).join("")}
    </tbody></table></div>`;
}

// 牌譜の状態を先頭から step 手目まで再現する
function replay(round, step) {
  const hands = round.haipai.map((h) => [...h]);
  const rivers = [[], [], [], []], melds = [[], [], [], []], riichi = [false, false, false, false];
  const doras = [round.dora];
  let pendingRiichi = -1, last = null, actor = round.oya, desc = "配牌";
  const remove = (arr, t, n = 1) => { for (let k = 0; k < n; k++) { const i = arr.indexOf(t); if (i >= 0) arr.splice(i, 1); } };
  const removeKind = (arr, kind, n) => { for (let k = 0; k < n; k++) { const i = arr.findIndex((x) => kindOf(x) === kind); if (i >= 0) arr.splice(i, 1); } };
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
      melds[a].push({ kind: { c: "chi", p: "pon", m: "minkan" }[code], tiles: [t, ...consumed].sort(byKind) });
      desc = `${{ c: "チー", p: "ポン", m: "大明槓" }[code]} ${tileName(t)}`;
    } else if (code === "a") {
      const kd = kindOf(t);
      removeKind(hands[a], kd, 4);
      melds[a].push({ kind: "ankan", tiles: t >= 34 ? [kd, t, kd, kd] : [kd, kd, kd, kd] });
      desc = `暗槓 ${tileName(kd)}`;
    } else if (code === "k") {
      remove(hands[a], t);
      const m = melds[a].find((x) => x.kind === "pon" && kindOf(x.tiles[0]) === kindOf(t));
      if (m) { m.kind = "kakan"; m.tiles = [...m.tiles, t].sort(byKind); }
      desc = `加槓 ${tileName(kindOf(t))}`;
    } else if (code === "n") { doras.push(t); desc = `槓ドラ ${tileName(t)} をめくる`; }
  }
  return { hands, rivers, melds, riichi, last, actor, desc, doras };
}
async function viewKifu(id, roundIdx) {
  const k = await getJSON(`kifu/${id}.json`);
  const state = { r: 0, step: 0, timer: null, view: 0 };
  if (roundIdx != null && k.rounds[roundIdx]) {
    // 記録集などから局を指定して開いたときは、その局の和了の場面を表示し、和了者を視点にする
    state.r = roundIdx;
    state.step = k.rounds[roundIdx].seq.length;
    const w = k.rounds[roundIdx].result.winner;
    if (w != null) state.view = w;
  }
  const winds = ["東", "南", "西", "北"];
  const draw = () => {
    const box = document.getElementById("kifu");
    if (!box) { clearInterval(state.timer); state.timer = null; return; }
    const round = k.rounds[state.r];
    const st = replay(round, state.step);
    const done = state.step >= round.seq.length;
    // 雀卓を上から見た正方形の盤面。各家の手牌・河を「自分の席が下」の向きで描き、席の位置まで回転させる
    // （下＝視点の家、右＝下家、上＝対面、左＝上家）
    const lastDiscard = st.last && st.last.kind === "discard" ? st.last : null;
    const remaining = 70 - round.seq.slice(0, state.step).filter((e) => e[0] === "t").length;
    const seats = [0, 1, 2, 3].map((s) => {
      const pos = (s - state.view + 4) % 4;
      const hand = [...st.hands[s]];
      let drawn = null;
      if (st.last && st.last.kind === "draw" && st.last.a === s) { drawn = st.last.t; hand.splice(hand.indexOf(drawn), 1); }
      hand.sort(byKind);
      const river = st.rivers[s].map((d, i) => tile(d.t, `${d.riichi ? "side" : ""} ${d.called ? "called" : ""} ${d.tg ? "tsumogiri" : ""} ${lastDiscard && lastDiscard.a === s && i === st.rivers[s].length - 1 ? "hi" : ""}`)).join("");
      const wind = winds[(s - round.oya + 4) % 4];
      return `<div class="mb-seat" style="transform:rotate(${-90 * pos}deg)">
        <div class="mb-label ${st.actor === s && !done ? "turn" : ""}"><span class="wind${wind === "東" ? " oya" : ""}">${wind}</span>
          <span class="nm">${esc(k.names[s])}</span><span class="sc">${round.scores[s].toLocaleString()}</span>${st.riichi[s] ? '<span class="stick"></span>' : ""}</div>
        <div class="mb-river">${river}</div>
        <div class="mb-hand"><span class="tiles">${hand.map((t) => tile(t)).join("")}${drawn !== null ? `<span class="gap"></span>${tile(drawn, "hi")}` : ""}</span>
          <span class="mb-melds">${st.melds[s].map((m) => meldHTML(m, false)).join("")}</span></div>
      </div>`;
    }).join("");
    const center = `<div class="mb-center"><div class="rd">${round.round}${round.honba ? `<small>${round.honba}本場</small>` : ""}</div>
      <div class="rest">残り<b>${Math.max(0, remaining)}</b>枚</div>
      <div class="dora"><span>ドラ表示</span>${st.doras.map((d) => tile(d)).join("")}</div>
      ${round.kyotaku ? `<div class="kyo">供託 ${round.kyotaku}</div>` : ""}</div>`;
    const res = done ? `<div class="result-box">${roundLine(round.result, k.names)}
        ${round.result.hand ? `<div style="margin-top:6px">${tilesHTML(round.result.hand.closed)}${round.result.hand.melds.map((m) => meldHTML(m)).join("")}</div>` : ""}
        <div class="dim small">${round.result.deltas.map((d, i) => `${esc(k.names[i])} ${d > 0 ? "+" : ""}${d}`).join(" / ")}</div></div>` : "";
    box.innerHTML = `<div class="row" style="margin-bottom:8px; font-size:0.8rem;">
        <select id="kround" aria-label="局">${k.rounds.map((r, i) => `<option value="${i}" ${i === state.r ? "selected" : ""}>${r.round}${r.honba ? ` ${r.honba}本場` : ""}</option>`).join("")}</select>
        <span class="spacer"></span><span class="dim">視点</span>
        <select id="kview" aria-label="視点">${k.names.map((n, i) => `<option value="${i}" ${i === state.view ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>
      <div class="mboard">${seats}${center}</div>${res}
      <div class="controls">
        <button data-k="prevround" ${state.r === 0 ? "disabled" : ""}>← 前の局</button>
        <button data-k="first" aria-label="局の最初へ">⏮</button><button data-k="prev" aria-label="1手戻る">◀</button>
        <button data-k="play">${state.timer ? "停止" : "再生"}</button>
        <button data-k="next" aria-label="1手進む">▶</button><button data-k="last" aria-label="局の最後へ">⏭</button>
        <button data-k="nextround" ${state.r === k.rounds.length - 1 ? "disabled" : ""}>次の局 →</button>
        <span class="status">${state.step}/${round.seq.length}手 ${done ? "終局" : `${esc(k.names[st.actor])}: ${st.desc}`}</span>
      </div>
      <div class="note">盤面の右半分をタップで1手進む、左半分で1手戻る。</div>`;
    // 盤面タップ：右半分で進む・左半分で戻る（局の端では前後の局へ移る）
    box.querySelector(".mboard").onclick = (e) => {
      const rect = e.currentTarget.getBoundingClientRect();
      act(e.clientX - rect.left >= rect.width / 2 ? "stepfwd" : "stepback");
    };
    document.getElementById("kround").onchange = (e) => { state.r = Number(e.target.value); state.step = 0; draw(); };
    document.getElementById("kview").onchange = (e) => { state.view = Number(e.target.value); draw(); };
    box.querySelectorAll(".controls button").forEach((b) => { b.onclick = () => act(b.dataset.k); });
  };
  const act = (kind) => {
    const round = k.rounds[state.r];
    if (kind === "first") state.step = 0;
    if (kind === "prev") state.step = Math.max(0, state.step - 1);
    if (kind === "next") state.step = Math.min(round.seq.length, state.step + 1);
    if (kind === "last") state.step = round.seq.length;
    if (kind === "nextround" && state.r < k.rounds.length - 1) { state.r += 1; state.step = 0; }
    if (kind === "prevround" && state.r > 0) { state.r -= 1; state.step = 0; }
    if (kind === "stepfwd") {
      if (state.step < round.seq.length) state.step += 1;
      else if (state.r < k.rounds.length - 1) { state.r += 1; state.step = 0; }
    }
    if (kind === "stepback") {
      if (state.step > 0) state.step -= 1;
      else if (state.r > 0) { state.r -= 1; state.step = k.rounds[state.r].seq.length; }
    }
    if (kind === "play") {
      if (state.timer) { clearInterval(state.timer); state.timer = null; }
      else state.timer = setInterval(() => {
        const rd = k.rounds[state.r];
        if (state.step < rd.seq.length) state.step += 1;
        else if (state.r < k.rounds.length - 1) { state.r += 1; state.step = 0; }
        else { clearInterval(state.timer); state.timer = null; }
        draw();
      }, 450);
    }
    draw();
  };
  afterRender(draw);
  return `<div class="back-link" data-go="game/${k.id}">← 対局結果へ</div>
    <h3 class="view-title">牌譜</h3><div class="note">${esc(eventLabel(k.event))}</div><div id="kifu"></div>`;
}

// ------------------------------------------------------------
// タイトル：現在の保持者・歴代
// ------------------------------------------------------------
async function viewTitles() {
  const idx = await getIndex();
  if (_titlesView === "current") {
    const s = idx.current_season;
    return `<h3 class="view-title">現在のタイトル保持者</h3>` + TITLES.map((t) => {
      const h = idx.titleholders?.[t];
      const count = h ? idx.title_history.filter((x) => x.title === t && x.winner_id === h.id).length : 0;
      return `<div class="title-card" ${h ? `data-id="${esc(h.id)}" role="link"` : ""}><h4>${t}</h4>
        <div class="holder">${h ? `${esc(h.name)}` : '<span class="dim">空位</span>'}</div>
        ${h ? `<div class="dim small">第${h.since}季から保持（${s - h.since + 1}期連続・通算${count}期）</div>` : ""}
        <div class="desc">${TITLE_DESC[t]}</div></div>`;
    }).join("");
  }
  const t = _titlesView;
  const hist = idx.title_history.filter((h) => h.title === t).sort((a, b) => b.season - a.season);
  if (!hist.length) return `<div class="empty">まだ開催されていません</div>`;
  const counts = {};
  [...hist].reverse().forEach((h) => { counts[h.winner_id] = (counts[h.winner_id] || 0) + 1; h._nth = counts[h.winner_id]; });
  const tab = Object.entries(RESULT_TITLE_TABS).find(([, v]) => v === t)[0];
  const rank = Object.entries(counts).map(([id, n]) => ({ id, n, name: hist.find((h) => h.winner_id === id).winner_name })).sort((a, b) => b.n - a.n);
  return `<h3 class="view-title">歴代${esc(t)}</h3><div class="note">${TITLE_DESC[t]}</div>
    <table><thead><tr><th>季</th><th>獲得者</th><th></th><th class="num">通算</th></tr></thead><tbody>
    ${hist.map((h) => `<tr data-go="${tab}/${h.season}"><td class="rank-num" style="width:4em;">第${h.season}季</td><td>${plink(h.winner_id, h.winner_name)}</td>
      <td>${h.event === "奪取" ? '<span class="chip gold">奪取</span>' : h.event === "防衛" ? '<span class="chip cyan">防衛</span>' : '<span class="chip">初代</span>'}</td><td class="num">${h._nth}期目</td></tr>`).join("")}
    </tbody></table>
    ${secTitle("獲得回数")}
    ${collapsibleTable("<thead><tr><th>#</th><th>名前</th><th class=\"num\">獲得</th></tr></thead>", rank,
      (r, n) => `<tr data-id="${esc(r.id)}"><td class="rank-num">${n}</td><td>${esc(r.name)}</td><td class="num">${r.n}期</td></tr>`, 10, (r) => r.n)}`;
}

// ------------------------------------------------------------
// 殿堂
// ------------------------------------------------------------
let _hofSort = { key: "peak_elo", dir: -1 };
const HOF_MIN_HANDS = 100;
async function viewHof() {
  const [idx, players] = await Promise.all([getIndex(), getPlayers()]);
  const tcount = {};
  idx.title_history.forEach((h) => { tcount[h.winner_id] = (tcount[h.winner_id] || 0) + 1; });
  if (_hofView === "ranking") {
    const rows = players.filter((p) => p.games).map((p) => {
      const st = p.stats || {}, h = st.hands || 0, ok = h >= HOF_MIN_HANDS;
      return {
        p, peak_elo: p.peak_elo, elo: p.elo, games: p.games, points: p.total_points,
        avg_place: avgPlace(p.placements, p.games), top_rate: p.placements[0] / p.games,
        win_rate: ok ? st.wins / h : null, dealin_rate: ok ? st.dealins / h : null,
        avg_value: st.wins ? st.win_value / st.wins : null, titles: tcount[p.id] || 0,
      };
    });
    const cols = [
      ["peak_elo", "最高", (r) => Math.round(r.peak_elo)], ["elo", "現在", (r) => Math.round(r.elo)],
      ["games", "半荘", (r) => r.games], ["points", "通算pt", (r) => pt(r.points)],
      ["avg_place", "平均着順", (r) => r.avg_place.toFixed(2), 1], ["top_rate", "トップ率", (r) => pct(r.top_rate, 1)],
      ["win_rate", "和了率", (r) => (r.win_rate == null ? "-" : pct(r.win_rate, 1))],
      ["dealin_rate", "放銃率", (r) => (r.dealin_rate == null ? "-" : pct(r.dealin_rate, 1)), 1],
      ["avg_value", "平均打点", (r) => (r.avg_value == null ? "-" : Math.round(r.avg_value).toLocaleString())],
      ["titles", "タイトル", (r) => (r.titles ? r.titles + "期" : "-")],
    ];
    const sort = _hofSort;
    rows.sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return (av - bv) * sort.dir;
    });
    const arrow = (k) => (k === sort.key ? (sort.dir === -1 ? " ▼" : " ▲") : "");
    const head = `<thead><tr><th>#</th><th>名前</th>${cols.map(([k, l]) => `<th class="num hof-sort" data-sort="${k}" style="cursor:pointer;">${l}${arrow(k)}</th>`).join("")}</tr></thead>`;
    afterRender(() => document.querySelectorAll("th.hof-sort").forEach((th) => th.addEventListener("click", () => {
      const k = th.dataset.sort, asc = cols.find((c) => c[0] === k)[3];
      _hofSort = _hofSort.key === k ? { key: k, dir: -_hofSort.dir } : { key: k, dir: asc ? 1 : -1 };
      render("hof");
    })));
    return `<div class="note">雀士ごとの通算成績の一覧。列見出しをクリックすると並び替え（和了率・放銃率は${HOF_MIN_HANDS}局以上が対象）。引退者も含みます。</div>` +
      collapsibleTable(head, rows, (r, n) => `<tr data-id="${esc(r.p.id)}"><td class="rank-num">${n}</td>
        <td style="white-space:nowrap;">${esc(r.p.display_name)}${nameTag(r.p.id)}${r.p.retired ? '<span class="dim small">（引退）</span>' : `<span class="dim small">（${r.p.league}）</span>`}</td>
        ${cols.map(([k, , f]) => `<td class="num"${k === sort.key ? ' style="color:var(--amber);"' : ""}>${f(r)}</td>`).join("")}</tr>`, 15);
  }
  if (_hofView === "records") return viewRecords(idx);
  if (_hofView === "retired") {
    const list = players.filter((p) => p.retired).sort((a, b) => (tcount[b.id] || 0) - (tcount[a.id] || 0) || b.peak_elo - a.peak_elo);
    if (!list.length) return `<div class="empty">まだ引退者はいません</div>`;
    return collapsibleTable('<thead><tr><th>名前</th><th class="num">最高</th><th>在籍</th><th class="num">タイトル</th></tr></thead>', list,
      (p) => `<tr data-id="${esc(p.id)}"><td>${esc(p.display_name)}<span class="dim small">（引退時${ageOf(p)}歳）</span></td><td class="num elo-val">${Math.round(p.peak_elo)}</td>
        <td class="dim small">${p.career?.[0]?.season ?? "-"}〜${p.retired_season ?? "-"}季</td><td class="num">${tcount[p.id] ? tcount[p.id] + "期" : "-"}</td></tr>`, 20);
  }
  const list = players.filter((p) => p.awakened_param).sort((a, b) => b.elo - a.elo);
  if (!list.length) return `<div class="empty">まだ覚醒した雀士はいません</div>`;
  return collapsibleTable('<thead><tr><th>名前</th><th class="num">レート</th><th>覚醒</th></tr></thead>', list,
    (p) => `<tr data-id="${esc(p.id)}"><td>${p.retired ? '<span class="dim small">引退</span> ' : leagueTag(p.league)}${esc(p.display_name)}</td>
      <td class="num elo-val">${Math.round(p.elo)}</td><td style="color:var(--amber);">★ ${esc(STYLE_LABELS[p.awakened_param] || "技量")}</td></tr>`, 15);
}

// 殿堂「記録」：サーバー（MySQL）で集計した一覧
const STAT_TABS = [["players", "個人成績"], ["yakuman", "役満"], ["big_hands", "高打点"], ["yaku", "役の出現率"], ["titles", "タイトル獲得"], ["scores", "半荘最高・最低"]];
const _rec = { tab: "players", season: "", sort: "win_rate" };
function gameRef(r) {
  const where = r.kind === "league" ? `${r.league}リーグ` : `${r.title}${r.stage ? " " + r.stage : ""}`;
  const kifu = +r.has_kifu && r.idx != null ? ` <span class="chip cyan link" data-go="kifu/${r.game_id}/${r.idx}">牌譜</span>` : "";
  return `<span class="link" data-go="game/${r.game_id}">第${r.season}季 ${esc(where)}</span>${kifu}`;
}
async function viewRecords(idx) {
  const seasonOpts = [`<option value="">通算</option>`];
  for (let x = idx.current_season; x >= 1; x--) seasonOpts.push(`<option value="${x}" ${String(x) === _rec.season ? "selected" : ""}>第${x}季</option>`);
  afterRender(() => {
    document.querySelectorAll("[data-rtab]").forEach((b) => b.addEventListener("click", () => { _rec.tab = b.dataset.rtab; render("hof"); }));
    document.getElementById("rec-season")?.addEventListener("change", (e) => { _rec.season = e.target.value; render("hof"); });
    document.querySelectorAll("[data-rsort]").forEach((b) => b.addEventListener("click", () => { _rec.sort = b.dataset.rsort; render("hof"); }));
  });
  let html = `<div class="note">記録集は、全半荘の局データをサーバーのデータベースで集計したもの。季ごとに絞り込めるほか、役満・高打点の一覧、役の出現率、タイトル獲得数、半荘の最高・最低得点が見られます。</div>
    <div class="pill-row">${STAT_TABS.map(([k, l]) => `<button class="btn${k === _rec.tab ? " active" : ""}" data-rtab="${k}">${l}</button>`).join("")}</div>
    ${_rec.tab !== "titles" ? `<div style="margin-bottom:10px;"><select id="rec-season" aria-label="季">${seasonOpts.join("")}</select></div>` : ""}`;
  const sq = _rec.season ? `&season=${_rec.season}` : "";
  try {
    if (_rec.tab === "players") {
      const minHands = _rec.season ? 30 : 100;
      const d = await api(`stats.php?type=players&min_hands=${minHands}${sq}`);
      const rows = d.rows.map((r) => {
        const games = +r.games;
        return { ...r, win_rate: r.wins / r.hands, dealin_rate: r.dealins / r.hands, riichi_rate: r.riichis / r.hands,
          tsumo_rate: r.wins ? r.tsumos / r.wins : 0, avg_place: games ? (+r.p1 + 2 * r.p2 + 3 * r.p3 + 4 * r.p4) / games : 0,
          top_rate: games ? r.p1 / games : 0, avg_value: +r.avg_value || 0, points: +r.points, games };
      });
      const cols = [["win_rate", "和了率", "%"], ["dealin_rate", "放銃率", "%", true], ["riichi_rate", "立直率", "%"],
        ["tsumo_rate", "ツモ率", "%"], ["avg_value", "平均打点", "n"], ["top_rate", "トップ率", "%"], ["avg_place", "平均着順", "f", true],
        ["points", "pt", "p"], ["games", "半荘", "n"]];
      const col = cols.find((c) => c[0] === _rec.sort) || cols[0];
      rows.sort((a, b) => (col[3] ? a[col[0]] - b[col[0]] : b[col[0]] - a[col[0]]));
      const fmt = (v, t) => (t === "%" ? (v * 100).toFixed(1) : t === "f" ? v.toFixed(2) : t === "p" ? pt(v) : Math.round(v).toLocaleString());
      html += `<div class="note">${minHands}局以上打った雀士が対象。列名をクリックで並べ替え（放銃率・平均着順は小さい順）。</div>` +
        collapsibleTable(`<thead><tr><th>#</th><th>名前</th>${cols.map(([k, l]) => `<th class="num" data-rsort="${k}" style="cursor:pointer;">${l}${k === col[0] ? " ▼" : ""}</th>`).join("")}</tr></thead>`,
          rows, (r, n) => `<tr data-id="${esc(r.id)}"><td class="rank-num">${n}</td><td style="white-space:nowrap;">${esc(r.name)} <span class="dim small">${r.league || "引退"}</span></td>
          ${cols.map(([k, , t]) => `<td class="num"${k === col[0] ? ' style="color:var(--amber);"' : ""}>${fmt(r[k], t)}</td>`).join("")}</tr>`, 20);
    } else if (_rec.tab === "yakuman" || _rec.tab === "big_hands") {
      const d = await api(`stats.php?type=${_rec.tab}${sq}`);
      html += d.rows.length ? collapsibleTable('<thead><tr><th>対局</th><th>和了者</th><th>役</th><th class="num">打点</th></tr></thead>', d.rows,
        (r) => `<tr><td class="small">${gameRef(r)}<br><span class="dim">${esc(r.round_name)}</span></td><td>${plink(r.winner_id, r.winner_name)}<br><span class="dim small">${r.type === "tsumo" ? "ツモ" : "放銃: " + esc(r.loser_name || "")}</span></td>
          <td class="small">${_rec.tab === "big_hands" ? `<span class="chip gold">${esc(r.label)}</span> ` : ""}<span class="dim">${esc(r.yaku)}</span></td><td class="num">${(+r.value).toLocaleString()}</td></tr>`, 20)
        : `<div class="empty">まだ記録がありません</div>`;
    } else if (_rec.tab === "yaku") {
      const d = await api(`stats.php?type=yaku${sq}`);
      const max = Math.max(1, ...d.rows.map((r) => +r.n));
      html += `<div class="note">和了 ${d.wins.toLocaleString()} 回のうち、各役が付いた割合（ドラを除く）。</div>
        <table><thead><tr><th>役</th><th class="num">回数</th><th class="num">出現率</th><th class="hide-sm" style="width:35%"></th></tr></thead><tbody>
        ${d.rows.map((r) => `<tr><td>${esc(r.name)}</td><td class="num">${(+r.n).toLocaleString()}</td><td class="num">${((r.n / Math.max(1, d.wins)) * 100).toFixed(2)}%</td>
          <td class="hide-sm"><div class="place-bar" style="margin:0;"><span style="width:${(r.n / max) * 100}%; background:var(--cyan-dim)"></span></div></td></tr>`).join("")}</tbody></table>`;
    } else if (_rec.tab === "titles") {
      const d = await api("stats.php?type=titles");
      const by = {};
      d.rows.forEach((r) => { (by[r.id] ||= { id: r.id, name: r.name, retired: +r.retired, total: 0, t: {} }); by[r.id].t[r.title] = +r.n; by[r.id].total += +r.n; });
      const list = Object.values(by).sort((a, b) => b.total - a.total);
      html += list.length ? collapsibleTable(`<thead><tr><th>#</th><th>名前</th>${TITLES.map((t) => `<th class="num">${TITLE_SHORT[t]}</th>`).join("")}<th class="num">合計</th></tr></thead>`, list,
        (p, n) => `<tr data-id="${esc(p.id)}"><td class="rank-num">${n}</td><td>${esc(p.name)}${p.retired ? '<span class="dim small">（引退）</span>' : ""}</td>
          ${TITLES.map((t) => `<td class="num">${p.t[t] || ""}</td>`).join("")}<td class="num"><b>${p.total}</b></td></tr>`, 20, (p) => p.total)
        : `<div class="empty">まだ記録がありません</div>`;
    } else {
      const d = await api(`stats.php?type=scores${sq}`);
      const tbl = (rows) => `<table><thead><tr><th>名前</th><th class="num">持ち点</th><th>対局</th></tr></thead><tbody>
        ${rows.map((r) => `<tr data-id="${esc(r.player_id)}"><td>${esc(r.name)}</td><td class="num">${(+r.final_score).toLocaleString()}</td><td class="small">${gameRef(r)}</td></tr>`).join("")}</tbody></table>`;
      html += `<h4 class="cat">最高得点</h4>${tbl(d.high)}<h4 class="cat">最低得点</h4>${tbl(d.low)}`;
    }
  } catch (e) {
    html += apiUnavailable(e);
  }
  return html;
}

// ------------------------------------------------------------
// 新人：キャラクリエイト・新人リーグ結果・歴代記録
// ------------------------------------------------------------
const PARAM_MIN = 0.5, PARAM_MAX = 10, PARAM_BUDGET = 45;
const PRESETS = { // mahjong_league/creation.py と同じ値
  balanced: ["バランス", { speed_weight: 6, dora_weight: 4, yakuhai_weight: 4, flush_weight: 3, tanyao_weight: 4, call_weight: 5, riichi_weight: 6, defense_weight: 7, push_weight: 6 }],
  attack: ["攻撃型", { speed_weight: 8, dora_weight: 6, yakuhai_weight: 4, flush_weight: 3, tanyao_weight: 4, call_weight: 4, riichi_weight: 9, defense_weight: 2, push_weight: 5 }],
  defense: ["守備型", { speed_weight: 6, dora_weight: 3, yakuhai_weight: 3, flush_weight: 2, tanyao_weight: 3, call_weight: 3, riichi_weight: 5, defense_weight: 10, push_weight: 10 }],
  caller: ["鳴き屋", { speed_weight: 7, dora_weight: 4, yakuhai_weight: 8, flush_weight: 5, tanyao_weight: 7, call_weight: 9, riichi_weight: 1, defense_weight: 2, push_weight: 2 }],
  flush: ["染め手", { speed_weight: 4, dora_weight: 4, yakuhai_weight: 6, flush_weight: 10, tanyao_weight: 1, call_weight: 8, riichi_weight: 3, defense_weight: 5, push_weight: 4 }],
};
const STATUS_LABEL = { pending: "受付済み", exported: "新人リーグ出場中", entered: "入門", not_selected: "落選" };

async function viewCreate() {
  const sliders = Object.entries(STYLE_LABELS).map(([k, l]) => `
    <label class="slider" title="${STYLE_DESC[k]}"><span>${l}</span><input type="range" min="${PARAM_MIN}" max="${PARAM_MAX}" step="0.5" name="${k}" value="${PRESETS.balanced[1][k]}"><output>${PRESETS.balanced[1][k]}</output></label>`).join("");
  afterRender(bindCreateForm);
  return `<h3 class="view-title">キャラクリエイト</h3>
    <div class="note">自分だけの雀士を投稿できます。投稿は次の新人リーグ（4人打ち・1人12半荘）に出場し、上位に入るとDリーグに入門します。入門時には既存の雀士が師匠に付きます。技量は入門時に決まり、若いうちに伸びます。</div>
    <div class="form-grid">
      <form id="create-form" autocomplete="off">
        <label>雀士名（12文字まで）<br><input name="name" maxlength="12" required style="width:100%"></label>
        <div style="height:8px"></div>
        <label>投稿者名（任意）<br><input name="creator" maxlength="12" style="width:100%"></label>
        <input name="website" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">
        ${secTitle("打ち筋")}
        <div class="pill-row">${Object.entries(PRESETS).map(([k, [l]]) => `<button type="button" class="btn${k === "balanced" ? " active" : ""}" data-preset="${k}">${l}</button>`).join("")}</div>
        <div class="sliders">${sliders}</div>
        <div class="note" style="margin-top:6px;">各項目の意味はページ上部の「？」（ルール）に載っています。</div>
        <div id="budget" class="note"></div>
        <button type="submit" class="btn primary">投稿する</button>
        <div id="create-msg" role="status" class="note"></div>
      </form>
      <div><div style="display:flex; justify-content:center;" id="create-radar"></div>
        <div class="note">合計は${PARAM_BUDGET}まで。超えた場合は比率を保ったまま自動で縮めます。</div></div>
    </div>
    ${secTitle("最近の投稿")}<div id="submissions" class="dim small">読み込み中...</div>`;
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
    form.querySelectorAll("[data-preset]").forEach((x) => x.classList.toggle("active", x === b));
    inputs.forEach((i) => { i.value = PRESETS[preset][1][i.name]; });
    update();
  }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("create-msg");
    const fd = new FormData(form);
    msg.textContent = "送信中...";
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
    box.className = "";
    box.innerHTML = d.submissions.length ? collapsibleTable('<thead><tr><th>受付</th><th>名前</th><th class="hide-sm">投稿者</th><th>状況</th></tr></thead>', d.submissions,
      (s) => `<tr ${s.player_id ? `data-id="${esc(s.player_id)}"` : ""}><td class="dim small">${esc(s.created_at)}</td><td>${esc(s.name)}</td><td class="hide-sm">${esc(s.creator || "")}</td>
        <td><span class="chip ${s.status === "entered" ? "cyan" : s.status === "not_selected" ? "" : "gold"}">${STATUS_LABEL[s.status] || s.status}</span>
        ${s.result_rank ? `<span class="dim small">新人リーグ${s.result_rank}位</span>` : ""}</td></tr>`, 10)
      : `<div class="dim small">まだ投稿はありません</div>`;
  } catch (e) {
    box.innerHTML = apiUnavailable(e);
  }
}

async function newcomerSeasons(idx) {
  const list = [];
  for (let s = 1; s <= idx.current_season + 1; s++) {
    const d = await tryJSON(`newcomer_league/for_season_${s}.json`);
    if (d) list.push(d);
  }
  return list;
}
async function viewNewcomer(season) {
  const [idx, players] = await Promise.all([getIndex(), getPlayers()]);
  const all = (await newcomerSeasons(idx)).filter((d) => d.standings.length);
  if (!all.length) return `<div class="empty">まだ新人リーグは開催されていません<br><span class="small">キャラクリエイトの投稿が集まると、次の季の前に開催されます</span></div>`;
  const seasons = all.map((d) => d.season);
  const s = seasons.includes(season) ? season : seasons[seasons.length - 1];
  const d = all.find((x) => x.season === s);
  const bySub = Object.fromEntries(players.filter((p) => p.submission_id).map((p) => [String(p.submission_id), p]));
  return seasonNav(s, seasons[seasons.length - 1], "newcomer", seasons[0]) + `
    <h3 class="view-title">新人リーグ（第${s}季入門分・入門枠${d.slots}名）</h3>
    <div class="note">4人打ちで1人12半荘。上位の投稿キャラが入門枠の数だけDリーグに入門します（自動生成の候補は入門しません）。</div>
    <div class="scroll-x"><table><thead><tr><th>#</th><th>名前</th><th class="num">pt</th><th class="num hide-sm">1/2/3/4着</th><th></th></tr></thead><tbody>
    ${d.standings.map((r) => {
      const p = r.submission_id != null && bySub[String(r.submission_id)];
      return `<tr class="${r.winner ? "zone-up" : ""}" ${p ? `data-id="${esc(p.id)}"` : ""}><td class="rank-num">${r.rank}</td>
        <td>${esc(r.name)} ${r.auto ? '<span class="dim small">（自動）</span>' : r.creator ? `<span class="dim small">by ${esc(r.creator)}</span>` : ""}</td>
        <td class="num">${pt(r.points)}</td><td class="num hide-sm dim">${r.placements.join("/")}</td><td>${r.winner ? '<span class="chip cyan">入門</span>' : ""}</td></tr>`;
    }).join("")}
    </tbody></table></div>`;
}
async function viewNewcomerHistory() {
  const [idx, players] = await Promise.all([getIndex(), getPlayers()]);
  const created = players.filter((p) => p.created).sort((a, b) => b.peak_elo - a.peak_elo);
  const all = await newcomerSeasons(idx);
  const held = all.filter((d) => d.standings.length);
  let html = `<h3 class="view-title">投稿キャラの歴代記録</h3>`;
  html += created.length
    ? collapsibleTable('<thead><tr><th>#</th><th>名前</th><th>所属</th><th class="num">最高</th><th class="num">タイトル</th></tr></thead>', created,
      (p, n) => `<tr data-id="${esc(p.id)}"><td class="rank-num">${n}</td><td>${esc(p.display_name)}${nameTag(p.id)}${p.creator ? ` <span class="dim small">by ${esc(p.creator)}</span>` : ""}</td>
        <td>${p.retired ? '<span class="dim small">引退</span>' : leagueTag(p.league)}</td><td class="num elo-val">${Math.round(p.peak_elo)}</td>
        <td class="num">${idx.title_history.filter((h) => h.winner_id === p.id).length || "-"}</td></tr>`, 15, (p) => p.peak_elo)
    : `<div class="dim small">まだ入門した投稿キャラはいません</div>`;
  html += secTitle("新人リーグの開催記録");
  html += held.length
    ? `<table><thead><tr><th>入門季</th><th class="num">参加</th><th class="num">入門枠</th><th>1位</th></tr></thead><tbody>
      ${held.reverse().map((d) => `<tr data-go="newcomer/${d.season}"><td>第${d.season}季</td><td class="num">${d.standings.filter((r) => !r.auto).length}名</td>
        <td class="num">${d.slots}名</td><td>${esc(d.standings[0].name)}${d.standings[0].auto ? '<span class="dim small">（自動）</span>' : ""}</td></tr>`).join("")}</tbody></table>`
    : `<div class="dim small">まだ開催されていません</div>`;
  return html;
}

// ------------------------------------------------------------
// ルール（？ボタンのモーダル）
// ------------------------------------------------------------
async function rulesHtml() {
  let rules = {};
  try { rules = (await getIndex()).rules || {}; } catch { /* 取得できなければタイトル別のルールは省略 */ }
  const sec = (t) => `<h3 style="font-size:0.85rem; color:var(--cyan); margin:14px 0 6px;">${t}</h3>`;
  return `<div style="font-size:0.8rem; line-height:1.7;">
    ${sec("タイトルごとのルール")}
    ${TITLES.map((t) => { const rr = rules[TITLE_RULE[t]]; return rr && rr.start_score ? `<div style="margin:10px 0 4px; color:var(--amber);">${TITLE_EVENT_NAME[t]}${t === "鳳凰位" ? "・鳳凰戦リーグ・新人リーグ" : ""}</div>${ruleSummary(rr)}` : ""; }).join("")}
    ${sec("共通ルール")}
    半荘戦。途中流局なし、飛びなし、ダブロンなし（頭ハネ）、喰いタン・後付けあり、役満の複合あり、
    責任払いあり（大三元・大四喜・四槓子）。第1季は全タイトルとも旧ルール（一発・裏・赤なし、定額ウマ +15/+5/−5/−15）で行われました。
    ${sec("鳳凰戦（リーグ）")}
    A12・B16・C20・D28名の通年リーグ。1節4半荘（A5節・B4節・C4節・D3節）の合計ポイントで順位を決めます。
    昇降級は A⇔B 2名、B⇔C 3名、C⇔D 4名。Aリーグ上位3名は鳳凰位決定戦へ。鳳凰位はAリーグ免除です。
    ${sec("タイトル戦")}
    ${TITLES.map((t) => `<div><b style="color:var(--amber);">${TITLE_EVENT_NAME[t]}</b>：${TITLE_DESC[t]}</div>`).join("")}
    <div class="dim small" style="margin-top:4px;">トーナメントでは保持者と上位リーグの雀士が後の回戦から登場します。前年の保持者は、挑戦者決定戦の勝者3名と決勝を打ちます。</div>
    ${sec("雀士")}
    打ち筋（9項目）と技量（判断の正確さ）を持ちます。若手は伸び、ベテランは緩やかに衰えます。
    新弟子は既存の雀士に弟子入りし、師匠の打ち筋を受け継ぎます（稀に新しい一門の開祖に）。
    ${sec("打ち筋の9項目")}
    <dl class="params-grid">${Object.entries(STYLE_DESC).map(([k, d]) => `<dt>${STYLE_LABELS[k]}</dt><dd>${d}</dd>`).join("")}</dl>
    <div class="dim small" style="margin-top:4px;">守備と押し返しは別の軸です。危険牌の打ちにくさ＝守備×危険度×「降りる度合い」で、降りる度合いは手が悪いほど大きく、押し返しが高いほど手が良いときに小さくなります。守備も押し返しも高いと「手が悪ければ降り、良ければ押す」打ち手になります。</div>
    ${sec("段位")}
    初段から始まり、九段が最高です。段位は下がりません。季ごとに昇段ポイントが入り、累計で昇段します。
    <dl class="params-grid">
      <dt>リーグ参加点</dt><dd>Aリーグ 6／Bリーグ 4／Cリーグ 2／Dリーグ 1</dd>
      <dt>順位ボーナス</dt><dd>Aリーグ：1位 +4、3位以内 +2　B〜Dリーグ：1位 +2、3位以内 +1</dd>
      <dt>タイトル</dt><dd>鳳凰位 +8、その他のタイトル +5（防衛も加算）</dd>
      <dt>昇段の目安</dt><dd>${DAN_NAMES.map((n, i) => `${n} ${DAN_THRESHOLDS[i]}点`).join("／")}。九段はタイトル獲得経験者のみ</dd>
    </dl>
    ${sec("引退")}
    ・70歳に達すると引退<br>
    ・Dリーグで2年連続マイナスなら引退<br>
    ・Dリーグに毎年最低2名の新人枠を確保するため、欠員が足りない場合はDリーグの下位から引退<br>
    ・いずれもタイトル保持中は猶予され、失冠するまで引退しない（降級は成績どおり）
  </div>`;
}

// ------------------------------------------------------------
// ルーター（#tab/param 形式。オセロ版と同じく戻る操作でスクロール位置を復元する）
// ------------------------------------------------------------
const scrollPositions = {};
const currentHash = () => location.hash.replace(/^#\/?/, "");
function navigateTo(hash) {
  scrollPositions[currentHash()] = window.scrollY;
  if (currentHash() === hash) { render(hash); return; }
  history.pushState({ hash }, "", "#" + hash);
  render(hash);
}
window.addEventListener("popstate", () => render(currentHash(), true));

let _renderSeq = 0;
// 描画後に行う処理（イベントの登録など）。ビューの中で登録し、HTMLを差し込んだ直後に実行する
let _afterRender = [];
const afterRender = (fn) => _afterRender.push(fn);
async function render(hash, isPopstate) {
  const parts = (hash || "").split("?")[0].split("/").map(decodeURIComponent);
  let [tab, param] = parts;
  if (tab === "player") tab = "individual"; // 旧URL互換
  const num = param ? parseInt(param, 10) : null;
  const views = {
    leagues: () => viewLeagues(),
    clans: () => (param ? viewClan(param) : viewClans()),
    houou: () => viewHouou(num),
    hououi: () => viewTitleResult("hououi", num), kirin: () => viewTitleResult("kirin", num),
    reiki: () => viewTitleResult("reiki", num), ouryu: () => viewTitleResult("ouryu", num),
    awards: () => viewAwards(num),
    matches: () => viewMatches(num),
    titles: () => viewTitles(),
    hof: () => viewHof(),
    individual: () => viewIndividual(param),
    game: () => viewGame(param),
    kifu: () => viewKifu(param, parts[2] != null && parts[2] !== "" ? parseInt(parts[2], 10) : null),
    newcomer_create: () => viewCreate(),
    newcomer: () => viewNewcomer(num),
    newcomer_history: () => viewNewcomerHistory(),
  };
  if (!views[tab] || ((tab === "individual" || tab === "game" || tab === "kifu") && !param)) tab = "leagues";
  showTab(tab);
  const seq = ++_renderSeq;
  _afterRender = [];
  const app = document.getElementById("app");
  const stay = tab === "titles" || tab === "hof"; // サブビュー切り替えでは読み込み表示を挟まない
  if (!stay) { app.className = "loading"; app.innerHTML = "読み込み中..."; }
  try {
    const [idx, allPlayers] = await Promise.all([getIndex(), getPlayers()]);
    setHolders(idx);
    setDans(allPlayers, idx);
    const html = await views[tab]();
    if (seq !== _renderSeq) return; // 読み込み中に別のページへ移った
    app.className = "";
    app.innerHTML = html;
    const hooks = _afterRender; _afterRender = [];
    hooks.forEach((fn) => fn());
  } catch (e) {
    if (seq !== _renderSeq) return;
    app.className = "empty";
    app.innerHTML = `読み込み失敗: ${esc(e.message)}`;
  }
  applyFavorites();
  if (isPopstate) {
    const target = scrollPositions[hash] || 0;
    let n = 0;
    const restore = () => { window.scrollTo(0, target); if (++n < 6) setTimeout(restore, 80); };
    restore();
  } else if (!stay) {
    window.scrollTo(0, 0);
  }
}
render(currentHash());
