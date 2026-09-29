"""
自作の点数計算を、実績のある外部ライブラリ `mahjong`（MIT License）とランダムな和了形で突き合わせる。
ライブラリが未インストールの環境ではスキップする（pip install -r requirements-dev.txt）。
"""
import random
import unittest
from dataclasses import replace

from mahjong_sim.rules import RENMEI
from mahjong_sim.scoring import Meld, WinContext, evaluate_win

try:
    from mahjong.hand_calculating.hand import HandCalculator
    from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules, HandConstants
    from mahjong.meld import Meld as LibMeld
    HAS_LIB = True
except ImportError:  # pragma: no cover
    HAS_LIB = False

# ライブラリは連風牌の雀頭を4符で数えるため、比較時はそれに合わせる
RULES = replace(RENMEI, renpuu_pair_fu=4)


def _random_hand(rng):
    """(closed_counts, melds, win_tile) を返す。作れなければ None"""
    counts = [0] * 34
    melds = []
    blocks = []
    for _ in range(4):
        if rng.random() < 0.55:
            s = rng.randrange(3)
            start = s * 9 + rng.randrange(7)
            blocks.append(("shuntsu", start))
        else:
            blocks.append(("koutsu", rng.randrange(34)))
    head = rng.randrange(34)
    used = [0] * 34
    for k, t in blocks:
        for x in ([t, t + 1, t + 2] if k == "shuntsu" else [t, t, t]):
            used[x] += 1
    used[head] += 2
    if max(used) > 4:
        return None

    closed_blocks = []
    for k, t in blocks:
        r = rng.random()
        if k == "shuntsu" and r < 0.3:
            melds.append(Meld("chi", (t, t + 1, t + 2), t, 3))
        elif k == "koutsu" and r < 0.25:
            melds.append(Meld("pon", (t, t, t), t, 1))
        elif k == "koutsu" and r < 0.35 and used[t] == 3:
            kind = rng.choice(["minkan", "ankan"])
            melds.append(Meld(kind, (t, t, t, t), None if kind == "ankan" else t, 2))
            used[t] += 1
        else:
            closed_blocks.append((k, t))
    for k, t in closed_blocks:
        for x in ([t, t + 1, t + 2] if k == "shuntsu" else [t, t, t]):
            counts[x] += 1
    counts[head] += 2
    closed_tiles = [t for t in range(34) for _ in range(counts[t])]
    return counts, melds, rng.choice(closed_tiles)


def _random_chiitoi(rng):
    kinds = rng.sample(range(34), 7)
    counts = [0] * 34
    for t in kinds:
        counts[t] = 2
    return counts, [], rng.choice(kinds)


def _to_lib(counts, melds, win_tile):
    """34種表記を136枚表記に変換する"""
    next_copy = [0] * 34
    def take(t):
        idx = t * 4 + next_copy[t]
        next_copy[t] += 1
        return idx
    lib_melds = []
    tiles136 = []
    for m in melds:
        ids = [take(t) for t in m.tiles]
        tiles136 += ids
        mtype = {"chi": LibMeld.CHI, "pon": LibMeld.PON}.get(m.kind, LibMeld.KAN)
        lib_melds.append(LibMeld(meld_type=mtype, tiles=ids, opened=m.kind != "ankan"))
    win136 = None
    for t in range(34):
        for _ in range(counts[t]):
            i = take(t)
            tiles136.append(i)
            if t == win_tile and win136 is None:
                win136 = i
    return tiles136, lib_melds, win136


@unittest.skipUnless(HAS_LIB, "mahjong ライブラリが必要です")
class CrossCheckTest(unittest.TestCase):
    def test_random_hands_match_library(self):
        rng = random.Random(20260928)
        calc = HandCalculator()
        options = OptionalRules(has_open_tanyao=True, has_aka_dora=False, has_double_yakuman=True,
                                kazoe_limit=HandConstants.KAZOE_SANBAIMAN, kiriage=False,
                                fu_for_open_pinfu=True, fu_for_pinfu_tsumo=False)
        checked = 0
        mismatches = []
        while checked < 3000:
            made = _random_chiitoi(rng) if rng.random() < 0.05 else _random_hand(rng)
            if made is None:
                continue
            counts, melds, win_tile = made
            menzen = all(m.kind == "ankan" for m in melds)
            is_tsumo = rng.random() < 0.4
            riichi = menzen and rng.random() < 0.5
            seat_wind = 27 + rng.randrange(4)
            round_wind = 27 + rng.randrange(2)
            dora_ind = rng.randrange(34)

            ctx = WinContext(closed_counts=counts, melds=melds, win_tile=win_tile, is_tsumo=is_tsumo,
                             seat_wind=seat_wind, round_wind=round_wind, is_dealer=seat_wind == 27,
                             riichi=riichi, dora_indicators=[dora_ind], rules=RULES)
            mine = evaluate_win(ctx)

            tiles136, lib_melds, win136 = _to_lib(counts, melds, win_tile)
            cfg = HandConfig(is_tsumo=is_tsumo, is_riichi=riichi, player_wind=seat_wind,
                             round_wind=round_wind, options=options)
            lib = calc.estimate_hand_value(tiles136, win136, melds=lib_melds,
                                           dora_indicators=[dora_ind * 4 + 3], config=cfg)
            checked += 1
            lib_ok = lib.error is None
            if (mine is not None) != lib_ok:
                mismatches.append(("win?", counts, melds, win_tile, is_tsumo, mine and mine.yaku, lib.error or lib.yaku))
                continue
            if not lib_ok:
                continue
            if mine.yakuman or lib.han >= 13 and lib.yaku and any(y.is_yakuman for y in lib.yaku):
                if not (mine.yakuman and any(y.is_yakuman for y in lib.yaku)):
                    mismatches.append(("yakuman", counts, melds, win_tile, mine.yaku, lib.yaku))
                continue
            if (mine.han, mine.fu) != (lib.han, lib.fu):
                mismatches.append(("han/fu", counts, melds, win_tile, is_tsumo, (mine.han, mine.fu, mine.yaku),
                                   (lib.han, lib.fu, lib.yaku)))
        self.assertEqual(mismatches[:5], [], f"{len(mismatches)} 件の不一致")


if __name__ == "__main__":
    unittest.main()
