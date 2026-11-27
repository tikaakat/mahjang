"""牌譜（data/kifu/<季>-<連番>.json）を季ごとの1ファイルにまとめる（R2 に置くため）。

  出力: <out>/<季>.pack      各半荘のファイルをそのままつなげたもの
        <out>/<季>.idx.json  {"<季>-<連番>": [開始位置, 長さ], ...}
Worker は idx で位置を調べ、R2 の範囲読み出しで1半荘ぶんだけ取り出す。
使い方: python3 tools/pack_kifu.py <kifuディレクトリ> <出力ディレクトリ>
"""
import json
import os
import re
import sys
from collections import defaultdict


def main(src, out):
    os.makedirs(out, exist_ok=True)
    by_season = defaultdict(list)
    for name in os.listdir(src):
        m = re.fullmatch(r"(\d+)-(\d+)\.json", name)
        if m:
            by_season[int(m.group(1))].append((int(m.group(2)), name))
    total = 0
    for season, items in sorted(by_season.items()):
        idx, pos = {}, 0
        with open(os.path.join(out, f"{season}.pack"), "wb") as pack:
            for _, name in sorted(items):
                data = open(os.path.join(src, name), "rb").read()
                pack.write(data)
                idx[name[:-5]] = [pos, len(data)]
                pos += len(data)
        with open(os.path.join(out, f"{season}.idx.json"), "w") as f:
            json.dump(idx, f, separators=(",", ":"))
        total += len(items)
    print(f"{len(by_season)}季・{total}半荘をまとめました")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
