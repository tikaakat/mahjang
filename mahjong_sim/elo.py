def update_elo_multi(ratings, placements, k=32):
    """
    4人打ち用のElo更新。全ての2人組を「着順が上なら勝ち」の1対1とみなして計算し、
    1局あたりの変動幅が2人対戦と同程度になるよう K を (人数-1) で割る。
    ratings: 各席のレーティング、placements: 各席の着順（1〜4）
    """
    n = len(ratings)
    k_pair = k / (n - 1)
    deltas = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            expected_i = 1 / (1 + 10 ** ((ratings[j] - ratings[i]) / 400))
            if placements[i] < placements[j]:
                score_i = 1.0
            elif placements[i] > placements[j]:
                score_i = 0.0
            else:
                score_i = 0.5
            deltas[i] += k_pair * (score_i - expected_i)
            deltas[j] -= k_pair * (score_i - expected_i)
    return [r + d for r, d in zip(ratings, deltas)]
