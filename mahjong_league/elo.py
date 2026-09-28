def k_factor(total_seasons):
    """経験の浅い個体ほどレートの変動幅を大きくする（オセロ版と同じ段階的逓減）"""
    if total_seasons < 3:
        return 48
    elif total_seasons < 8:
        return 32
    return 24


def update_elo_table(individuals, placements):
    """
    4人打ち1半荘の結果でEloを更新する。全ての2人組を「着順が上なら勝ち」の1対1とみなし、
    各自のKを (人数-1) で割って合算する（1半荘の変動幅が1対1の対局と同程度になる）。
    """
    n = len(individuals)
    ratings = [ind.elo for ind in individuals]
    deltas = [0.0] * n
    for i in range(n):
        k_i = k_factor(individuals[i].total_seasons) / (n - 1)
        for j in range(n):
            if i == j:
                continue
            expected = 1 / (1 + 10 ** ((ratings[j] - ratings[i]) / 400))
            if placements[i] < placements[j]:
                score = 1.0
            elif placements[i] > placements[j]:
                score = 0.0
            else:
                score = 0.5
            deltas[i] += k_i * (score - expected)
    for ind, d in zip(individuals, deltas):
        ind.elo = ind.elo + d
