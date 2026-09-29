"""
4人打ちリーチ麻雀の対局進行。ルールは RuleSet（既定：日本プロ麻雀連盟 公式ルール）に従う。

対応: ツモ・打牌・リーチ・チー・ポン・大明槓・暗槓・加槓・嶺上開花・槍槓・ロン（頭ハネ）・
      フリテン（捨て牌／同巡／リーチ後）・喰い替え禁止（現物・筋）・天和・地和・流局（聴牌料）・
      流し満貫・責任払い（大三元・大四喜・四槓子）・連荘・本場・供託
非対応: 赤ドラ（連盟ルールでは不要）、途中流局（連盟ルールでは採用なし）
"""
import random

from .tiles import NUM_KINDS, EAST, new_wall, tile_name, dora_from_indicator, is_yaochu, WINDS, DRAGONS
from .shanten import shanten, winning_tiles
from .scoring import Meld, WinContext, evaluate_win
from .rules import RENMEI

AKA_KINDS = (4, 13, 22)   # 赤ドラになりうる牌（五萬・五筒・五索）。各1枚が赤

ROUND_NAMES = ["東1局", "東2局", "東3局", "東4局", "南1局", "南2局", "南3局", "南4局"]


class RoundState:
    """1局分の状態。AIはこのオブジェクトから「自分の手牌」と「公開情報」だけを読む"""

    def __init__(self, scores, round_index, dealer, honba, riichi_sticks, rng, rules):
        self.rules = rules
        self.scores = scores
        self.round_index = round_index
        self.round_wind = EAST + round_index // 4
        self.dealer = dealer
        self.honba = honba
        self.riichi_sticks = riichi_sticks

        self.rules = rules
        wall = new_wall(rng)
        red = [False] * len(wall)
        if rules.aka:
            for k in AKA_KINDS:
                red[wall.index(k)] = True
        self.dead_wall = wall[:14]
        self.live_wall = wall[14:]
        self.live_red = red[14:]                       # live_wall と同じ並びで「赤5か」
        self.rinshan = self.dead_wall[:4]
        self.rinshan_red = red[:4]
        self.dora_indicators = [self.dead_wall[4]]
        self.ura_indicators = [self.dead_wall[5]]
        self.kan_count = 0

        self.hands = [[0] * NUM_KINDS for _ in range(4)]
        self.melds = [[] for _ in range(4)]
        self.discards = [[] for _ in range(4)]       # [{"tile", "tsumogiri", "riichi", "called"}]
        self.discard_sets = [set() for _ in range(4)]  # 自分の捨て牌（鳴かれた牌も含む：フリテン判定用）
        self.riichi = [False] * 4
        self.double_riichi = [False] * 4
        self.ippatsu = [False] * 4
        self.riichi_furiten = [False] * 4
        self.temp_furiten = [False] * 4
        self.safe_after_riichi = [set() for _ in range(4)]
        self.nagashi_ok = [True] * 4                   # 流し満貫の権利（么九牌のみ・鳴かれていない）
        self.pao = [None] * 4                          # 責任払いの相手
        self.any_call = False
        self.discard_counts = [0] * 4
        self.events = []                               # 牌譜（簡易mjai形式）
        self.hand_red = [[0, 0, 0] for _ in range(4)]  # 手牌中の赤5の枚数（萬・筒・索）
        self.meld_red = [0] * 4                        # 副露中の赤5の枚数

        for _ in range(13):
            for i in range(4):
                seat = (dealer + i) % 4
                t, r = self.live_wall.pop(), self.live_red.pop()
                self.hands[seat][t] += 1
                if r:
                    self.hand_red[seat][t // 9] += 1
        self.events.append({"type": "start_kyoku", "bakaze": self.round_wind, "kyoku": round_index % 4 + 1,
                            "honba": honba, "kyotaku": riichi_sticks, "oya": dealer,
                            "dora_marker": self.dora_indicators[0], "scores": list(scores),
                            "tehais": [[t for t in range(NUM_KINDS) for _ in range(self.hands[s][t])] for s in range(4)],
                            "aka": [[k for k in AKA_KINDS if self.hand_red[s][k // 9]] for s in range(4)]})

    # ---------------- 赤ドラ・槓ドラ ----------------
    def aka_count(self, seat):
        return sum(self.hand_red[seat]) + self.meld_red[seat]

    def red_in_hand(self, seat, t):
        return t in AKA_KINDS and self.hand_red[seat][t // 9] > 0

    def take_red(self, seat, t, prefer_red):
        """手牌から t を1枚出すとき、それが赤5かを決めて手牌の赤の枚数を減らす。
        prefer_red=False（打牌）は普通の5を先に出し、True（鳴き・槓）は赤を先に使う"""
        if not self.red_in_hand(seat, t):
            return False
        red = prefer_red or self.hands[seat][t] <= self.hand_red[seat][t // 9]
        if red:
            self.hand_red[seat][t // 9] -= 1
        return red

    def reveal_kan_dora(self):
        """槓のたびに新しいドラ表示牌（と裏ドラ表示牌）をめくる"""
        if not self.rules.kan_dora:
            return
        k = len(self.dora_indicators)
        if 5 + 2 * k < len(self.dead_wall):
            self.dora_indicators.append(self.dead_wall[4 + 2 * k])
            self.ura_indicators.append(self.dead_wall[5 + 2 * k])
            self.events.append({"type": "dora", "dora_marker": self.dora_indicators[-1]})

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
        return self.discard_sets[target] | self.safe_after_riichi[target]

    def is_menzen(self, seat):
        return all(not m.is_open for m in self.melds[seat])

    def meld_count(self, seat):
        return len(self.melds[seat])

    # ---------------- 和了判定 ----------------
    def win_result(self, seat, tile, is_tsumo, rinshan=False, chankan=False, ron_red=False):
        counts = list(self.hands[seat])
        aka = (self.aka_count(seat) + (1 if ron_red and not is_tsumo else 0)) if self.rules.aka else 0
        if not is_tsumo:
            counts[tile] += 1
        first_turn = self.discard_counts[seat] == 0 and not self.any_call and is_tsumo
        ctx = WinContext(
            closed_counts=counts, melds=self.melds[seat], win_tile=tile, is_tsumo=is_tsumo,
            seat_wind=self.seat_wind(seat), round_wind=self.round_wind,
            is_dealer=(seat == self.dealer),
            riichi=self.riichi[seat] and not self.double_riichi[seat],
            double_riichi=self.double_riichi[seat], ippatsu=self.ippatsu[seat],
            haitei=is_tsumo and self.tiles_left() == 0 and not rinshan,
            houtei=(not is_tsumo) and self.tiles_left() == 0,
            rinshan=rinshan, chankan=chankan,
            tenhou=first_turn and seat == self.dealer,
            chiihou=first_turn and seat != self.dealer,
            dora_indicators=self.dora_indicators, ura_indicators=self.ura_indicators,
            rules=self.rules, aka=aka,
        )
        return evaluate_win(ctx)

    def is_furiten(self, seat):
        if self.riichi_furiten[seat] or self.temp_furiten[seat]:
            return True
        waits = winning_tiles(self.hands[seat], self.meld_count(seat))
        return any(w in self.discard_sets[seat] for w in waits)

    def is_tenpai(self, seat):
        return (shanten(self.hands[seat], self.meld_count(seat)) == 0
                and len(winning_tiles(self.hands[seat], self.meld_count(seat))) > 0)


class Game:
    """1半荘（または東風戦）を進行する"""

    def __init__(self, agents, rules=RENMEI, rng=None, log=False, length=None):
        assert len(agents) == 4
        self.agents = agents
        self.rules = rules
        self.rng = rng or random.Random()
        length = length or rules.game_length
        self.last_round = 3 if length == "east" else 7
        self.verbose = log
        self.scores = [rules.start_score] * 4
        self.rounds = []

    def _say(self, msg):
        if self.verbose:
            print(msg)

    def run(self):
        round_index, honba, sticks = 0, 0, 0
        for _ in range(60):  # 連荘が異常に続いた場合の安全弁
            dealer = round_index % 4
            rs = RoundState(self.scores, round_index, dealer, honba, sticks, self.rng, self.rules)
            self._say(f"--- {ROUND_NAMES[round_index]} {honba}本場（供託{sticks}） 点数 {self.scores} ---")
            result = self._play_round(rs)
            sticks = rs.riichi_sticks
            result.update({"round": ROUND_NAMES[round_index], "honba": honba, "events": rs.events})
            self.rounds.append(result)

            renchan = result["dealer_keeps"]
            if self.rules.tobi and min(self.scores) < 0:
                break
            if renchan:
                is_all_last = round_index == self.last_round
                top = max(range(4), key=lambda s: (self.scores[s], -s))
                if (self.rules.agari_yame and is_all_last and top == dealer
                        and self.scores[dealer] >= self.rules.return_score):
                    break
                honba += 1
            else:
                honba = honba + 1 if result["type"] in ("draw", "nagashi") else 0
                round_index += 1
                if round_index > self.last_round:
                    break

        # 残った供託はトップへ
        order = sorted(range(4), key=lambda s: (-self.scores[s], s))
        self.scores[order[0]] += sticks * 1000
        return {"final_scores": list(self.scores), **final_placement(self.scores, self.rules),
                "rounds": self.rounds}

    # ============================================================
    # 1局の進行
    # ============================================================
    def _play_round(self, rs):
        current = rs.dealer
        draw_mode = "live"   # "live" / "rinshan" / None（鳴いた直後で打牌のみ）
        forbidden = set()

        while True:
            drawn = None
            drawn_red = False
            is_rinshan = False
            if draw_mode == "live":
                if not rs.live_wall:
                    return self._exhaustive_draw(rs)
                drawn, drawn_red = rs.live_wall.pop(), rs.live_red.pop()
            elif draw_mode == "rinshan":
                drawn, drawn_red = rs.rinshan.pop(), rs.rinshan_red.pop()
                rs.live_wall.pop(0)  # 王牌を14枚に保つため、海底側が1枚繰り上がる
                rs.live_red.pop(0)
                is_rinshan = True
            if drawn is not None:
                rs.hands[current][drawn] += 1
                if drawn_red:
                    rs.hand_red[current][drawn // 9] += 1
                rs.events.append({"type": "tsumo", "actor": current, "pai": drawn, "red": drawn_red})
                res = rs.win_result(current, drawn, is_tsumo=True, rinshan=is_rinshan)
                if res and self.agents[current].decide_tsumo(rs, current, drawn, res):
                    return self._settle_tsumo(rs, current, drawn, res)

                # ---- 暗槓・加槓 ----
                kan = self._self_kan(rs, current, drawn)
                if kan == "chankan":
                    return rs._chankan_result
                if kan:
                    draw_mode = "rinshan"
                    continue

            # ---- 打牌 ----
            declare = False
            if rs.riichi[current] and drawn is not None:
                discard = drawn
            else:
                discard, declare = self.agents[current].choose_discard(rs, current, drawn, forbidden)
                if rs.hands[current][discard] <= 0:
                    raise RuntimeError(f"AI {current} が手牌にない牌 {tile_name(discard)} を切ろうとしました")
                if discard in forbidden and any(rs.hands[current][t] > 0 for t in range(NUM_KINDS) if t not in forbidden):
                    raise RuntimeError(f"AI {current} が喰い替え禁止の牌 {tile_name(discard)} を切ろうとしました")
                if declare and not self._can_riichi(rs, current, discard):
                    declare = False
            forbidden = set()
            self._do_discard(rs, current, discard, drawn, declare, drawn_red)

            # ---- ロン判定（頭ハネ） ----
            result = self._check_ron(rs, current, discard, red=rs.discards[current][-1]["red"])
            if result:
                return result

            for s in range(4):
                if s != current and rs.riichi[s]:
                    rs.safe_after_riichi[s].add(discard)
            if declare:
                self.scores[current] -= 1000
                rs.riichi_sticks += 1
                rs.events.append({"type": "reach_accepted", "actor": current})

            # ---- 鳴き判定（大明槓・ポン → チー）。河底牌は鳴けない ----
            if rs.live_wall:
                call = self._handle_calls(rs, current, discard)
                if call:
                    caller, kind, forbid = call
                    rs.discards[current][-1]["called"] = True
                    rs.nagashi_ok[current] = False
                    rs.any_call = True
                    rs.ippatsu = [False] * 4
                    current = caller
                    forbidden = forbid
                    draw_mode = "rinshan" if kind == "minkan" else None
                    continue

            current = (current + 1) % 4
            draw_mode = "live"

    def _do_discard(self, rs, seat, discard, drawn, declare, drawn_red=False):
        if discard == drawn and drawn_red and rs.red_in_hand(seat, discard):
            rs.hand_red[seat][discard // 9] -= 1       # ツモ切りした赤5
            red = True
        else:
            red = rs.take_red(seat, discard, prefer_red=False)
        rs.hands[seat][discard] -= 1
        rs.discards[seat].append({"tile": discard, "tsumogiri": discard == drawn, "riichi": declare, "called": False,
                                  "red": red})
        rs.discard_sets[seat].add(discard)
        rs.temp_furiten[seat] = False
        if not is_yaochu(discard):
            rs.nagashi_ok[seat] = False
        if rs.riichi[seat]:
            rs.ippatsu[seat] = False
        if declare:
            rs.riichi[seat] = True
            rs.ippatsu[seat] = True
            rs.double_riichi[seat] = rs.discard_counts[seat] == 0 and not rs.any_call
            rs.events.append({"type": "reach", "actor": seat})
            self._say(f"  {seat}家 リーチ（宣言牌 {tile_name(discard)}）")
        rs.discard_counts[seat] += 1
        rs.events.append({"type": "dahai", "actor": seat, "pai": discard, "tsumogiri": discard == drawn, "red": red})

    def _check_ron(self, rs, discarder, tile, chankan=False, red=False):
        for i in range(1, 4):
            seat = (discarder + i) % 4
            if shanten(rs.hands[seat], rs.meld_count(seat)) != 0:
                continue
            waits = winning_tiles(rs.hands[seat], rs.meld_count(seat))
            if tile not in waits:
                continue
            res = None if rs.is_furiten(seat) else rs.win_result(seat, tile, is_tsumo=False, chankan=chankan,
                                                                 ron_red=red)
            if res and self.agents[seat].decide_ron(rs, seat, tile, discarder, res):
                return self._settle_ron(rs, seat, discarder, tile, res)
            rs.temp_furiten[seat] = True
            if rs.riichi[seat]:
                rs.riichi_furiten[seat] = True
        return None

    def _can_riichi(self, rs, seat, discard):
        if rs.riichi[seat] or not rs.is_menzen(seat):
            return False
        if self.scores[seat] < self.rules.riichi_min_score or rs.tiles_left() < 4:
            return False
        hand = list(rs.hands[seat])
        hand[discard] -= 1
        return shanten(hand, rs.meld_count(seat)) == 0

    # ============================================================
    # 槓
    # ============================================================
    def _self_kan_options(self, rs, seat, drawn):
        if rs.kan_count >= self.rules.max_kans or not rs.live_wall:
            return []
        hand = rs.hands[seat]
        opts = []
        for t in range(NUM_KINDS):
            if hand[t] == 4:
                if rs.riichi[seat]:
                    # リーチ後の暗槓は、ツモ牌で待ちが変わらない場合のみ
                    if t != drawn:
                        continue
                    before = list(hand); before[t] -= 1
                    after = list(hand); after[t] -= 4
                    if winning_tiles(before, rs.meld_count(seat)) != winning_tiles(after, rs.meld_count(seat) + 1):
                        continue
                opts.append(("ankan", t))
        if not rs.riichi[seat]:
            for m in rs.melds[seat]:
                if m.kind == "pon" and hand[m.base] >= 1:
                    opts.append(("kakan", m.base))
        return opts

    def _self_kan(self, rs, seat, drawn):
        opts = self._self_kan_options(rs, seat, drawn)
        if not opts:
            return None
        choice = self.agents[seat].decide_self_kan(rs, seat, opts)
        if not choice:
            return None
        kind, t = choice
        if kind == "ankan":
            red = rs.take_red(seat, t, prefer_red=True)
            rs.meld_red[seat] += red
            rs.hands[seat][t] -= 4
            rs.melds[seat].append(Meld("ankan", (t, t, t, t), None, seat))
        else:
            # 槍槓の判定
            red = rs.take_red(seat, t, prefer_red=True)
            rs.hands[seat][t] -= 1
            rs.events.append({"type": "kakan", "actor": seat, "pai": t, "red": red})
            res = self._check_ron(rs, seat, t, chankan=True, red=red)
            if res:
                rs._chankan_result = res
                return "chankan"
            idx = next(i for i, m in enumerate(rs.melds[seat]) if m.kind == "pon" and m.base == t)
            old = rs.melds[seat][idx]
            rs.melds[seat][idx] = Meld("kakan", (t, t, t, t), old.called_tile, old.from_seat)
            rs.meld_red[seat] += red
        if kind == "ankan":
            rs.events.append({"type": "ankan", "actor": seat, "pai": t, "red": red})
        rs.kan_count += 1
        rs.reveal_kan_dora()
        rs.any_call = True
        rs.ippatsu = [False] * 4
        self._check_pao(rs, seat, None)
        self._say(f"  {seat}家 {'暗槓' if kind == 'ankan' else '加槓'} {tile_name(t)}")
        return kind

    # ============================================================
    # 他家の打牌への鳴き
    # ============================================================
    def _handle_calls(self, rs, discarder, tile):
        can_kan = rs.kan_count < self.rules.max_kans
        for i in range(1, 4):
            seat = (discarder + i) % 4
            if rs.riichi[seat] or rs.hands[seat][tile] < 2:
                continue
            options = [("pon", (tile, tile, tile))]
            if can_kan and rs.hands[seat][tile] >= 3:
                options.append(("minkan", (tile, tile, tile, tile)))
            choice = self.agents[seat].decide_call(rs, seat, tile, discarder, options)
            if choice:
                kind, tiles = choice
                self._make_meld(rs, seat, kind, tiles, tile, discarder)
                if kind == "minkan":
                    rs.kan_count += 1
                    rs.reveal_kan_dora()
                return seat, kind, {tile}
        seat = (discarder + 1) % 4
        if tile < 27 and not rs.riichi[seat]:
            options = []
            n = tile % 9
            base = tile - n
            hand = rs.hands[seat]
            for start in (tile - 2, tile - 1, tile):
                if start < base or start + 2 > base + 8:
                    continue
                others = [t for t in (start, start + 1, start + 2) if t != tile]
                if all(hand[t] >= 1 for t in others):
                    options.append(("chi", (start, start + 1, start + 2)))
            if options:
                choice = self.agents[seat].decide_call(rs, seat, tile, discarder, options)
                if choice:
                    tiles = choice[1]
                    self._make_meld(rs, seat, "chi", tiles, tile, discarder)
                    forbid = {tile}
                    # 筋喰い替え（両面の片側で鳴いて反対側を切る）も禁止
                    if tile == tiles[0] and tiles[2] % 9 < 8:
                        forbid.add(tiles[2] + 1)
                    elif tile == tiles[2] and tiles[0] % 9 > 0:
                        forbid.add(tiles[0] - 1)
                    return seat, "chi", forbid
        return None

    def _make_meld(self, rs, seat, kind, tiles, called_tile, from_seat):
        used = list(tiles)
        used.remove(called_tile)
        called_red = rs.discards[from_seat][-1].get("red", False)
        consumed_red = False
        for t in used:
            if not consumed_red and rs.take_red(seat, t, prefer_red=True):
                consumed_red = True
            rs.hands[seat][t] -= 1
        rs.meld_red[seat] += called_red + consumed_red
        rs.melds[seat].append(Meld(kind, tuple(tiles), called_tile, from_seat))
        rs.events.append({"type": {"chi": "chi", "pon": "pon", "minkan": "daiminkan"}[kind],
                          "actor": seat, "target": from_seat, "pai": called_tile, "consumed": used,
                          "red": called_red, "consumed_red": consumed_red})
        self._check_pao(rs, seat, from_seat)
        label = {"chi": "チー", "pon": "ポン", "minkan": "大明槓"}[kind]
        self._say(f"  {seat}家 {label} {' '.join(tile_name(t) for t in tiles)}")

    def _check_pao(self, rs, seat, from_seat):
        """大三元・大四喜・四槓子が副露で確定した瞬間、最後の牌を鳴かせた相手に責任払いを課す"""
        if not self.rules.pao or from_seat is None or rs.pao[seat] is not None:
            return
        melds = rs.melds[seat]
        trip_bases = [m.base for m in melds if m.is_triplet_like]
        if sum(1 for t in trip_bases if t in DRAGONS) == 3 and melds[-1].base in DRAGONS:
            rs.pao[seat] = from_seat
        elif sum(1 for t in trip_bases if t in WINDS) == 4 and melds[-1].base in WINDS:
            rs.pao[seat] = from_seat
        elif sum(1 for m in melds if m.is_kan) == 4 and melds[-1].kind == "minkan":
            rs.pao[seat] = from_seat

    # ============================================================
    # 精算
    # ============================================================
    def _settle_tsumo(self, rs, winner, tile, res):
        deltas = [0] * 4
        is_dealer = winner == rs.dealer
        liable = rs.pao[winner] if res.yakuman else None
        from_dealer, from_child = res.tsumo_points(is_dealer)
        honba = 100 * rs.honba
        if liable is not None:
            total = sum((from_dealer if s == rs.dealer else from_child) + honba for s in range(4) if s != winner)
            deltas[liable] -= total
            deltas[winner] += total
        else:
            for s in range(4):
                if s == winner:
                    continue
                pay = (from_dealer if s == rs.dealer else from_child) + honba
                deltas[s] -= pay
                deltas[winner] += pay
        deltas[winner] += rs.riichi_sticks * 1000
        rs.riichi_sticks = 0
        self._apply(deltas)
        rs.events.append({"type": "hora", "actor": winner, "target": winner, "pai": tile, "deltas": deltas})
        self._say(f"  {winner}家 ツモ {tile_name(tile)} {res.label()} {[n for n, _ in res.yaku]} → {deltas}")
        value = sum(from_dealer if s == rs.dealer else from_child for s in range(4) if s != winner)
        return {"type": "tsumo", "winner": winner, "loser": None, "tile": tile, "win": dict(res.to_dict(), value=value),
                "deltas": deltas, "dealer_keeps": is_dealer, "riichi": list(rs.riichi),
                "pao": liable, "hand": self._reveal(rs, winner)}

    def _settle_ron(self, rs, winner, loser, tile, res):
        deltas = [0] * 4
        is_dealer = winner == rs.dealer
        pay = res.ron_points(is_dealer) + self.rules.honba_ron * rs.honba
        liable = rs.pao[winner] if res.yakuman else None
        if liable is not None and liable != loser:
            half = pay // 2
            deltas[liable] -= half
            deltas[loser] -= pay - half
        else:
            deltas[loser] -= pay
        deltas[winner] += pay + rs.riichi_sticks * 1000
        rs.riichi_sticks = 0
        self._apply(deltas)
        rs.events.append({"type": "hora", "actor": winner, "target": loser, "pai": tile, "deltas": deltas})
        self._say(f"  {winner}家 ロン {tile_name(tile)}（{loser}家から） {res.label()} {[n for n, _ in res.yaku]} → {deltas}")
        return {"type": "ron", "winner": winner, "loser": loser, "tile": tile,
                "win": dict(res.to_dict(), value=res.ron_points(is_dealer)),
                "deltas": deltas, "dealer_keeps": is_dealer, "riichi": list(rs.riichi),
                "pao": liable, "hand": self._reveal(rs, winner)}

    @staticmethod
    def _reveal(rs, seat):
        return {"closed": [t for t in range(NUM_KINDS) for _ in range(rs.hands[seat][t])],
                "melds": [m.to_dict() for m in rs.melds[seat]]}

    def _exhaustive_draw(self, rs):
        tenpai = [rs.is_tenpai(s) for s in range(4)]
        deltas = [0] * 4
        nagashi = [s for s in range(4) if self.rules.nagashi_mangan and rs.nagashi_ok[s] and rs.discards[s]]
        if nagashi:
            # 流し満貫：満貫ツモ相当の支払い（聴牌料は発生しない）
            for s in nagashi:
                for p in range(4):
                    if p == s:
                        continue
                    pay = 4000 if (s == rs.dealer or p == rs.dealer) else 2000
                    deltas[p] -= pay
                    deltas[s] += pay
            kind = "nagashi"
        else:
            n = sum(tenpai)
            if 0 < n < 4:
                pen = self.rules.noten_penalty
                for s in range(4):
                    deltas[s] = pen // n if tenpai[s] else -pen // (4 - n)
            kind = "draw"
        self._apply(deltas)
        rs.events.append({"type": "ryukyoku", "tenpai": tenpai, "deltas": deltas, "nagashi": nagashi})
        self._say(f"  {'流し満貫 ' + str(nagashi) if nagashi else '流局'} 聴牌={tenpai} → {deltas}")
        return {"type": kind, "winner": None, "loser": None, "tenpai": tenpai, "nagashi": nagashi,
                "deltas": deltas, "dealer_keeps": tenpai[rs.dealer] and self.rules.draw_renchan,
                "riichi": list(rs.riichi)}

    def _apply(self, deltas):
        for s in range(4):
            self.scores[s] += deltas[s]


def final_placement(scores, rules):
    """
    着順とポイント。同点は順位点を等分（rules.tie_split_uma）
      fixed   : (素点-返し)/1000 + 順位点 + オカ
      sinking : 同上。順位点は原点以上（浮き）の人数で決まる沈みウマ
      win_loss: 1着 +1・4着 -1 のみ（素点は含めない。101方式）
    """
    order = sorted(range(4), key=lambda s: (-scores[s], s))
    oka = (rules.return_score - rules.start_score) * 4 // 1000
    uma = rules.uma
    if rules.uma_mode == "sinking":
        from .rules import SINKING_UMA
        uma = SINKING_UMA.get(sum(1 for x in scores if x >= rules.return_score), (0, 0, 0, 0))
    placement = [0] * 4
    bonus = [0.0] * 4
    i = 0
    while i < 4:
        j = i
        if rules.tie_split_uma:
            while j + 1 < 4 and scores[order[j + 1]] == scores[order[i]]:
                j += 1
        share = (sum(uma[i:j + 1]) + (oka if i == 0 else 0)) / (j - i + 1)
        for k in range(i, j + 1):
            placement[order[k]] = i + 1 if rules.tie_split_uma else k + 1
            bonus[order[k]] = share
        i = j + 1
    if rules.uma_mode == "win_loss":
        points = [round(bonus[s], 2) for s in range(4)]
    else:
        points = [round((scores[s] - rules.return_score) / 1000 + bonus[s], 1) for s in range(4)]
    return {"placement": placement, "points": points}
