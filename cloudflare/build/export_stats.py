"""集計API（server/api/stats.php）を PHP の組み込みサーバーで動かし、全パターンの結果を JSON に書き出す。
使い方: python3 export_stats.py <ベースURL> <出力ディレクトリ> <公開済みの最新季>"""
import json
import sys
import urllib.request

base, out, latest = sys.argv[1], sys.argv[2], int(sys.argv[3])


def get(q):
    with urllib.request.urlopen(f"{base}/api/stats.php?{q}", timeout=300) as r:
        return r.read()


import os
os.makedirs(out, exist_ok=True)
n = 0
for t in ("players", "yakuman", "big_hands", "yaku", "scores"):
    for season in ["all"] + list(range(1, latest + 1)):
        q = f"type={t}" + ("&min_hands=0" if t == "players" else "") + ("" if season == "all" else f"&season={season}")
        body = get(q)
        json.loads(body)
        open(f"{out}/{t}-{season}.json", "wb").write(body)
        n += 1
for t in ("titles", "clans"):
    body = get(f"type={t}")
    json.loads(body)
    open(f"{out}/{t}-all.json", "wb").write(body)
    n += 1
print(f"{n} files")
