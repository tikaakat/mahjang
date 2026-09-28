import random

from mahjong_sim.ai import PARAM_KEYS

STYLE_KEYS = PARAM_KEYS  # 打ち筋の個性（牌効率・ドラ・役牌・染め手・タンヤオ・鳴き・リーチ・守備・押し）


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
        self.initial_age = initial_age if initial_age is not None else random.randint(20, 26)
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
        self.career = []                  # [{"season", "league", "rank", "points"}]

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

    def record_game(self, placement, points):
        self.games += 1
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
        return ind
