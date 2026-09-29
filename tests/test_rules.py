import random
import unittest

from mahjong_sim.tiles import parse_tiles, to_counts, EAST, SOUTH, dora_from_indicator
from mahjong_sim.shanten import shanten, winning_tiles
from mahjong_sim.scoring import WinContext, Meld, evaluate_win
from mahjong_sim.game import Game, final_placement
from mahjong_sim.rules import RENMEI, TENHOU_LIKE
from mahjong_sim.ai import MahjongAI
from mahjong_sim.play import BENCHMARK_PARAMS


def c(text):
    return to_counts(parse_tiles(text))


def win(text, win_tile, tsumo=False, melds=None, dealer=False, riichi=False, seat=EAST, rnd=EAST, dora=None):
    ctx = WinContext(closed_counts=c(text), melds=melds or [], win_tile=parse_tiles(win_tile)[0],
                     is_tsumo=tsumo, seat_wind=seat, round_wind=rnd, is_dealer=dealer, riichi=riichi,
                     dora_indicators=parse_tiles(dora) if dora else [])
    return evaluate_win(ctx)


class ShantenTest(unittest.TestCase):
    def test_complete(self):
        self.assertEqual(shanten(c("123m456p789s111s東東")), -1)

    def test_tenpai(self):
        self.assertEqual(shanten(c("123m456p789s11s東東")), 0)
        self.assertEqual(sorted(winning_tiles(c("123m456p789s23s東東"))), parse_tiles("14s"))

    def test_chiitoitsu_and_kokushi(self):
        self.assertEqual(shanten(c("1122m3344p5566s東")), 0)
        self.assertEqual(shanten(c("19m19p19s東南西北白發中")), 0)
        self.assertEqual(len(winning_tiles(c("19m19p19s東南西北白發中"))), 13)

    def test_one_shanten(self):
        self.assertEqual(shanten(c("123m456p78s東東南西北")), 2)
        self.assertEqual(shanten(c("123m456p789s1s3s東南")), 1)

    def test_with_melds(self):
        self.assertEqual(shanten(c("123m45p東東"), 2), 0)


class ScoringTest(unittest.TestCase):
    def test_pinfu_tsumo(self):
        r = win("234m567p345s678s55m", "8s", tsumo=True)
        names = [n for n, _ in r.yaku]
        self.assertIn("平和", names)
        self.assertIn("門前清自摸和", names)
        self.assertIn("断么九", names)
        self.assertEqual(r.fu, 20)
        self.assertEqual(r.han, 3)

    def test_mangan_ron(self):
        r = win("111222333m456p東東", "東", riichi=True, dealer=False, seat=SOUTH)
        # 三暗刻（ロンした東は対子→単騎ではなくシャンポン…ここでは東は雀頭なので三暗刻成立）
        self.assertIsNotNone(r)
        self.assertTrue(r.han >= 3)

    def test_no_yaku_open(self):
        melds = [Meld("chi", tuple(parse_tiles("123m")), parse_tiles("1m")[0], 3)]
        r = win("456p789s11s東東", "東", melds=melds, seat=SOUTH, rnd=SOUTH)
        # 東は場風でも自風でもない → 役なし
        self.assertIsNone(r)

    def test_yakuhai_open(self):
        melds = [Meld("pon", tuple(parse_tiles("中中中")), parse_tiles("中")[0], 3)]
        r = win("456p789s11s123m", "1m", melds=melds, seat=SOUTH)
        self.assertEqual([n for n, _ in r.yaku], ["役牌 中"])
        self.assertEqual(r.ron_points(False), 1000)

    def test_chiitoitsu(self):
        r = win("1122m3344p5566s東東", "東")
        self.assertEqual(r.fu, 25)
        self.assertIn("七対子", [n for n, _ in r.yaku])

    def test_kokushi(self):
        r = win("19m19p19s東南西北白發中中", "中")
        self.assertEqual(r.yakuman, 1)
        self.assertEqual(r.ron_points(True), 48000)

    def test_dora(self):
        self.assertEqual(dora_from_indicator(parse_tiles("9m")[0]), parse_tiles("1m")[0])
        self.assertEqual(dora_from_indicator(parse_tiles("北")[0]), parse_tiles("東")[0])
        self.assertEqual(dora_from_indicator(parse_tiles("中")[0]), parse_tiles("白")[0])
        r = win("234m567p345s678s55m", "8s", tsumo=True, dora="4m")
        self.assertIn(("ドラ", 2), r.yaku)


class RenmeiRuleTest(unittest.TestCase):
    def test_no_ippatsu_no_ura(self):
        ctx = WinContext(closed_counts=c("234m567p345s678s55m"), melds=[], win_tile=parse_tiles("8s")[0],
                         is_tsumo=False, seat_wind=SOUTH, round_wind=EAST, is_dealer=False, riichi=True,
                         ippatsu=True, dora_indicators=[], ura_indicators=parse_tiles("4m"))
        names = [n for n, _ in evaluate_win(ctx).yaku]
        self.assertNotIn("一発", names)
        self.assertNotIn("裏ドラ", names)

    def test_kazoe_capped_at_sanbaiman(self):
        # 清一色・一気通貫・リーチ・ツモ・ドラ多数でも三倍満止まり
        ctx = WinContext(closed_counts=c("12345678923455m"), melds=[], win_tile=0, is_tsumo=True,
                         seat_wind=SOUTH, round_wind=EAST, is_dealer=False, riichi=True,
                         dora_indicators=parse_tiles("4m"))
        r = evaluate_win(ctx)
        self.assertGreaterEqual(r.han, 13)
        self.assertEqual(r.yakuman, 0)
        self.assertEqual(r.base, 6000)

    def test_ankan_fu(self):
        melds = [Meld("ankan", (0, 0, 0, 0), None, 0)]
        ctx = WinContext(closed_counts=c("234p567s東東西西西"), melds=melds, win_tile=parse_tiles("4p")[0],
                         is_tsumo=True, seat_wind=SOUTH, round_wind=EAST, is_dealer=False, riichi=True)
        r = evaluate_win(ctx)
        # 20 + ツモ2 + 暗槓么九32 + 西暗刻8 + 雀頭(場風東)2 = 64 → 70符
        self.assertEqual(r.fu, 70)

    def test_tie_splits_uma(self):
        res = final_placement([40000, 30000, 30000, 20000], RENMEI)
        self.assertEqual(res["placement"], [1, 2, 2, 4])
        self.assertEqual(res["points"], [25.0, 0.0, 0.0, -25.0])

    def test_tenhou_like_oka(self):
        res = final_placement([40000, 30000, 20000, 10000], TENHOU_LIKE)
        self.assertEqual(res["points"], [60.0, 10.0, -20.0, -50.0])


class GameTest(unittest.TestCase):
    def test_full_game_runs_and_points_are_conserved(self):
        rng = random.Random(1)
        for level in (1, 3, 5):
            agents = [MahjongAI(BENCHMARK_PARAMS, skill=level) for _ in range(4)]
            result = Game(agents, length="east", rng=rng).run()
            self.assertEqual(sum(result["final_scores"]), 120000)
            self.assertEqual(sorted(result["placement"]), [1, 2, 3, 4])
            self.assertAlmostEqual(sum(result["points"]), 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
