"""
4人打ちリーチ麻雀の対局進行。

ルールの簡略化（README「既知の制約」も参照）:
  - 赤ドラなし・カンなし（槓ドラ・嶺上開花なし）
  - 途中流局（九種九牌・四風連打など）なし、流し満貫なし
  - ダブロンなし（頭ハネ：放銃者の下家から順に優先）
  - 喰い替えは「鳴いた牌と同じ牌を同巡に切れない」のみ禁止
  - オーラス親の和了止め・聴牌止めあり、西入なし、飛び終了あり
"""
import random

from .tiles import NUM_KINDS, EAST, new_wall, tile_name, dora_from_indicator
from .shanten import shanten, winning_tiles
from .scoring import Meld, WinContext, evaluate_win

START_SCORE = 25000
RETURN_SCORE = 30000
UMA = (30, 10, -10, -30)
OKA = (RETURN_SCORE - START_SCORE) * 4 // 1000  # トップ賞（千点単位）
ROUND_NAMES = ["東1局", "東2局", "東3局", "東4局", "南1局", "南2局", "南3局", "南4局"]


class RoundState:
    """1局分の状態。AIはこのオブジェクトから「自分の手牌」と「公開情報」だけを読む"""

    def __init__(self, scores, round_index, dealer, honba, riichi_sticks, rng):
        self.scores = scores
        self.round_index = round_index
        self.round_wind = EAST + round_index // 4
        self.dealer = dealer
        self.honba = honba
        self.riichi_sticks = riichi_sticks

        wall = new_wall(rng)
        self.dead_wall = wall[:14]
        self.live_wall = wall[14:]
        self.dora_indicators = [self.dead_wall[0]]
        self.ura_indicators = [self.dead_wall[1]]

        self.hands = [[0] * NUM_KINDS for _ in range(4)]
        self.melds = [[] for _ in range(4)]
        self.discards = [[] for _ in range(4)]       # [{"tile", "tsumogiri", "riichi", "called"}]
        self.discard_sets = [set() for _ in range(4)]  # 自分の捨て牌（鳴かれた牌も含む：フリテン判定用）
        self.riichi = [False] * 4
        self.double_riichi = [False] * 4
        self.ippatsu = [False] * 4
        self.riichi_furiten = [False] * 4
        self.temp_furiten = [False] * 4
        self.safe_after_riichi = [set() for _ in range(4)]  # リーチ後に他家から出て通った牌
        self.any_call = False
        self.last_drawn = None

        for _ in range(13):
            for i in range(4):
                seat = (dealer + i) % 4
                self.hands[seat][self.live_wall.pop()] += 1

    # ---------------- 公開情報のヘルパー ----------------
    def seat_wind(self, seat):
        return EAST + (seat - self.dealer) % 4

    def tiles_left(self):
        return len(self.live_wall)

    def dora_tiles(self):
        return [dora_from_indicator(i) for i in self.dora_indicators]

    def public_visible_counts(self):
        """全員に見えている牌（河・副露・ドラ表示牌）の枚数"""
        vis = [0] * NUM_KINDS
        for s in range(4):
            for d in self.discards[s]:
                if not d["called"]:
                    vis[d["tile"]] += 1
            for m in self.melds[s]:
                for t in m.tiles:
                    vis[t] += 1
        for t in self.dora_indicators:
            vis[t] += 1
        return vis

    def genbutsu(self, target):
        """target にとっての現物（ロンされない牌）"""
        return self.discard_sets[target] | self.safe_after_riichi[target]

    def is_menzen(self, seat):
        return not self.melds[seat]

    # ---------------- 和了判定 ----------------
    def win_result(self, seat, tile, is_tsumo):
        counts = list(self.hands[seat])
        if not is_tsumo:
            counts[tile] += 1
        ctx = WinContext(
            closed_counts=counts, melds=self.melds[seat], win_tile=tile, is_tsumo=is_tsumo,
            seat_wind=self.seat_wind(seat), round_wind=self.round_wind,
            is_dealer=(seat == self.dealer),
            riichi=self.riichi[seat] and not self.double_riichi[seat],
            double_riichi=self.double_riichi[seat], ippatsu=self.ippatsu[seat],
            haitei=is_tsumo and self.tiles_left() == 0,
            houtei=(not is_tsumo) and self.tiles_left() == 0,
            dora_indicators=self.dora_indicators, ura_indicators=self.ura_indicators,
        )
        return evaluate_win(ctx)

    def is_furiten(self, seat):
        if self.riichi_furiten[seat] or self.temp_furiten[seat]:
            return True
        waits = winning_tiles(self.hands[seat], len(self.melds[seat]))
        return any(w in self.discard_sets[seat] for w in waits)


