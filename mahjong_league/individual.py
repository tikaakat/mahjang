import random

from mahjong_sim.ai import PARAM_KEYS

STYLE_KEYS = PARAM_KEYS  # 打ち筋の個性（牌効率・ドラ・役牌・染め手・タンヤオ・鳴き・リーチ・守備・押し）


ELO_TRACE_MAX = 400

# 入門時の年齢。オセロ版より幅を広げている（麻雀は年齢層が幅広い）
NEWCOMER_AGE_RANGE = (25, 35)            # 通常の新人（新弟子・投稿キャラ）
AWAKENED_INITIAL_AGE_RANGE = (20, 35)    # 覚醒して入門した新人


def roll_initial_age(awakened=False):
    return random.randint(*(AWAKENED_INITIAL_AGE_RANGE if awakened else NEWCOMER_AGE_RANGE))


def empty_stats():
    return {"hands": 0, "wins": 0, "tsumo": 0, "dealins": 0, "riichi": 0, "draws": 0, "draw_tenpai": 0,
            "win_value": 0, "dealin_value": 0, "max_value": 0, "yakuman": 0,
            "score_sum": 0, "score_max": None, "busts": 0}   # 半荘の最終持ち点の合計・最高、飛び（0点未満）回数


class LeagueIndividual:
    """
    リーグ制における雀士。
    params（打ち筋の個性）に加えて、talent（技量：判断の正確さ 0〜1）を持つ。
    麻雀は「重みが大きいほど強い」わけではないため、実力の差は主に talent で表現する。
    """
    def __init__(self, ind_id, league, params=None, talent=0.6, generation=0,
                 parent_a_id=None, display_name=None, initial_age=None, clan_root_id=None):
        self.id = ind_id
        self.league = league              # "A" / "B" / "C" / "D"
        self.params = params or {}
        self.talent = talent
        self.clan_root_id = clan_root_id if clan_root_id is not None else ind_id
        self.display_name = display_name
        self.awakened_param = None
        self.generation = generation
        self.parent_a_id = parent_a_id    # 師匠
        self.initial_age = initial_age if initial_age is not None else roll_initial_age()
        self.age_multipliers = {}
        self.consecutive_losing_seasons = 0

        self.peak_elo = 1500.0
        self.elo = 1500.0
        self.volatility = 1.0             # ムラ気：対局ごとの調子の振れ幅
        self.seasons_in_league = 0
        self.total_seasons = 0
        self.retired = False
        self.games = 0                    # 通算半荘数
        self.placements = [0, 0, 0, 0]    # 通算着順回数
        self.total_points = 0.0           # 通算ポイント
        self.career = []                  # [{"season", "league", "rank", "points", "elo"}]
        self.stats = empty_stats()        # 局単位の通算成績（和了率・放銃率などの元データ）
        self.elo_history = []             # [[期, 期末レート], ...]
        self.elo_trace = []               # [[期, 通算半荘数, レート], ...] 半荘ごと（直近 ELO_TRACE_MAX 件）
        self.recent_games = []            # 最近の対局（records.apply_match_index が更新）
        self.opponents = {}               # {相手id: [同卓数, 自分が上位, 自分が下位]}
        self.created = False              # キャラクリエイトで生まれた雀士か
        self.submission_id = None         # サイトの投稿ID
        self.creator = None               # 投稿者の表示名（任意）

        # 今季のリーグ成績（保存しない一時値）
        self.points_this_season = 0.0

    @property
    def age(self):
        return self.initial_age + self.total_seasons

    @property
    def elo(self):
        return self._elo

    @elo.setter
    def elo(self, value):
        self._elo = value
        if value > self.peak_elo:
            self.peak_elo = value

    def record_rounds(self, seat, rounds):
        """1半荘分の局結果から、和了・放銃・立直などを通算成績に加える"""
        st = self.stats
        for r in rounds:
            st["hands"] += 1
            if (r.get("riichi") or [False] * 4)[seat]:
                st["riichi"] += 1
            win = r.get("win")
            if r.get("winner") == seat and win:
                st["wins"] += 1
                st["win_value"] += win.get("value", 0)
                st["max_value"] = max(st["max_value"], win.get("value", 0))
                if r["type"] == "tsumo":
                    st["tsumo"] += 1
                if win.get("yakuman"):
                    st["yakuman"] += 1
            if r.get("loser") == seat and win:
                st["dealins"] += 1
                st["dealin_value"] += win.get("value", 0)
            if r["type"] in ("draw", "nagashi") and r.get("tenpai") and r["tenpai"][seat]:
                st["draw_tenpai"] += 1
            if r["type"] in ("draw", "nagashi"):
                st["draws"] += 1

    def record_game(self, placement, points, season=None, score=None):
        self.games += 1
        if score is not None:
            st = self.stats
            st["score_sum"] += score
            st["score_max"] = score if st["score_max"] is None else max(st["score_max"], score)
            st["busts"] += score < 0
        if season is not None:
            self.elo_trace.append([season, self.games, round(self.elo, 1)])
            del self.elo_trace[:-ELO_TRACE_MAX]
        self.placements[placement - 1] += 1
        self.total_points = round(self.total_points + points, 1)

    def to_dict(self):
        return {
            "id": self.id, "league": self.league, "params": self.params, "talent": self.talent,
            "clan_root_id": self.clan_root_id, "display_name": self.display_name,
            "awakened_param": self.awakened_param, "generation": self.generation,
            "parent_a_id": self.parent_a_id, "initial_age": self.initial_age,
            "age_multipliers": self.age_multipliers,
            "consecutive_losing_seasons": self.consecutive_losing_seasons,
            "elo": round(self.elo, 2), "peak_elo": round(self.peak_elo, 2), "volatility": self.volatility,
            "seasons_in_league": self.seasons_in_league, "total_seasons": self.total_seasons,
            "retired": self.retired, "games": self.games, "placements": self.placements,
            "total_points": self.total_points, "career": self.career,
            "created": self.created, "submission_id": self.submission_id, "creator": self.creator,
            "stats": self.stats, "elo_history": self.elo_history, "elo_trace": self.elo_trace,
            "recent_games": self.recent_games, "opponents": self.opponents,
        }

    @staticmethod
    def from_dict(d):
        ind = LeagueIndividual(
            d["id"], d["league"], d.get("params"), d.get("talent", 0.6), d.get("generation", 0),
            d.get("parent_a_id"), display_name=d.get("display_name"),
            initial_age=d.get("initial_age"), clan_root_id=d.get("clan_root_id"),
        )
        ind.awakened_param = d.get("awakened_param")
        ind.age_multipliers = d.get("age_multipliers", {})
        ind.consecutive_losing_seasons = d.get("consecutive_losing_seasons", 0)
        ind.peak_elo = d.get("peak_elo", d.get("elo", 1500.0))
        ind.elo = d.get("elo", 1500.0)
        ind.volatility = d.get("volatility", 1.0)
        ind.seasons_in_league = d.get("seasons_in_league", 0)
        ind.total_seasons = d.get("total_seasons", 0)
        ind.retired = d.get("retired", False)
        ind.games = d.get("games", 0)
        ind.placements = d.get("placements", [0, 0, 0, 0])
        ind.total_points = d.get("total_points", 0.0)
        ind.career = d.get("career", [])
        ind.created = d.get("created", False)
        ind.submission_id = d.get("submission_id")
        ind.creator = d.get("creator")
        ind.stats = {**empty_stats(), **(d.get("stats") or {})}
        ind.elo_history = d.get("elo_history", [])
        ind.elo_trace = d.get("elo_trace", [])
        ind.recent_games = d.get("recent_games", [])
        ind.opponents = d.get("opponents", {})
        return ind
