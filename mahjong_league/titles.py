"""
タイトル戦（日本プロ麻雀連盟のタイトル戦を参考にした4人打ち版）

- 鳳凰位  : 鳳凰戦Aリーグの上位3名＋前年鳳凰位による決定戦（半荘16回戦）。保持者はAリーグ免除
- 十段位  : レート（Elo）上位32名によるシード付きトーナメント（オセロの白虎戦に相当）
- 王位    : 全雀士参加の抽選トーナメント。上位リーグ・タイトル保持者ほど後の回戦から登場（玄武戦に相当）
- マスターズ: 全雀士参加の抽選トーナメント。各卓2半荘の合計で勝ち上がる（玄武戦に相当）

トーナメントは各卓4名・合計ポイント上位2名が勝ち上がる。前年の保持者は決勝シード。
保持者がいる場合は、ベスト4による「挑戦者決定戦」（上位3名通過）を経て、保持者を加えた4名で決勝を行う。
"""
import random

from .tables import play_session, play_sessions

TITLES = ("鳳凰位", "十段位", "王位", "マスターズ")

HOUOU_FINAL_GAMES = 16
FINAL_GAMES = {"十段位": 5, "王位": 5, "マスターズ": 4}
CHALLENGER_DECISION_GAMES = 3


def _tiebreak_rank(members, totals, prio):
    return sorted(members, key=lambda ind: (-totals[ind.id], prio.get(ind.id, 999), -ind.elo))


def _snake_tables(players, n_tables):
    """シード順に並んだ選手を蛇行配置で卓に割り振る（上位シード同士が同卓になりにくい）"""
    tables = [[] for _ in range(n_tables)]
    for i, p in enumerate(players):
        row, col = divmod(i, n_tables)
        tables[col if row % 2 == 0 else n_tables - 1 - col].append(p)
    return tables


def run_final(title, finalists, season, rng, games, prio, stage_name="決勝"):
    """決勝卓（4名で games 半荘の合計）。戻り値: (順位順リスト, 合計, 記録)"""
    totals, records = play_session(
        finalists, games, {"kind": "title", "title": title, "season": season, "stage": stage_name},
        rng=rng, keep_kifu=True,
    )
    ranked = _tiebreak_rank(finalists, totals, prio)
    return ranked, totals, records


def run_tournament(title, entrants, season, rng, mode="random", end_size=4, games_per_table=None):
    """
    entrants: 優先度順（シード上位が先頭）の参加者
    mode: "seeded"＝蛇行配置（レート順）/ "random"＝抽選
    戻り値: (勝ち残った end_size 名, ステージ記録, 対局記録)
    """
    prio = {ind.id: i for i, ind in enumerate(entrants)}
    current = list(entrants)
    stages = []
    records = []

    # 4×2^k の人数に揃えるための予備戦（シード下位だけが打つ。上位はシード＝不戦勝）
    target = end_size
    while target * 2 <= len(current):
        target *= 2
    stage_no = 1
    if len(current) > target:
        eliminate = len(current) - target
        n_tables = (eliminate + 1) // 2
        players = current[len(current) - 4 * n_tables:]
        byes = current[:len(current) - 4 * n_tables]
        advance_last = 3 if eliminate % 2 else 2
        adv, stage, recs = _play_stage(title, season, rng, players, n_tables, mode, prio, f"{stage_no}回戦",
                                       games=games_per_table or 1, advance_last=advance_last)
        stage["byes"] = [ind.id for ind in byes]
        stages.append(stage)
        records += recs
        current = byes + adv
        current.sort(key=lambda ind: prio[ind.id])
        stage_no += 1

    while len(current) > end_size:
        n_tables = len(current) // 4
        games = 1 if len(current) > 16 else 2
        if games_per_table:
            games = games_per_table
        name = {16: "準々決勝", 8: "準決勝"}.get(len(current), f"{stage_no}回戦")
        adv, stage, recs = _play_stage(title, season, rng, current, n_tables, mode, prio, name, games=games)
        stages.append(stage)
        records += recs
        current = sorted(adv, key=lambda ind: prio[ind.id])
        stage_no += 1
    return current, stages, records


