"""AIの強さ・打ち方を、現実のプロの目安と比べるための計測ツール。
リーグの雀士（打ち筋・技量）で4人卓を組み、半荘を多数打って局単位の指標を集計する。
使い方: python tools/measure_ai.py --games 400 [--rule houou] [--workers 4]"""
import argparse
import json
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mahjong_sim.ai import MahjongAI
from mahjong_sim.game import Game
from mahjong_sim.rules import RULESETS

# 目安：Mリーグ（ランキング対象選手の平均。25000点持ち・赤あり・裏あり）
TARGET = {"和了率": 20.6, "放銃率": 11.0, "立直率": 24.2, "副露率": 23.3, "平均和了打点": 6753, "流局率": 17.0}


def load_field(data_dir):
    with open(os.path.join(data_dir, "rosters.json"), encoding="utf-8") as f:
        r = json.load(f)
    return [p for lg in "ABCD" for p in r[lg]]


def play(args):
    field, seed, rule_key, noise_at_zero, skill, tune = args
    from mahjong_sim import ai as ai_module
    ai_module.TUNE.update(tune)
    rng = random.Random(seed)
    seats = rng.sample(field, 4)
    agents = [MahjongAI(p["params"], skill=skill, name=p["id"],
                        noise=(ai_module.noise_from_talent(p.get("talent", 0.6)) if noise_at_zero is None
                               else noise_at_zero * (1 - p.get("talent", 0.6))), rng=rng)
              for p in seats]
    res = Game(agents, rules=RULESETS[rule_key], rng=rng).run()
    band = {}
    for p, place in zip(seats, res["placement"]):
        t = p.get("talent", 0.6)
        b = "技量0.4-0.55" if t < 0.55 else "技量0.55-0.7" if t < 0.7 else "技量0.7-0.8" if t < 0.8 else "技量0.8以上"
        band.setdefault(b, []).append(place)
    st = {k: 0 for k in ("hands", "wins", "tsumo", "dealins", "riichi", "calls", "draws", "win_value", "yakuman", "chombo")}
    st["games"] = 1
    for r in res["rounds"]:
        st["hands"] += 4
        called = set()
        for e in r["events"]:
            if e["type"] in ("chi", "pon", "daiminkan"):
                called.add(e["actor"])
        st["calls"] += len(called)
        st["riichi"] += sum(1 for x in (r.get("riichi") or []) if x)
        if r["type"] in ("draw", "nagashi"):
            st["draws"] += 1
        else:
            st["wins"] += 1
            st["win_value"] += r["win"].get("value", 0)
            st["tsumo"] += r["type"] == "tsumo"
            st["dealins"] += r["type"] == "ron"
            st["yakuman"] += 1 if r["win"].get("yakuman") else 0
    st["rounds"] = len(res["rounds"])
    st["band"] = band
    return st


def report(total):
    hands, rounds = total["hands"], total["rounds"]
    out = {
        "和了率": 100 * total["wins"] / hands,
        "放銃率": 100 * total["dealins"] / hands,
        "立直率": 100 * total["riichi"] / hands,
        "副露率": 100 * total["calls"] / hands,
        "平均和了打点": total["win_value"] / max(1, total["wins"]),
        "流局率": 100 * total["draws"] / rounds,
        "ツモ和了の割合": 100 * total["tsumo"] / max(1, total["wins"]),
        "1半荘の局数": rounds / total["games"],
    }
    for k, v in out.items():
        t = TARGET.get(k)
        print(f"  {k:<10}{v:>9.1f}" + (f"   （目安 {t}）" if t else ""))
    print("  技量帯ごとの平均着順（2.50が平均）: " + "　".join(
        f"{b} {sum(v) / len(v):.2f}（{len(v)}人）" for b, v in sorted(total["band"].items())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--rule", default="houou")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--noise", type=float, default=None, help="指定すると、技量0のときのブレをこの値で固定（0ならブレなし）")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skill", type=int, default=4)
    ap.add_argument("--tune", nargs="*", default=[], help="ai.TUNE の上書き。例: riichi_bias=0.2 dora_scale=2")
    a = ap.parse_args()
    field = load_field(a.data_dir)
    tune = {k: float(v) for k, v in (t.split("=") for t in a.tune)}
    jobs = [(field, a.seed * 100000 + i, a.rule, a.noise, a.skill, tune) for i in range(a.games)]
    total = {}
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for st in ex.map(play, jobs, chunksize=4):
            for k, v in st.items():
                if k == "band":
                    for b, places in v.items():
                        total.setdefault("band", {}).setdefault(b, []).extend(places)
                else:
                    total[k] = total.get(k, 0) + v
    print(f"{a.games}半荘（{a.rule}ルール・リーグの雀士・skill {a.skill}・ノイズ{a.noise}・調整 {tune or 'なし'}）")
    report(total)


if __name__ == "__main__":
    main()
