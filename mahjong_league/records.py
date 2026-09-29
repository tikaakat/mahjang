"""
対局記録から、サイト表示用の集計を作る。
  - 個体ごとの「最近の対局」「対戦相手別成績」（同卓した相手ごとに、自分が上位・下位だった回数）
  - 季ごとの表彰（半荘数・トップ数・平均着順・獲得ポイント・和了率・放銃率・最高打点・役満・連続連対・期末レート）
"""
RECENT_GAMES_MAX = 30
MIN_GAMES_FOR_RATE = 12     # 平均着順の対象（半荘数。Dリーグの年間半荘数と同じ）
MIN_HANDS_FOR_RATE = 100    # 和了率・放銃率の対象（局数）


def event_label(ev):
    if ev.get("kind") == "league":
        return f"{ev.get('league')}リーグ 第{ev.get('section')}節"
    if ev.get("kind") == "title":
        return f"{ev.get('title')} {ev.get('stage')}"
    return "新人リーグ"


def apply_match_index(people, matches):
    """people: {id: 個体（LeagueIndividual か dict）}。matches は対局順・id 付き"""
    for m in matches:
        label = event_label(m["event"])
        season = m["event"].get("season")
        for seat, pid in enumerate(m["seats"]):
            ind = people.get(pid)
            if ind is None:
                continue
            recent = _get(ind, "recent_games")
            recent.append({"id": m["id"], "season": season, "label": label, "placement": m["placement"][seat],
                           "points": m["points"][seat], "score": m["final_scores"][seat],
                           "others": [n for i, n in enumerate(m["names"]) if i != seat]})
            del recent[:-RECENT_GAMES_MAX]
            opp = _get(ind, "opponents", {})
            for other_seat, other_id in enumerate(m["seats"]):
                if other_seat == seat:
                    continue
                rec = opp.setdefault(other_id, [0, 0, 0])   # [同卓数, 自分が上位, 自分が下位]
                rec[0] += 1
                if m["placement"][seat] < m["placement"][other_seat]:
                    rec[1] += 1
                elif m["placement"][seat] > m["placement"][other_seat]:
                    rec[2] += 1


def _get(ind, key, default=None):
    if isinstance(ind, dict):
        return ind.setdefault(key, [] if default is None else default)
    if not hasattr(ind, key) or getattr(ind, key) is None:
        setattr(ind, key, [] if default is None else default)
    return getattr(ind, key)


def compute_awards(season, matches, names, final_elo):
    """その季の全対局（リーグ戦・タイトル戦）から表彰を作る。final_elo: {id: 期末レート}"""
    agg = {}
    for m in matches:
        for seat, pid in enumerate(m["seats"]):
            a = agg.setdefault(pid, {"id": pid, "name": m["names"][seat], "games": 0, "tops": 0, "lasts": 0,
                                     "place_sum": 0, "points": 0.0, "hands": 0, "wins": 0, "dealins": 0,
                                     "max_value": 0, "yakuman": 0, "streak": 0, "best_streak": 0})
            p = m["placement"][seat]
            a["games"] += 1
            a["place_sum"] += p
            a["points"] = round(a["points"] + m["points"][seat], 1)
            a["tops"] += p == 1
            a["lasts"] += p == 4
            a["streak"] = a["streak"] + 1 if p <= 2 else 0
            a["best_streak"] = max(a["best_streak"], a["streak"])
            for r in m["rounds"]:
                a["hands"] += 1
                win = r.get("win")
                if r.get("winner") == seat and win:
                    a["wins"] += 1
                    a["max_value"] = max(a["max_value"], win.get("value", 0))
                    a["yakuman"] += 1 if win.get("yakuman") else 0
                if r.get("loser") == seat and win:
                    a["dealins"] += 1
    people = list(agg.values())
    for a in people:
        a["avg_place"] = round(a["place_sum"] / a["games"], 3) if a["games"] else None
        a["win_rate"] = round(a["wins"] / a["hands"], 4) if a["hands"] else None
        a["dealin_rate"] = round(a["dealins"] / a["hands"], 4) if a["hands"] else None
        a["elo"] = final_elo.get(a["id"])
        a["name"] = names.get(a["id"], a["name"])
        a.pop("streak", None)
        a.pop("place_sum", None)

    def top(key, reverse=True, cond=lambda a: True):
        pool = [a for a in people if cond(a) and a.get(key) is not None]
        pool.sort(key=lambda a: (a[key], a["games"]), reverse=reverse)
        return pool

    return {
        "season": season,
        "min_games_for_rate": MIN_GAMES_FOR_RATE,
        "min_hands_for_rate": MIN_HANDS_FOR_RATE,
        "games": top("games"),
        "tops": top("tops"),
        "points": top("points"),
        "avg_place": top("avg_place", reverse=False, cond=lambda a: a["games"] >= MIN_GAMES_FOR_RATE),
        "win_rate": top("win_rate", cond=lambda a: a["hands"] >= MIN_HANDS_FOR_RATE),
        "dealin_rate": top("dealin_rate", reverse=False, cond=lambda a: a["hands"] >= MIN_HANDS_FOR_RATE),
        "max_value": top("max_value", cond=lambda a: a["max_value"] > 0),
        "yakuman": top("yakuman", cond=lambda a: a["yakuman"] > 0),
        "streak": top("best_streak"),
        "elo_end": top("elo"),
    }
