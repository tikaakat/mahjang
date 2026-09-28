import random

from .ai import MahjongAI
from .game import Game

INDIVIDUAL_SKILL = 4

# ベンチマーク（温度計）用の固定パラメータ：バランス型の手堅い設定
BENCHMARK_PARAMS = {
    "speed_weight": 5.0,
    "dora_weight": 2.0,
    "yakuhai_weight": 2.0,
    "flush_weight": 1.0,
    "tanyao_weight": 1.0,
    "call_weight": 3.0,
    "riichi_weight": 6.0,
    "defense_weight": 4.0,
    "push_weight": 5.0,
}

# タイトルホルダー（暫定）のパラメータ：手作業で調整した「強い打ち手」の設定
TITLE_HOLDER_PARAMS = {
    "speed_weight": 6.0,
    "dora_weight": 2.5,
    "yakuhai_weight": 2.0,
    "flush_weight": 1.0,
    "tanyao_weight": 1.5,
    "call_weight": 4.0,
    "riichi_weight": 6.0,
    "defense_weight": 5.0,
    "push_weight": 6.0,
}


def _run(agents, length, rng):
    return Game(agents, length=length, rng=rng).run()


def _summarize_rounds(rounds):
    """対局ログを保存用に軽量化する（打牌の全履歴は保存しない）"""
    out = []
    for r in rounds:
        item = {"round": r["round"], "honba": r["honba"], "type": r["type"], "deltas": r["deltas"]}
        if r["type"] == "draw":
            item["tenpai"] = r["tenpai"]
        else:
            item.update({"winner": r["winner"], "loser": r["loser"], "tile": r["tile"], "win": r["win"]})
        out.append(item)
    return out


def play_table(individuals, length="east", rng=None):
    """個体4人で1半荘（東風戦）を打つ。席順はランダム。
    戻り値: {"seats": [個体ID], "final_scores", "placement", "points", "rounds"}"""
    rng = rng or random.Random()
    seated = list(individuals)
    rng.shuffle(seated)
    agents = [MahjongAI(ind.params, skill=INDIVIDUAL_SKILL, name=ind.id) for ind in seated]
    result = _run(agents, length, rng)
    return {
        "seats": [ind.id for ind in seated],
        "final_scores": result["final_scores"],
        "placement": result["placement"],
        "points": result["points"],
        "rounds": _summarize_rounds(result["rounds"]),
    }


def play_vs_fixed(individual, params, skill, length="east", rng=None):
    """個体1人 vs 固定AI3人。個体の席はランダム。
    戻り値: (個体の着順, 個体の素点, 個体の席, 対局結果)"""
    rng = rng or random.Random()
    seat = rng.randrange(4)
    agents = [MahjongAI(params, skill=skill, name="fixed") for _ in range(4)]
    agents[seat] = MahjongAI(individual.params, skill=INDIVIDUAL_SKILL, name=individual.id)
    result = _run(agents, length, rng)
    summary = {
        "final_scores": result["final_scores"],
        "table_placement": result["placement"],
        "table_points": result["points"],
        "rounds": _summarize_rounds(result["rounds"]),
    }
    return result["placement"][seat], result["final_scores"][seat], seat, summary


def play_vs_benchmark(individual, benchmark_level, length="east", rng=None):
    return play_vs_fixed(individual, BENCHMARK_PARAMS, benchmark_level, length, rng)


def play_vs_title_holder(individual, title_holder_level, length="east", rng=None):
    return play_vs_fixed(individual, TITLE_HOLDER_PARAMS, title_holder_level, length, rng)


def rank_score(placement):
    """着順を 0〜1 の「勝率相当」に換算する（1着=1.0, 2着=0.67, 3着=0.33, 4着=0）"""
    return (4 - placement) / 3
