"""1半荘を実況表示するデモ。雀士を指定しなければ標準的なAI同士で打つ。

例:
  python play_demo.py --seed 1
  python play_demo.py --players A0-000 A0-001 A0-002 A0-003   # data/rosters.json の雀士4人で対局
"""
import argparse
import json
import os
import random

from mahjong_sim.ai import MahjongAI
from mahjong_sim.game import Game
from mahjong_sim.play import BENCHMARK_PARAMS
from mahjong_sim.rules import RENMEI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--players", nargs=4, metavar="ID", help="対局させる雀士ID（4人）")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.players:
        with open(os.path.join(args.data_dir, "rosters.json"), encoding="utf-8") as f:
            pool = {d["id"]: d for lg in json.load(f).values() for d in lg}
        agents = [MahjongAI(pool[i]["params"], name=pool[i]["display_name"],
                            noise=14.0 * (1 - pool[i]["talent"])) for i in args.players]
    else:
        agents = [MahjongAI(BENCHMARK_PARAMS, name=f"標準AI{s + 1}") for s in range(4)]

    result = Game(agents, rules=RENMEI, rng=random.Random(args.seed), log=True).run()
    print("=== 終局 ===")
    for s in range(4):
        print(f"  {agents[s].name}: {result['final_scores'][s]}点 {result['placement'][s]}着 ({result['points'][s]:+.1f})")


if __name__ == "__main__":
    main()
