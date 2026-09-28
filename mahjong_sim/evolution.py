import random

from .individual import Individual
from .ai import PARAM_KEYS
from .elo import update_elo_multi
from .play import play_table, play_vs_benchmark, play_vs_title_holder, rank_score
from .family_names import random_immigrant_family_name

MUTATION_RATE = 0.2
MUTATION_STRENGTH = 0.25
TABLE_SIZE = 4


def _new_id(generation, suffix=""):
    return f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}{suffix}"


# ============================================================
# 無性生殖：親の変異版を1体作る
# ============================================================
def mutate_clone(parent, generation):
    child_params = {}
    for key in PARAM_KEYS:
        val = parent.params[key]
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_params[key] = max(0.01, val)

    child = Individual(
        _new_id(generation), generation, parent_a_id=parent.id, parent_b_id=None,
        params=child_params, family_label=parent.family_label,
    )
    child.elo = parent.elo
    return child


# ============================================================
# 移民との交配イベント：パラメータごとに、どちらかの親から丸ごと継承する「組み換え」方式。
# 平均化（ブレンド）は多様性を減らす方向に働くため採用しない。家名は合成表記。
# ============================================================
def crossover_main_sub(parent_main, parent_sub, new_id, generation, family_label=None):
    child_params = {}
    for key in PARAM_KEYS:
        source = parent_main if random.random() < 0.5 else parent_sub
        val = source.params[key]
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_params[key] = max(0.01, val)

    child = Individual(
        new_id, generation, parent_main.id, parent_sub.id, child_params,
        family_label=family_label or parent_main.family_label,
    )
    child.elo = (parent_main.elo + parent_sub.elo) / 2
    return child


def generate_immigrant(generation):
    return Individual(
        ind_id=_new_id(generation, suffix="i"), generation=generation,
        family_label=random_immigrant_family_name(),
    )


def crossover_hybrid(parent_top, immigrant, generation):
    combined_label = f"{parent_top.family_label}×{immigrant.family_label}"
    return crossover_main_sub(parent_top, immigrant, _new_id(generation, suffix="h"), generation, family_label=combined_label)


def manual_breed(population_by_id, parent_a_id, parent_b_id, generation):
    parent_a = population_by_id[parent_a_id]
    parent_b = population_by_id[parent_b_id]
    return crossover_main_sub(parent_a, parent_b, _new_id(generation, suffix="m"), generation)


# ============================================================
# スイス方式トーナメント（4人打ち版）
# 成績順に並べ、上から4人ずつ卓を組む。ただし同じ相手との再戦はなるべく避ける。
# ============================================================
def swiss_tables(ranked_ids, met_pairs):
    unseated = list(ranked_ids)
    tables = []
    while len(unseated) >= TABLE_SIZE:
        table = [unseated.pop(0)]
        while len(table) < TABLE_SIZE:
            # 成績の近い順に見て、卓の既存メンバーとの対戦回数が最も少ない相手を選ぶ
            window = unseated[:TABLE_SIZE * 2]
            best = min(window, key=lambda c: (sum(met_pairs.get(frozenset((c, m)), 0) for m in table),
                                              unseated.index(c)))
            unseated.remove(best)
            table.append(best)
        tables.append(table)
    return tables


def run_swiss_tournament(population, generation, matches_log, rounds=4, game_length="east"):
    by_id = {ind.id: ind for ind in population}
    score = {ind.id: 0.0 for ind in population}
    met_pairs = {}

    for rnd_idx in range(rounds):
        ranked_ids = sorted(by_id.keys(), key=lambda i: (-score[i], -by_id[i].elo))
        tables = swiss_tables(ranked_ids, met_pairs)
        print(f"  --- スイス方式 ラウンド{rnd_idx + 1}/{rounds}（{len(tables)}卓）---")

        for table_idx, table in enumerate(tables):
            for i in range(len(table)):
                for j in range(i + 1, len(table)):
                    key = frozenset((table[i], table[j]))
                    met_pairs[key] = met_pairs.get(key, 0) + 1

            result = play_table([by_id[i] for i in table], length=game_length)
            seats = result["seats"]
            ratings = [by_id[i].elo for i in seats]
            new_ratings = update_elo_multi(ratings, result["placement"])

            for s, ind_id in enumerate(seats):
                ind = by_id[ind_id]
                ind.elo = new_ratings[s]
                score[ind_id] += result["points"][s]
                ind.match_history.append({
                    "opponents": [x for x in seats if x != ind_id],
                    "placement": result["placement"][s],
                    "score": result["final_scores"][s],
                    "generation": generation,
                })

            standing = sorted(range(4), key=lambda s: result["placement"][s])
            desc = " / ".join(f"{result['placement'][s]}着 {seats[s]}({result['final_scores'][s]})" for s in standing)
            print(f"    卓{table_idx + 1}/{len(tables)}: {desc}")

            matches_log.append({
                "opponent_type": "individual", "generation": generation, "round": rnd_idx + 1,
                "seats": seats, "final_scores": result["final_scores"],
                "placement": result["placement"], "points": result["points"],
                "rounds": result["rounds"],
            })

    return score


