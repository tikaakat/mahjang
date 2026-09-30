"""
新人リーグ：サイトから投稿されたキャラクリエイトを集めて4人打ちのミニリーグで競わせ、
上位（来期のDリーグ欠員数ぶん）だけが次の期の開始時にDリーグへ入門する。

投稿が目標人数に満たない場合は自動生成の候補で埋める（自動生成が上位に入った枠は、
通常の新弟子で補充される）。本戦（run_season.py）の直後（次季の欠員が確定してから）に実行する。勝者は次の実行の本戦の冒頭で入門する。

入力:  --submissions-path の JSON（[{"submission_id", "name", "creator", "type", "params"}, ...]）
出力:  data/newcomer_winners.json（run_season.py が読む）
       data/newcomer_league/for_season_N.json（サイト表示・投稿ステータス更新用）
"""
import argparse
import json
import os
import random

from mahjong_league.creation import build_created_individual, clean_name, PRESETS
from mahjong_league.league import run_league, LEAGUE_CAPACITY
from mahjong_league.names import NameRegistry
from mahjong_league.io_utils import load_rosters, load_season_state

TARGET_POOL = 16          # 4人卓×4
SUBMISSION_CAP = 32       # 1回に受け付ける投稿の上限（超過分は先着順で次回へは回さず落選扱い）
SECTIONS = 3              # 1節4半荘 × 3節 = 1人12半荘


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--submissions-path", default="data/newcomer_submissions.json")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    if args.seed is not None:
        random.seed(args.seed)

    submissions = []
    if os.path.exists(args.submissions_path):
        try:
            with open(args.submissions_path, encoding="utf-8") as f:
                submissions = json.load(f) or []
        except (json.JSONDecodeError, OSError) as e:
            print(f"※ 投稿ファイルを読めなかったため0件として扱います: {e}")
        if not isinstance(submissions, list):
            submissions = []
    submissions = [s for s in submissions if clean_name(s.get("name"))][:SUBMISSION_CAP]

    state = load_season_state(args.data_dir)
    rosters = load_rosters(args.data_dir)
    target_season = state["current_season"] + 1
    if rosters is None:
        slots = 0  # 初回は初期ロスターで定員が埋まるため入門枠なし
    else:
        slots = LEAGUE_CAPACITY["D"] - len(rosters["D"])
    print(f"新人リーグ（第{target_season}期入門分）: 投稿{len(submissions)}件・入門枠{slots}名")

    if not submissions:
        _write_outputs(args.data_dir, target_season, [], [], slots)
        print("投稿がないため新人リーグは開催しません")
        return

    registry = NameRegistry.from_dict(state.get("name_registry", {}))
    entries = [dict(s, auto_generated=False) for s in submissions]
    pool_size = max(TARGET_POOL, -(-len(entries) // 4) * 4)
    while len(entries) < pool_size:
        entries.append({"name": registry.generate(), "type": random.choice(list(PRESETS)), "auto_generated": True})

    candidates = []
    for i, entry in enumerate(entries):
        ind = build_created_individual(entry, f"NL{target_season}-{i:03d}")
        ind.entry = entry
        candidates.append(ind)

    ranked, _records, stats = run_league(candidates, "新人", target_season, rng, sections=SECTIONS)

    winners, standings = [], []
    for rank, ind in enumerate(ranked, 1):
        e = ind.entry
        is_winner = (not e["auto_generated"]) and rank <= slots
        st = stats[ind.id]
        standings.append({
            "rank": rank, "name": ind.display_name, "submission_id": e.get("submission_id"),
            "creator": e.get("creator"), "auto": e["auto_generated"], "points": st["points"],
            "games": st["games"], "placements": st["placements"], "winner": is_winner,
            "params": ind.params, "awakened_param": ind.awakened_param,
        })
        if is_winner:
            winners.append({k: v for k, v in e.items() if k != "auto_generated"})
        print(f"  {rank:2d}位 {ind.display_name}{'（自動）' if e['auto_generated'] else ''} {st['points']:+.1f}"
              + ("  → 入門" if is_winner else ""))
    _write_outputs(args.data_dir, target_season, winners, standings, slots)


def _write_outputs(data_dir, season, winners, standings, slots):
    with open(os.path.join(data_dir, "newcomer_winners.json"), "w", encoding="utf-8") as f:
        json.dump(winners, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(data_dir, "newcomer_league"), exist_ok=True)
    with open(os.path.join(data_dir, "newcomer_league", f"for_season_{season}.json"), "w", encoding="utf-8") as f:
        json.dump({"season": season, "slots": slots, "standings": standings}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
