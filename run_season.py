"""
MAHJONG LEAGUE：1シーズン（1年）分を進める。

  1. Dリーグの欠員を新弟子で補充（師弟制度）
  2. 年齢バフの再抽選
  3. 鳳凰戦（A〜Dリーグ）…鳳凰位保持者はAリーグ免除
  4. タイトル戦：鳳凰位決定戦・十段戦・王位戦・マスターズ
  5. 昇降級・引退・成長、保存
"""
import argparse
import json
import os
import random

from mahjong_sim.ai import PARAM_KEYS
from mahjong_sim.rules import RENMEI
from mahjong_league.buffs import roll_age_multipliers
from mahjong_league.league import (
    LEAGUES, bootstrap_rosters, run_league, relegate_and_retire, recruit_d_league, develop, SECTIONS,
)
from mahjong_league.names import NameRegistry
from mahjong_league.titles import (
    TITLES, run_houou_final, contest_title, jyudan_entrants, open_entrants,
)
from mahjong_league.io_utils import (
    load_rosters, save_rosters, load_season_state, save_season_state, save_season_files, save_site_index,
    backfill_history, needs_backfill,
)


def _holder(state, title, by_id):
    info = state["titleholders"].get(title)
    if not info:
        return None
    ind = by_id.get(info["id"])
    if ind is None:
        print(f"  ※ {title}保持者（{info.get('name')}）が現役にいないため空位として扱います")
    return ind


