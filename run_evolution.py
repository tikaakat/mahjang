import argparse
import random

from mahjong_sim.individual import Individual
from mahjong_sim.evolution import run_generation, run_title_challenge, TITLE_MATCH_GAMES
from mahjong_sim.io_utils import load_checkpoint, export_population, load_training_state, save_training_state
from mahjong_sim.family_names import assign_initial_family_names

BENCHMARK_LEVEL_MAX = 4
BENCHMARK_LEVEL_STEP = 1
WIN_RATE_UPGRADE_THRESHOLD = 0.65    # 着順スコア（1着=1.0〜4着=0）の平均。互角なら0.5前後
WIN_RATE_DOWNGRADE_THRESHOLD = 0.35


def compute_win_rate_vs_benchmark(matches_log, generation):
    relevant = [m for m in matches_log if m.get("opponent_type") == "benchmark" and m.get("generation") == generation]
    if not relevant:
        return None, None
    rate = sum(m["result"] for m in relevant) / len(relevant)
    avg_placement = sum(m["placement"] for m in relevant) / len(relevant)
    return rate, avg_placement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--population-size", type=int, default=16, help="個体数（4の倍数）")
    parser.add_argument("--swiss-rounds", type=int, default=4)
    parser.add_argument("--game-length", choices=["east", "south"], default="east",
                        help="east=東風戦 / south=半荘戦")
    parser.add_argument("--benchmark-level", type=int, default=2,
                        help="ベンチマーク相手の初期レベル(1〜4)。2回目以降は training_state.json の値が優先")
    parser.add_argument("--benchmark-games", type=int, default=6)
    parser.add_argument("--immigrant-count", type=int, default=1, help="毎世代必ず投入する移民の数")
    parser.add_argument("--grace-period", type=int, default=3, help="新規移民が無条件で保護される世代数")
    parser.add_argument("--reset-interval", type=int, default=10, help="恒久保証リストを実力順で引き直す世代間隔")
    args = parser.parse_args()

    if args.population_size % 4 != 0:
        parser.error("--population-size は4の倍数にしてください（4人打ちの卓を組むため）")

    all_individuals, matches_log = load_checkpoint(args.data_dir)
    training_state = load_training_state(args.data_dir)

    benchmark_level = training_state.get("benchmark_level") or args.benchmark_level
    win_rate_history = training_state.get("win_rate_history", [])
    active_population_ids = training_state.get("active_population_ids")
    title_holder_defeats = training_state.get("title_holder_defeats", [])
    guaranteed_families = training_state.get("guaranteed_families", [])
    grace_info = training_state.get("grace_info", {})

    if all_individuals is None:
        random.seed()
        all_individuals = {}
        matches_log = []
        population = []
        family_names = assign_initial_family_names(args.population_size)
        for i in range(args.population_size):
            ind = Individual(ind_id=f"G0-{i:03d}", generation=0, family_label=family_names[i])
            population.append(ind)
            all_individuals[ind.id] = ind
        start_gen = 0
    else:
        # 新規参入個体は「次に戦う世代」の番号で生まれるため、最大世代がそのまま次の世代になる
        start_gen = training_state.get("next_generation") or max(ind.generation for ind in all_individuals.values())
        if active_population_ids:
            population = [all_individuals[i] for i in active_population_ids if i in all_individuals]
            missing = len(active_population_ids) - len(population)
            if missing > 0:
                print(f"  ※ 前回の現役個体のうち{missing}体が見つかりませんでした")
        else:
            print("  ※ 現役個体リストが見つからないため、Elo上位から復元します")
            ranked = sorted(all_individuals.values(), key=lambda ind: ind.elo, reverse=True)
            population = ranked[:args.population_size]

    for gen in range(start_gen, start_gen + args.generations):
        print(f"=== Generation {gen} (benchmark_level={benchmark_level}, population={len(population)}) ===")
        population, guaranteed_families, grace_info, swiss_score = run_generation(
            population, gen, matches_log,
            population_size=args.population_size,
            swiss_rounds=args.swiss_rounds,
            game_length=args.game_length,
            benchmark_level=benchmark_level,
            benchmark_games=args.benchmark_games,
            immigrant_count=args.immigrant_count,
            guaranteed_families=guaranteed_families,
            grace_info=grace_info,
            grace_period=args.grace_period,
            reset_interval=args.reset_interval,
        )
        for ind in population:
            all_individuals[ind.id] = ind

        ranked_now = sorted(population, key=lambda ind: -ind.elo)
        for ind in ranked_now[:5]:
            print(f"  {ind.id} [{ind.family_label}流]: Elo={ind.elo:.1f}")

        export_population(list(all_individuals.values()), matches_log, args.data_dir)

        win_rate, avg_placement = compute_win_rate_vs_benchmark(matches_log, gen)
        if win_rate is not None:
            win_rate_history.append({
                "generation": gen, "win_rate": round(win_rate, 3),
                "avg_placement": round(avg_placement, 2), "benchmark_level": benchmark_level,
            })
            print(f"  温度計（首位 vs ベンチマーク, 世代{gen}）: 着順スコア {win_rate:.1%} / 平均着順 {avg_placement:.2f}")

            measured_level = benchmark_level
            if win_rate >= WIN_RATE_UPGRADE_THRESHOLD and benchmark_level < BENCHMARK_LEVEL_MAX:
                benchmark_level = min(BENCHMARK_LEVEL_MAX, benchmark_level + BENCHMARK_LEVEL_STEP)
                print(f"  → 成績が良いため、ベンチマークのレベルを {benchmark_level} に引き上げました")
            elif win_rate <= WIN_RATE_DOWNGRADE_THRESHOLD and benchmark_level > args.benchmark_level:
                benchmark_level = max(args.benchmark_level, benchmark_level - BENCHMARK_LEVEL_STEP)
                print(f"  → 成績が悪いため、ベンチマークのレベルを {benchmark_level} に引き下げました")

            # --- タイトル挑戦：温度計の壁を極限まで登り切った首位だけが挑戦できる ---
            #     （最上位レベルのベンチマーク相手に好成績を出した世代のみ）
            if measured_level >= BENCHMARK_LEVEL_MAX and win_rate >= WIN_RATE_UPGRADE_THRESHOLD:
                champion = max(population, key=lambda ind: (swiss_score.get(ind.id, float("-inf")), ind.elo))
                print(f"  ★ {champion.id}［{champion.family_label}流］がタイトルホルダーに挑戦します！")
                won_title, tops, avg = run_title_challenge(champion, gen, matches_log, game_length=args.game_length)
                print(f"    結果: {TITLE_MATCH_GAMES}戦 トップ{tops}回 平均着順{avg:.2f} → {'タイトル奪取！' if won_title else '敗退'}")
                if won_title:
                    title_holder_defeats.append({
                        "individual_id": champion.id,
                        "family_label": champion.family_label,
                        "generation": gen,
                        "tops": tops,
                        "avg_placement": round(avg, 2),
                    })
                export_population(list(all_individuals.values()), matches_log, args.data_dir)

        save_training_state(args.data_dir, {
            "benchmark_level": benchmark_level,
            "next_generation": gen + 1,
            "win_rate_history": win_rate_history,
            "active_population_ids": [ind.id for ind in population],
            "title_holder_defeats": title_holder_defeats,
            "guaranteed_families": guaranteed_families,
            "grace_info": grace_info,
        })


if __name__ == "__main__":
    main()