def _play_stage(title, season, rng, players, n_tables, mode, prio, name, games, advance_last=2):
    if mode == "random":
        shuffled = list(players)
        rng.shuffle(shuffled)
        tables = [shuffled[i * 4:(i + 1) * 4] for i in range(n_tables)]
    else:
        tables = _snake_tables(players, n_tables)
    advancers = []
    stage = {"name": name, "games": games, "tables": []}
    records = []
    sessions = [(table, games, {"kind": "title", "title": title, "season": season, "stage": name, "table": t_idx + 1},
                 False) for t_idx, table in enumerate(tables)]
    for t_idx, (table, (totals, recs)) in enumerate(zip(tables, play_sessions(sessions, rng))):
        ranked = _tiebreak_rank(table, totals, prio)
        n_adv = advance_last if t_idx == len(tables) - 1 else 2
        advancers += ranked[:n_adv]
        stage["tables"].append({
            "members": [ind.id for ind in ranked],
            "totals": {ind.id: totals[ind.id] for ind in ranked},
            "advanced": [ind.id for ind in ranked[:n_adv]],
        })
        records += recs
    return advancers, stage, records


def contest_title(title, entrants, holder, season, rng, mode="random", games_per_table=None):
    """
    トーナメント → （保持者がいれば挑戦者決定戦）→ 決勝。
    戻り値: 結果 dict（history 用）と 対局記録
    """
    prio = {ind.id: i for i, ind in enumerate(entrants)}
    best4, stages, records = run_tournament(title, entrants, season, rng, mode=mode,
                                            games_per_table=games_per_table)
    if holder is not None:
        ranked, totals, recs = run_final(title, best4, season, rng, CHALLENGER_DECISION_GAMES, prio,
                                         stage_name="挑戦者決定戦")
        stages.append({"name": "挑戦者決定戦", "games": CHALLENGER_DECISION_GAMES, "tables": [{
            "members": [ind.id for ind in ranked], "totals": totals,
            "advanced": [ind.id for ind in ranked[:3]],
        }]})
        records += recs
        finalists = [holder] + ranked[:3]
        prio[holder.id] = -1
    else:
        finalists = best4
    ranked, totals, recs = run_final(title, finalists, season, rng, FINAL_GAMES[title], prio)
    records += recs
    stages.append({"name": "決勝", "games": FINAL_GAMES[title], "tables": [{
        "members": [ind.id for ind in ranked], "totals": totals, "advanced": [ranked[0].id],
    }]})
    return _result(title, season, holder, ranked, totals, stages), records


def run_houou_final(a_ranked, holder, season, rng):
    """鳳凰位決定戦：Aリーグ上位3名＋前年鳳凰位（空位ならAリーグ上位4名）で半荘16回戦"""
    challengers = a_ranked[:3] if holder is not None else a_ranked[:4]
    finalists = ([holder] if holder is not None else []) + challengers
    prio = {ind.id: i for i, ind in enumerate(finalists)}
    ranked, totals, records = run_final("鳳凰位", finalists, season, rng, HOUOU_FINAL_GAMES, prio,
                                        stage_name="鳳凰位決定戦")
    stages = [{"name": "鳳凰位決定戦", "games": HOUOU_FINAL_GAMES, "tables": [{
        "members": [ind.id for ind in ranked], "totals": totals, "advanced": [ranked[0].id],
    }]}]
    return _result("鳳凰位", season, holder, ranked, totals, stages), records


def _result(title, season, holder, ranked, totals, stages):
    winner = ranked[0]
    if holder is None:
        event = "初代"
    elif winner.id == holder.id:
        event = "防衛"
    else:
        event = "奪取"
    return {
        "title": title, "season": season, "event": event,
        "winner_id": winner.id, "winner_name": winner.display_name,
        "previous_id": holder.id if holder else None,
        "previous_name": holder.display_name if holder else None,
        "final_standings": [{"id": ind.id, "name": ind.display_name, "points": totals[ind.id]} for ind in ranked],
        "stages": stages,
    }


def jyudan_entrants(all_members, holder_id, top_n=32):
    """十段戦：レート上位 top_n 名（保持者を除く）。シード順＝レート順"""
    pool = [ind for ind in all_members if ind.id != holder_id]
    return sorted(pool, key=lambda ind: -ind.elo)[:top_n]


def open_entrants(all_members, holder_id, titleholder_ids, league_rank):
    """王位戦・マスターズ：全雀士。優先度＝タイトル保持者 → 所属リーグ・順位 → レート"""
    pool = [ind for ind in all_members if ind.id != holder_id]
    return sorted(pool, key=lambda ind: (0 if ind.id in titleholder_ids else 1,
                                         league_rank.get(ind.id, (9, 999)), -ind.elo))
