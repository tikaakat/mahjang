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


def save_season_files(data_dir, season, standings, matches, titles):
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


def save_site_index(data_dir, state, rosters):
    """フロントエンド用のまとめ（現役・引退の全雀士、タイトル保持者、季一覧）"""
    players = [ind.to_dict() for lg in LEAGUES for ind in rosters[lg]] + state.get("retired_archive", [])
    for p in players:
        p.pop("age_multipliers", None)
    _write(os.path.join(data_dir, "players.json"), players)
    _write(os.path.join(data_dir, "index.json"), {
        "current_season": state["current_season"],
        "titleholders": state["titleholders"],
        "title_history": [{k: v for k, v in h.items() if k != "stages"} for h in state["title_history"]],
        "rules": state.get("rules"),
        "leagues": {lg: [ind.id for ind in rosters[lg]] for lg in LEAGUES},
    })