class Game:
    """1半荘（または東風戦）を進行する"""

    def __init__(self, agents, length="east", rng=None, log=False):
        assert len(agents) == 4
        self.agents = agents
        self.rng = rng or random.Random()
        self.last_round = 3 if length == "east" else 7
        self.verbose = log
        self.scores = [START_SCORE] * 4
        self.rounds = []

    def _say(self, msg):
        if self.verbose:
            print(msg)

    def run(self):
        round_index, honba, sticks = 0, 0, 0
        for _ in range(40):  # 連荘が異常に続いた場合の安全弁
            dealer = round_index % 4
            rs = RoundState(self.scores, round_index, dealer, honba, sticks, self.rng)
            self._say(f"--- {ROUND_NAMES[round_index]} {honba}本場（供託{sticks}） 点数 {self.scores} ---")
            result = self._play_round(rs)
            sticks = rs.riichi_sticks
            result.update({"round": ROUND_NAMES[round_index], "honba": honba})
            self.rounds.append(result)

            renchan = result["dealer_keeps"]
            if min(self.scores) < 0:
                break
            if renchan:
                is_all_last = round_index == self.last_round
                top = max(range(4), key=lambda s: (self.scores[s], -s))
                if is_all_last and top == dealer and self.scores[dealer] >= RETURN_SCORE:
                    break  # 和了止め・聴牌止め
                honba += 1
            else:
                honba = honba + 1 if result["type"] == "draw" else 0
                round_index += 1
                if round_index > self.last_round:
                    break

        # 残った供託はトップへ
        ranks = sorted(range(4), key=lambda s: (-self.scores[s], s))
        self.scores[ranks[0]] += sticks * 1000
        ranks = sorted(range(4), key=lambda s: (-self.scores[s], s))
        placement = [0] * 4
        points = [0.0] * 4
        for r, s in enumerate(ranks):
            placement[s] = r + 1
            points[s] = round((self.scores[s] - RETURN_SCORE) / 1000 + UMA[r] + (OKA if r == 0 else 0), 1)
        return {"final_scores": list(self.scores), "placement": placement, "points": points, "rounds": self.rounds}

    # ============================================================
    # 1局の進行
    # ============================================================
    def _play_round(self, rs):
        current = rs.dealer
        need_draw = True
        forbidden = None
        discard_counts = [0] * 4

        while True:
            drawn = None
            if need_draw:
                if not rs.live_wall:
                    return self._exhaustive_draw(rs)
                drawn = rs.live_wall.pop()
                rs.hands[current][drawn] += 1
                rs.last_drawn = drawn
                res = rs.win_result(current, drawn, is_tsumo=True)
                if res and self.agents[current].decide_tsumo(rs, current, drawn, res):
                    return self._settle_tsumo(rs, current, drawn, res)

            # ---- 打牌 ----
            declare = False
            if rs.riichi[current] and drawn is not None:
                discard = drawn
            else:
                discard, declare = self.agents[current].choose_discard(rs, current, drawn, forbidden)
                if rs.hands[current][discard] <= 0:
                    raise RuntimeError(f"AI {current} が手牌にない牌 {tile_name(discard)} を切ろうとしました")
                if declare and not self._can_riichi(rs, current, discard):
                    declare = False
            forbidden = None

            rs.hands[current][discard] -= 1
            rs.discards[current].append({"tile": discard, "tsumogiri": discard == drawn, "riichi": declare, "called": False})
            rs.discard_sets[current].add(discard)
            rs.temp_furiten[current] = False
            if rs.riichi[current]:
                rs.ippatsu[current] = False
            if declare:
                rs.riichi[current] = True
                rs.ippatsu[current] = True
                rs.double_riichi[current] = discard_counts[current] == 0 and not rs.any_call
                self._say(f"  {current}家 リーチ（宣言牌 {tile_name(discard)}）")
            discard_counts[current] += 1

            # ---- ロン判定（頭ハネ） ----
            for i in range(1, 4):
                seat = (current + i) % 4
                if shanten(rs.hands[seat], len(rs.melds[seat])) != 0:
                    continue
                waits = winning_tiles(rs.hands[seat], len(rs.melds[seat]))
                if discard not in waits:
                    continue
                res = None if rs.is_furiten(seat) else rs.win_result(seat, discard, is_tsumo=False)
                if res and self.agents[seat].decide_ron(rs, seat, discard, current, res):
                    return self._settle_ron(rs, seat, current, discard, res)
                # 見逃し・役なし → 同巡内フリテン（リーチ中は永久フリテン）
                rs.temp_furiten[seat] = True
                if rs.riichi[seat]:
                    rs.riichi_furiten[seat] = True

            for s in range(4):
                if s != current and rs.riichi[s]:
                    rs.safe_after_riichi[s].add(discard)

            if declare:
                self.scores[current] -= 1000
                rs.riichi_sticks += 1

            # ---- 鳴き判定（ポン優先 → チー）。河底牌は鳴けない ----
            called = False
            if rs.live_wall:
                called, caller = self._handle_calls(rs, current, discard)
                if called:
                    rs.discards[current][-1]["called"] = True
                    rs.any_call = True
                    rs.ippatsu = [False] * 4
                    current = caller
                    need_draw = False
                    forbidden = discard
                    continue

            current = (current + 1) % 4
            need_draw = True

    def _can_riichi(self, rs, seat, discard):
        if rs.riichi[seat] or not rs.is_menzen(seat):
            return False
        if self.scores[seat] < 1000 or rs.tiles_left() < 4:
            return False
        hand = list(rs.hands[seat])
        hand[discard] -= 1
        return shanten(hand, 0) == 0

    def _handle_calls(self, rs, discarder, tile):
        # ポン（どの他家からでも可）
        for i in range(1, 4):
            seat = (discarder + i) % 4
            if rs.riichi[seat] or rs.hands[seat][tile] < 2:
                continue
            option = ("pon", (tile, tile, tile))
            if self.agents[seat].decide_call(rs, seat, tile, discarder, [option]):
                self._make_meld(rs, seat, "pon", (tile, tile, tile), tile, discarder)
                return True, seat
        # チー（下家のみ）
        seat = (discarder + 1) % 4
        if tile < 27 and not rs.riichi[seat]:
            options = []
            n = tile % 9
            hand = rs.hands[seat]
            for start in (tile - 2, tile - 1, tile):
                if start < tile - n or start + 2 > tile - n + 8:
                    continue
                others = [t for t in (start, start + 1, start + 2) if t != tile]
                if all(hand[t] >= 1 for t in others):
                    options.append(("chi", (start, start + 1, start + 2)))
            if options:
                choice = self.agents[seat].decide_call(rs, seat, tile, discarder, options)
                if choice:
                    self._make_meld(rs, seat, "chi", choice[1], tile, discarder)
                    return True, seat
        return False, None

    def _make_meld(self, rs, seat, kind, tiles, called_tile, from_seat):
        used = list(tiles)
        used.remove(called_tile)
        for t in used:
            rs.hands[seat][t] -= 1
        rs.melds[seat].append(Meld(kind, tuple(tiles), called_tile, from_seat))
        self._say(f"  {seat}家 {'ポン' if kind == 'pon' else 'チー'} {' '.join(tile_name(t) for t in tiles)}")

    # ============================================================
    # 精算
    # ============================================================
    def _settle_tsumo(self, rs, winner, tile, res):
        deltas = [0] * 4
        is_dealer = winner == rs.dealer
        from_dealer, from_child = res.tsumo_points(is_dealer)
        for s in range(4):
            if s == winner:
                continue
            pay = (from_dealer if s == rs.dealer else from_child) + 100 * rs.honba
            deltas[s] -= pay
            deltas[winner] += pay
        deltas[winner] += rs.riichi_sticks * 1000
        rs.riichi_sticks = 0
        self._apply(deltas)
        self._say(f"  {winner}家 ツモ {tile_name(tile)} {res.label()} {[n for n, _ in res.yaku]} → {deltas}")
        return {"type": "tsumo", "winner": winner, "loser": None, "tile": tile, "win": res.to_dict(),
                "deltas": deltas, "dealer_keeps": is_dealer, "riichi": list(rs.riichi)}

    def _settle_ron(self, rs, winner, loser, tile, res):
        deltas = [0] * 4
        is_dealer = winner == rs.dealer
        pay = res.ron_points(is_dealer) + 300 * rs.honba
        deltas[loser] -= pay
        deltas[winner] += pay + rs.riichi_sticks * 1000
        rs.riichi_sticks = 0
        self._apply(deltas)
        self._say(f"  {winner}家 ロン {tile_name(tile)}（{loser}家から） {res.label()} {[n for n, _ in res.yaku]} → {deltas}")
        return {"type": "ron", "winner": winner, "loser": loser, "tile": tile, "win": res.to_dict(),
                "deltas": deltas, "dealer_keeps": is_dealer, "riichi": list(rs.riichi)}

    def _exhaustive_draw(self, rs):
        tenpai = [shanten(rs.hands[s], len(rs.melds[s])) == 0 for s in range(4)]
        n = sum(tenpai)
        deltas = [0] * 4
        if 0 < n < 4:
            for s in range(4):
                deltas[s] = 3000 // n if tenpai[s] else -3000 // (4 - n)
        self._apply(deltas)
        self._say(f"  流局 聴牌={tenpai} → {deltas}")
        return {"type": "draw", "winner": None, "loser": None, "tenpai": tenpai,
                "deltas": deltas, "dealer_keeps": tenpai[rs.dealer], "riichi": list(rs.riichi)}

    def _apply(self, deltas):
        for s in range(4):
            self.scores[s] += deltas[s]