def run_one_season(rosters, state, rng, sections_scale=1.0, created_requests=None):
    season = state["current_season"] + 1
    print(f"=== 第{season}期 ===", flush=True)
    titleholder_ids = {v["id"] for v in state["titleholders"].values() if v}

    registry = NameRegistry.from_dict(state.get("name_registry", {}))
    rosters, newcomers = recruit_d_league(rosters, season, registry, titleholder_ids,
                                          created_requests=created_requests)
    state["name_registry"] = registry.to_dict()
    if newcomers:
        print(f"  新弟子 {len(newcomers)}名がDリーグに入門")

    for lg in LEAGUES:
        for ind in rosters[lg]:
            ind.age_multipliers = roll_age_multipliers(ind.age, PARAM_KEYS)

    by_id = {ind.id: ind for lg in LEAGUES for ind in rosters[lg]}
    matches = []

    # ---------------- 鳳凰戦 ----------------
    houou_holder = _holder(state, "鳳凰位", by_id)
    exempt = {}
    if houou_holder is not None:
        exempt = {houou_holder.league: [houou_holder]}
    ranked, league_stats = {}, {}
    for lg in LEAGUES:
        members = [ind for ind in rosters[lg] if ind is not houou_holder]
        sections = max(1, round(SECTIONS[lg] * sections_scale))
        print(f"  --- 鳳凰戦 {lg}リーグ（{len(members)}名・{sections}節） ---", flush=True)
        ranked[lg], recs, stats = run_league(members, lg, season, rng, sections=sections)
        league_stats.update(stats)
        matches += recs
        top = ranked[lg][0]
        print(f"  {lg}リーグ1位: {top.display_name}（{stats[top.id]['points']:+.1f}pt）")

    # ---------------- タイトル戦 ----------------
    titles = []
    res, recs = run_houou_final(ranked["A"], houou_holder, season, rng)
    titles.append(res); matches += recs

    league_rank = {ind.id: (LEAGUES.index(lg), r) for lg in LEAGUES for r, ind in enumerate(ranked[lg])}
    if houou_holder is not None:
        league_rank[houou_holder.id] = (0, -1)
    all_members = list(by_id.values())

    holder = _holder(state, "十段位", by_id)
    res, recs = contest_title("十段位", jyudan_entrants(all_members, holder and holder.id), holder, season, rng,
                              mode="seeded")
    titles.append(res); matches += recs

    holder = _holder(state, "王位", by_id)
    res, recs = contest_title("王位", open_entrants(all_members, holder and holder.id, titleholder_ids, league_rank),
                              holder, season, rng, mode="random")
    titles.append(res); matches += recs

    holder = _holder(state, "マスターズ", by_id)
    res, recs = contest_title("マスターズ", open_entrants(all_members, holder and holder.id, titleholder_ids, league_rank),
                              holder, season, rng, mode="random", games_per_table=2)
    titles.append(res); matches += recs

    for t in titles:
        prev = state["titleholders"].get(t["title"])
        since = prev["since"] if prev and prev["id"] == t["winner_id"] else season
        state["titleholders"][t["title"]] = {"id": t["winner_id"], "name": t["winner_name"], "since": since}
        tag = {"初代": "初代", "防衛": "防衛", "奪取": "奪取！"}[t["event"]]
        print(f"  ★ {t['title']}: {t['winner_name']}（{tag}） 決勝 " +
              " / ".join(f"{s['name']} {s['points']:+.1f}" for s in t["final_standings"]))
    state["title_history"] += [{k: v for k, v in t.items() if k != "stages"} for t in titles]

    for i, m in enumerate(matches, 1):
        m["id"] = f"{season}-{i:04d}"

    # ---------------- 成績表・昇降級 ----------------
    new_titleholder_ids = {v["id"] for v in state["titleholders"].values() if v}
    next_exempt = {state["titleholders"]["鳳凰位"]["id"]}
    pre_league = {ind.id: ind.league for ind in all_members}
    new_rosters, retired = relegate_and_retire(ranked, exempt, new_titleholder_ids, exempt_next_ids=next_exempt)
    post_league = {ind.id: lg for lg in LEAGUES for ind in new_rosters[lg]}
    retired_ids = {ind.id for ind in retired}

    standings = []
    for lg in LEAGUES:
        rows = [(None, houou_holder)] if (houou_holder is not None and houou_holder.league == lg) else []
        rows += list(enumerate(ranked[lg], 1))
        for rank, ind in rows:
            st = league_stats.get(ind.id, {"points": 0.0, "games": 0, "placements": [0, 0, 0, 0]})
            if ind.id in retired_ids:
                movement = "retired"
            elif post_league.get(ind.id) != pre_league[ind.id]:
                movement = "promoted" if LEAGUES.index(post_league[ind.id]) < LEAGUES.index(pre_league[ind.id]) else "relegated"
            else:
                movement = "stay"
            standings.append({
                "season": season, "league": lg, "rank": rank, "id": ind.id, "name": ind.display_name,
                "points": st["points"], "games": st["games"], "placements": st["placements"],
                "elo": round(ind.elo, 1), "movement": movement, "exempt": rank is None,
                "new": ind.total_seasons == 0,
            })
            ind.career.append({"season": season, "league": lg, "rank": rank, "points": st["points"],
                               "elo": round(ind.elo, 1)})

    for ind in all_members:
        ind.elo_history.append([season, round(ind.elo, 1)])
    for ind in retired:
        ind.retired_season = season
    for lg in LEAGUES:
        for ind in new_rosters[lg]:
            develop(ind)
    state["retired_archive"] += [dict(ind.to_dict(), retired_season=season) for ind in retired]
    if retired:
        print(f"  引退: {', '.join(ind.display_name for ind in retired)}")
    state["current_season"] = season
    return new_rosters, standings, matches, titles


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--seasons", type=int, default=1)
    parser.add_argument("--sections-scale", type=float, default=1.0,
                        help="リーグの節数の倍率（動作確認用に 0.25 などで短縮できる）")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    if args.seed is not None:
        random.seed(args.seed)

    state = load_season_state(args.data_dir)
    state["rules"] = RENMEI.to_dict()
    rosters = load_rosters(args.data_dir)
    if rosters is None:
        print("初回起動：ロスターを新規作成します")
        registry = NameRegistry.from_dict(state.get("name_registry", {}))
        rosters = bootstrap_rosters(registry)
        state["name_registry"] = registry.to_dict()

    if needs_backfill(rosters):
        print("通算の局成績・レート推移を過去の対局記録から作り直します")
        backfill_history(args.data_dir, rosters, state)

    # 新人リーグ（run_newcomer_league.py）の勝者。最初に処理する期にだけ適用し、読んだら消す
    winners_path = os.path.join(args.data_dir, "newcomer_winners.json")
    created_requests = None
    if os.path.exists(winners_path):
        with open(winners_path, encoding="utf-8") as f:
            created_requests = json.load(f) or None
        os.remove(winners_path)

    for i in range(args.seasons):
        rosters, standings, matches, titles = run_one_season(
            rosters, state, rng, args.sections_scale, created_requests=created_requests if i == 0 else None)
        save_rosters(args.data_dir, rosters)
        save_season_files(args.data_dir, state["current_season"], standings, matches, titles)
        save_season_state(args.data_dir, state)
        save_site_index(args.data_dir, state, rosters)
        print(f"第{state['current_season']}期 完了・保存しました\n", flush=True)


if __name__ == "__main__":
    main()
