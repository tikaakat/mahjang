import json
import os

from .individual import LeagueIndividual
from .league import LEAGUES


def _write(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=(",", ":") if indent is None else None)


def _read(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rosters(data_dir):
    d = _read(os.path.join(data_dir, "rosters.json"))
    if d is None:
        return None
    return {lg: [LeagueIndividual.from_dict(x) for x in d.get(lg, [])] for lg in LEAGUES}


def save_rosters(data_dir, rosters):
    _write(os.path.join(data_dir, "rosters.json"),
           {lg: [ind.to_dict() for ind in rosters[lg]] for lg in LEAGUES}, indent=1)


def load_season_state(data_dir):
    state = _read(os.path.join(data_dir, "season_state.json"), {})
    state.setdefault("current_season", 0)
    state.setdefault("titleholders", {})
    state.setdefault("title_history", [])
    state.setdefault("retired_archive", [])
    state.setdefault("name_registry", {})
    return state


def save_season_state(data_dir, state):
    _write(os.path.join(data_dir, "season_state.json"), state, indent=1)


def save_season_files(data_dir, season, standings, matches, titles, awards=None):
    """季ごとの成績・対局・タイトル戦。決勝の牌譜は別ファイル（サイトの牌譜ビューアが遅延読込する）"""
    slim = []
    for m in matches:
        kifu = m.pop("kifu", None)
        if kifu is not None:
            _write(os.path.join(data_dir, "kifu", f"{m['id']}.json"),
                   {"id": m["id"], "event": m["event"], "seats": m["seats"], "names": m["names"],
                    "final_scores": m["final_scores"], "placement": m["placement"], "points": m["points"],
                    "rounds": kifu})
            m["has_kifu"] = True
        slim.append(m)
    _write(os.path.join(data_dir, "standings", f"season_{season}.json"), standings)
    _write(os.path.join(data_dir, "matches", f"season_{season}.json"), slim)
    _write(os.path.join(data_dir, "titles", f"season_{season}.json"), titles)
    if awards is not None:
        _write(os.path.join(data_dir, "awards", f"season_{season}.json"), awards)


# 一覧（players.json）には載せず、雀士ごとの詳細ファイル（players/<id>.json）にだけ載せる項目
DETAIL_ONLY_KEYS = ("elo_trace", "recent_games", "opponents")


def save_site_index(data_dir, state, rosters):
    """フロントエンド用のまとめ（現役・引退の全雀士、タイトル保持者、季一覧）と雀士ごとの詳細"""
    players = [ind.to_dict() for lg in LEAGUES for ind in rosters[lg]] + state.get("retired_archive", [])
    summary = []
    for p in players:
        p = {k: v for k, v in p.items() if k != "age_multipliers"}
        _write(os.path.join(data_dir, "players", f"{p['id']}.json"), p)
        summary.append({k: v for k, v in p.items() if k not in DETAIL_ONLY_KEYS})
    _write(os.path.join(data_dir, "players.json"), summary)
    _write(os.path.join(data_dir, "index.json"), {
        "current_season": state["current_season"],
        "titleholders": state["titleholders"],
        "title_history": [{k: v for k, v in h.items() if k != "stages"} for h in state["title_history"]],
        "rules": state.get("rules"),
        "leagues": {lg: [ind.id for ind in rosters[lg]] for lg in LEAGUES},
    })


def backfill_history(data_dir, rosters, state):
    """
    通算の局成績（stats）・期末レート（elo_history）・半荘ごとのレート推移（elo_trace）・
    最近の対局と対戦相手別成績・季ごとの表彰を、保存済みの対局記録・成績表から作り直す。
    これらの項目を追加する前に行われた期の分を補うためのもので、何度実行しても同じ結果になる。
    """
    from .individual import empty_stats
    from .records import apply_match_index, compute_awards

    people = {ind.id: ind for lg in LEAGUES for ind in rosters[lg]}
    archived = {d["id"]: d for d in state.get("retired_archive", [])}
    stats = {pid: empty_stats() for pid in list(people) + list(archived)}
    history = {pid: [] for pid in stats}
    career_elo = {}

    # レートは対局記録の順に更新をやり直して、半荘ごとの推移を再現する
    from .elo import update_elo_table
    shadows = {}
    for pid in stats:
        sh = LeagueIndividual(pid, "D")
        sh.stats = stats[pid]
        shadows[pid] = sh
    seasons_played = {pid: 0 for pid in stats}
    people_all = {**archived, **people}
    for pid, ind in people_all.items():
        if isinstance(ind, dict):
            ind["recent_games"], ind["opponents"] = [], {}
        else:
            ind.recent_games, ind.opponents = [], {}
    career_movement = {}

    current = state.get("current_season", 0)
    for season in range(1, current + 1):
        matches = _read(os.path.join(data_dir, "matches", f"season_{season}.json"), [])
        for m in matches:
            if not all(pid in shadows for pid in m["seats"]):
                for seat, pid in enumerate(m["seats"]):
                    if pid in shadows:
                        shadows[pid].record_rounds(seat, m["rounds"])
                continue
            seats = [shadows[pid] for pid in m["seats"]]
            for sh in seats:
                sh.total_seasons = seasons_played[sh.id]
            update_elo_table(seats, m["placement"])
            for seat, sh in enumerate(seats):
                sh.record_rounds(seat, m["rounds"])
                sh.record_game(m["placement"][seat], m["points"][seat], season=season, score=m["final_scores"][seat])
        for pid in {pid for m in matches for pid in m["seats"] if pid in seasons_played}:
            seasons_played[pid] += 1
        apply_match_index(people_all, matches)
        final_elo, names = {}, {}
        for row in _read(os.path.join(data_dir, "standings", f"season_{season}.json"), []):
            final_elo[row["id"]], names[row["id"]] = row["elo"], row["name"]
            career_movement[(row["id"], season)] = row.get("movement")
            if row["id"] in history:
                history[row["id"]].append([season, row["elo"]])
                career_elo[(row["id"], season)] = row["elo"]
        _write(os.path.join(data_dir, "awards", f"season_{season}.json"),
               compute_awards(season, matches, names, final_elo))

    for pid, ind in people.items():
        ind.stats = stats[pid]
        ind.elo_history = history[pid]
        ind.elo_trace = shadows[pid].elo_trace
        for c in ind.career:
            c.setdefault("elo", career_elo.get((pid, c["season"])))
            c.setdefault("movement", career_movement.get((pid, c["season"])))
    for pid, d in archived.items():
        d["stats"] = stats[pid]
        d["elo_history"] = history[pid]
        d["elo_trace"] = shadows[pid].elo_trace
        for c in d.get("career", []):
            c.setdefault("elo", career_elo.get((pid, c["season"])))
            c.setdefault("movement", career_movement.get((pid, c["season"])))


def needs_backfill(rosters):
    return any(ind.games and (not ind.stats["hands"] or not ind.elo_trace or not ind.recent_games
                              or ind.stats.get("score_max") is None)
               for lg in LEAGUES for ind in rosters[lg])
