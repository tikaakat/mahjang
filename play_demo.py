"""1局分の対局を実況表示するデモ。個体を指定しなければベンチマークAI同士で打つ。

例:
  python play_demo.py                          # ベンチマークAI(レベル4)同士の東風戦
  python play_demo.py --level 1 --length south # レベル1同士の半荘戦
  python play_demo.py --individuals G3-1A2 G3-0FF G2-3Ci G3-777   # data/ の個体4人で対局
"""
import argparse
import json
import os
import random

from mahjong_sim.ai import MahjongAI
from mahjong_sim.game import Game
from mahjong_sim.play import BENCHMARK_PARAMS, INDIVIDUAL_SKILL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--individuals", nargs=4, metavar="ID", help="対局させる個体ID（4人）")
    parser.add_argument("--level", type=int, default=4, help="個体を指定しない場合のAIレベル(1〜5)")
    parser.add_argument("--length", choices=["east", "south"], default="east")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    if args.individuals:
        with open(os.path.join(args.data_dir, "individuals.json"), encoding="utf-8") as f:
            pool = {d["id"]: d for d in json.load(f)}
        agents = [MahjongAI(pool[i]["params"], skill=INDIVIDUAL_SKILL, name=i) for i in args.individuals]
    else:
        agents = [MahjongAI(BENCHMARK_PARAMS, skill=args.level, name=f"bench{s}") for s in range(4)]

    result = Game(agents, length=args.length, rng=random.Random(args.seed), log=True).run()
    print("=== 終局 ===")
    for s in range(4):
        print(f"  {s}家 {agents[s].name}: {result['final_scores'][s]}点 {result['placement'][s]}着 ({result['points'][s]:+.1f})")


if __name__ == "__main__":
    main()