# ============================================================
# 固定AI（ベンチマーク・タイトルホルダー）との対局
# ============================================================
def _play_series(individual, generation, matches_log, games, opponent_type, level, game_length, play_fn):
    placements = []
    for _ in range(games):
        placement, final_score, seat, summary = play_fn(individual, level, length=game_length)
        placements.append(placement)
        individual.match_history.append({
            "opponent": opponent_type, "placement": placement, "score": final_score,
            "generation": generation, "seat": seat,
        })
        matches_log.append({
            "individual_a_id": individual.id, "opponent_type": opponent_type, "level": level,
            "placement": placement, "result": rank_score(placement), "seat": seat,
            "generation": generation, **summary,
        })
    return placements


# ============================================================
# ベンチマーク「温度計」：Eloには影響させず、現在のレベルを監視するためだけの対局
# 首位の個体が、固定AI3人の卓に入って打つ
# ============================================================
def run_benchmark_thermometer(top_individual, generation, matches_log, games=5,
                               benchmark_level=2, game_length="east"):
    return _play_series(top_individual, generation, matches_log, games, "benchmark",
                        benchmark_level, game_length, play_vs_benchmark)


# ============================================================
# タイトル戦：温度計の壁を極限まで登り切った首位だけが挑戦できる、
# 「タイトルホルダー」（暫定：自前AIの最高精度版。将来的に外部の強豪AIへ差し替え予定）
# ============================================================
TITLE_HOLDER_LEVEL = 5
TITLE_MATCH_GAMES = 5
TITLE_WIN_AVG_PLACEMENT = 2.0  # 平均着順がこれ以下ならタイトル奪取


def run_title_challenge(champion, generation, matches_log, game_length="east"):
    """首位がタイトルホルダー3人の卓に挑戦する。Eloには影響させない特別な記録として残す"""
    placements = _play_series(champion, generation, matches_log, TITLE_MATCH_GAMES, "title_holder",
                              TITLE_HOLDER_LEVEL, game_length, play_vs_title_holder)
    avg = sum(placements) / len(placements)
    tops = sum(1 for p in placements if p == 1)
    return avg <= TITLE_WIN_AVG_PLACEMENT, tops, avg


# ============================================================
# 新規参入個体の生成：基本は変異クローンで埋め、うち1枠は毎世代必ず新しい移民に譲る。
# 移民は次世代のトーナメントで実力を証明できれば生き残り、弱ければそのまま消える。
# ============================================================
def generate_new_entrants(survivors, generation, population_size, immigrant_count=1):
    slots = population_size - len(survivors)
    new_entrants = []

    actual_immigrant_count = min(immigrant_count, slots)
    for _ in range(actual_immigrant_count):
        immigrant = generate_immigrant(generation)
        new_entrants.append(immigrant)
        print(f"  → 移民 {immigrant.id}［{immigrant.family_label}流］が現れました（実力を証明できれば生き残ります）")

    ranked_survivors = sorted(survivors, key=lambda ind: -ind.elo) if survivors else []
    idx = 0
    while len(new_entrants) < slots and ranked_survivors:
        parent = ranked_survivors[idx % len(ranked_survivors)]
        new_entrants.append(mutate_clone(parent, generation))
        idx += 1

    return new_entrants[:slots]


