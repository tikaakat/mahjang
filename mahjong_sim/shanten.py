"""
向聴数（シャンテン数）の計算。
-1 = 和了形、0 = 聴牌、1 = 一向聴 ...
通常手・七対子・国士無双の3形を考慮し、最小値を返す。
"""
from functools import lru_cache

from .tiles import NUM_KINDS, YAOCHU


def _pareto(options):
    """(面子, 塔子, 雀頭) の組のうち、他に完全に劣るものを除く"""
    opts = sorted(set(options), reverse=True)
    kept = []
    for o in opts:
        if not any(k[0] >= o[0] and k[1] >= o[1] and k[2] >= o[2] for k in kept):
            kept.append(o)
    return tuple(kept)


@lru_cache(maxsize=None)
def _suit_options(counts):
    """数牌1色（9要素のタプル）から取れる (面子数, 塔子数, 雀頭有無) の候補"""
    i = 0
    while i < 9 and counts[i] == 0:
        i += 1
    if i == 9:
        return ((0, 0, 0),)

    results = []
    c = list(counts)

    def add(dm, dt, dp):
        for m, t, p in _suit_options(tuple(c)):
            if p + dp <= 1:
                results.append((m + dm, t + dt, p + dp))

    if c[i] >= 3:
        c[i] -= 3
        add(1, 0, 0)
        c[i] += 3
    if i <= 6 and c[i + 1] and c[i + 2]:
        c[i] -= 1; c[i + 1] -= 1; c[i + 2] -= 1
        add(1, 0, 0)
        c[i] += 1; c[i + 1] += 1; c[i + 2] += 1
    if c[i] >= 2:
        c[i] -= 2
        add(0, 0, 1)   # 雀頭として使う
        add(0, 1, 0)   # 対子を塔子として使う
        c[i] += 2
    if i <= 7 and c[i + 1]:
        c[i] -= 1; c[i + 1] -= 1
        add(0, 1, 0)
        c[i] += 1; c[i + 1] += 1
    if i <= 6 and c[i + 2]:
        c[i] -= 1; c[i + 2] -= 1
        add(0, 1, 0)
        c[i] += 1; c[i + 2] += 1
    c[i] -= 1  # 孤立牌として捨てる
    add(0, 0, 0)
    return _pareto(results)


def _honor_options(honors):
    triplets = sum(1 for c in honors if c >= 3)
    pairs = sum(1 for c in honors if c == 2)
    opts = [(triplets, pairs, 0)]
    if pairs:
        opts.append((triplets, pairs - 1, 1))
    return opts


def _combine(a, b):
    return _pareto((x[0] + y[0], x[1] + y[1], x[2] + y[2])
                   for x in a for y in b if x[2] + y[2] <= 1)


def regular_shanten(counts, meld_count=0):
    opts = _suit_options(tuple(counts[0:9]))
    opts = _combine(opts, _suit_options(tuple(counts[9:18])))
    opts = _combine(opts, _suit_options(tuple(counts[18:27])))
    opts = _combine(opts, _honor_options(counts[27:34]))
    best = 8
    for m, t, p in opts:
        mm = m + meld_count
        s = 8 - 2 * mm - min(t, 4 - mm) - p
        if s < best:
            best = s
    return best


def chiitoitsu_shanten(counts):
    pairs = sum(1 for c in counts if c >= 2)
    kinds = sum(1 for c in counts if c >= 1)
    return 6 - pairs + max(0, 7 - kinds)


def kokushi_shanten(counts):
    kinds = sum(1 for t in YAOCHU if counts[t] >= 1)
    has_pair = any(counts[t] >= 2 for t in YAOCHU)
    return 13 - kinds - (1 if has_pair else 0)


@lru_cache(maxsize=400000)
def _shanten_cached(counts, meld_count):
    s = regular_shanten(counts, meld_count)
    if meld_count == 0:
        s = min(s, chiitoitsu_shanten(counts), kokushi_shanten(counts))
    return s


def shanten(counts, meld_count=0):
    return _shanten_cached(tuple(counts), meld_count)


def winning_tiles(counts, meld_count=0):
    """聴牌形（手牌13枚相当）の待ち牌一覧。自分で4枚使っている牌は除く"""
    c = list(counts)
    waits = []
    for t in range(NUM_KINDS):
        if c[t] >= 4:
            continue
        c[t] += 1
        if shanten(c, meld_count) == -1:
            waits.append(t)
        c[t] -= 1
    return waits


def ukeire(counts, meld_count, unseen):
    """有効牌の種類と残り枚数。unseen[t] = 自分から見えていない牌tの枚数"""
    base = shanten(counts, meld_count)
    c = list(counts)
    kinds = []
    total = 0
    for t in range(NUM_KINDS):
        if unseen[t] <= 0:
            continue
        c[t] += 1
        if shanten(c, meld_count) < base:
            kinds.append(t)
            total += unseen[t]
        c[t] -= 1
    return kinds, total
