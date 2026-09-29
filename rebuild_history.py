"""通算の局成績（和了率など）とレート推移を、保存済みの対局記録から作り直してサイト用データを更新する。
シーズンは進めない。使い方: python rebuild_history.py --data-dir data"""
import argparse

from mahjong_league.io_utils import (
    load_rosters, load_season_state, save_rosters, save_season_state, save_site_index, backfill_history,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    state = load_season_state(args.data_dir)
    rosters = load_rosters(args.data_dir)
    if rosters is None:
        print("ロスターがありません")
        return
    backfill_history(args.data_dir, rosters, state)
    save_rosters(args.data_dir, rosters)
    save_season_state(args.data_dir, state)
    save_site_index(args.data_dir, state, rosters)
    print("作り直しました")


if __name__ == "__main__":
    main()