def select_survivors_with_protection(ranked, population_size, protected_families, max_slots_per_family_ratio=0.5):
    """
    保護対象（恒久保証＋猶予期間中の移民）の流派には、優先的に1枠を確保する。
    保護対象が生存枠を超える場合は、代表の順位が低い流派から優先度を落とす
    （＝恒久保証側が一時的に席を譲る形になる。移民の猶予は必ず守られる）。
    残りの枠は成績順で埋めるが、1流あたりの取得枠数には上限を設ける。
    """
    slots = max(1, population_size // 2)
    max_per_family = max(1, int(slots * max_slots_per_family_ratio))

    rank_index = {ind.id: i for i, ind in enumerate(ranked)}

    family_reps = {}
    for ind in ranked:
        label = ind.family_label
        if label not in family_reps or rank_index[ind.id] < rank_index[family_reps[label].id]:
            family_reps[label] = ind

    present_protected = [fam for fam in protected_families if fam in family_reps]
    present_protected_sorted = sorted(present_protected, key=lambda fam: rank_index[family_reps[fam].id])
    guaranteed_labels = present_protected_sorted[:slots]

    guaranteed = [family_reps[fam] for fam in guaranteed_labels]
    guaranteed_ids = {ind.id for ind in guaranteed}

    survivors = list(guaranteed)
    family_counts = {}
    for ind in survivors:
        family_counts[ind.family_label] = family_counts.get(ind.family_label, 0) + 1

    for ind in ranked:
        if len(survivors) >= slots:
            break
        if ind.id in guaranteed_ids:
            continue
        if family_counts.get(ind.family_label, 0) >= max_per_family:
            continue
        survivors.append(ind)
        family_counts[ind.family_label] = family_counts.get(ind.family_label, 0) + 1

    if len(survivors) < slots:
        chosen_ids = {ind.id for ind in survivors}
        for ind in ranked:
            if len(survivors) >= slots:
                break
            if ind.id in chosen_ids:
                continue
            survivors.append(ind)

    return survivors


# ============================================================
# 1世代分の処理
# ============================================================
def run_generation(population, generation, matches_log,
                    population_size=16, swiss_rounds=4, game_length="east",
                    benchmark_level=2, benchmark_games=5,
                    immigrant_count=1,
                    guaranteed_families=None, grace_info=None,
                    grace_period=3, reset_interval=10):
    """
    guaranteed_families: 恒久保証されている流派名のリスト（reset_intervalごとに引き直す）
    grace_info: {流派名: 保護終了世代} の辞書。新規移民に猶予期間として付与する
    """
    guaranteed_families = list(guaranteed_families) if guaranteed_families else []
    grace_info = dict(grace_info) if grace_info else {}

    score = run_swiss_tournament(
        population, generation, matches_log, rounds=swiss_rounds, game_length=game_length,
    )

    ranked = sorted(population, key=lambda ind: (-score[ind.id], -ind.elo))

    if ranked:
        run_benchmark_thermometer(
            ranked[0], generation, matches_log, games=benchmark_games,
            benchmark_level=benchmark_level, game_length=game_length,
        )

    slots = max(1, population_size // 2)
    rank_index = {ind.id: i for i, ind in enumerate(ranked)}

    def top_family_labels(n):
        family_reps = {}
        for ind in ranked:
            label = ind.family_label
            if label not in family_reps or rank_index[ind.id] < rank_index[family_reps[label].id]:
                family_reps[label] = ind
        return sorted(family_reps.keys(), key=lambda fam: rank_index[family_reps[fam].id])[:n]

    if not guaranteed_families:
        guaranteed_families = top_family_labels(slots)
        print(f"  恒久保証リストを初期化しました: {', '.join(guaranteed_families)}")

    active_grace = {fam for fam, expiry in grace_info.items() if generation <= expiry}
    protected_families = set(guaranteed_families) | active_grace

    survivors = select_survivors_with_protection(ranked, population_size, protected_families)

    families_present = sorted(set(ind.family_label for ind in survivors))
    grace_note = f"（猶予中: {', '.join(sorted(active_grace))}）" if active_grace else ""
    print(f"  現在の流派（生存者内）: {', '.join(families_present)} {grace_note}")

    if reset_interval and generation > 0 and generation % reset_interval == 0:
        new_guaranteed = top_family_labels(slots)
        print(f"  ★ 恒久保証リストを更新: {', '.join(guaranteed_families)} → {', '.join(new_guaranteed)}")
        guaranteed_families = new_guaranteed
        grace_info = {fam: exp for fam, exp in grace_info.items() if generation <= exp}

    new_entrants = generate_new_entrants(survivors, generation + 1, population_size, immigrant_count)
    for ind in new_entrants:
        is_fresh_immigrant = (ind.parent_a_id is None and ind.parent_b_id is None)
        if is_fresh_immigrant and ind.family_label not in grace_info and ind.family_label not in guaranteed_families:
            grace_info[ind.family_label] = generation + 1 + grace_period
            print(f"  → {ind.family_label}流に猶予期間を付与（世代{generation + 1 + grace_period}まで保護）")

    return survivors + new_entrants, guaranteed_families, grace_info, score
