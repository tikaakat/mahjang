"""
麻雀AI。評価関数の重み（params）が個体の「個性」になる。

打牌は「攻撃（向聴数・受け入れ）＋打点（ドラ・役牌・染め手・タンヤオ）−守備（危険度）」の
合計が最大の牌を選ぶ。鳴き・リーチ・押し引きも params で傾向が変わる。

skill（思考の精度）はベンチマークの強さ調整に使う:
  1: 自分の手牌だけで受け入れを数える / 守備なし / 鳴かない / 常に即リーチ
  2: 見えている牌を考慮 / 現物だけで守る / 役牌だけ鳴く
  3: 筋・字牌の見え方で危険度を測る / タンヤオ・染め手でも鳴く / 押し引きあり
  4: ダマテン判断あり（個体はこのレベルで思考する）
  5: 4に加えて2段先の受け入れ（好形変化）まで読む（タイトルホルダー用）
"""
import random

from .tiles import NUM_KINDS, DRAGONS, is_honor, is_yaochu, is_simple, suit_of, number_of
from .shanten import shanten, winning_tiles, ukeire
from .scoring import WinContext, evaluate_win

PARAM_KEYS = [
    "speed_weight",     # 牌効率（受け入れ枚数）重視
    "dora_weight",      # ドラを大切にする
    "yakuhai_weight",   # 役牌を大切にする
    "flush_weight",     # 染め手（混一色・清一色）志向
    "tanyao_weight",    # 断么九志向
    "call_weight",      # 鳴きの積極性
    "riichi_weight",    # 即リーチの積極性（低いとダマテンを好む）
    "defense_weight",   # 守備意識（危険牌を避ける）
    "push_weight",      # 押し度胸（手が良いときは守備を緩める）
]

SHANTEN_UNIT = 12.0  # 1向聴の差を表す基準点


class MahjongAI:
    def __init__(self, params, skill=4, name="AI", noise=0.0, rng=None):
        self.p = params
        self.skill = skill
        self.name = name
        self.noise = noise          # ムラ気：打牌評価に加える揺らぎの大きさ（点）
        self.rng = rng or random.Random()

    # ============================================================
    # 共通の観測
    # ============================================================
    def _unseen(self, rs, seat):
        hand = rs.hands[seat]
        if self.skill <= 1:
            return [4 - hand[t] for t in range(NUM_KINDS)]
        vis = rs.public_visible_counts()
        return [max(0, 4 - vis[t] - hand[t]) for t in range(NUM_KINDS)]

    def _yakuhai_tiles(self, rs, seat):
        return set(DRAGONS) | {rs.seat_wind(seat), rs.round_wind}

    def _threats(self, rs, seat):
        """[(相手, 脅威度)]。リーチ=1.0、3副露=0.5 など"""
        out = []
        doras = set(rs.dora_tiles())
        yakuhai_all = set(DRAGONS) | {rs.round_wind}
        for opp in range(4):
            if opp == seat:
                continue
            if rs.riichi[opp]:
                out.append((opp, 1.0))
            elif self.skill >= 3 and rs.melds[opp]:
                n = len(rs.melds[opp])
                valuable = any(m.is_triplet_like and (m.base in yakuhai_all or m.base == rs.seat_wind(opp))
                               for m in rs.melds[opp]) or any(t in doras for m in rs.melds[opp] for t in m.tiles)
                if n >= 3:
                    out.append((opp, 0.6 if valuable else 0.45))
                elif n == 2 and valuable:
                    out.append((opp, 0.3))
        return out

    def _tile_danger(self, rs, seat, tile, opp):
        safe = rs.genbutsu(opp)
        if tile in safe:
            return 0.0
        if self.skill <= 2:
            return 1.0
        if is_honor(tile):
            vis = rs.public_visible_counts()[tile] + rs.hands[seat][tile]
            return {0: 0.6, 1: 0.5, 2: 0.25}.get(vis, 0.03)
        n = number_of(tile)
        base = {1: 0.55, 9: 0.55, 2: 0.8, 8: 0.8}.get(n, 1.0)
        lower = tile - 3 if n >= 4 else None
        upper = tile + 3 if n <= 6 else None
        lower_ok = lower is None or lower in safe
        upper_ok = upper is None or upper in safe
        if lower_ok and upper_ok:
            return base * 0.35
        if (lower is not None and lower in safe) or (upper is not None and upper in safe):
            return base * 0.7
        return base

    # ============================================================
    # 手牌の価値（打点の見込み）
    # ============================================================
    def _value_features(self, rs, seat, hand):
        melds = rs.melds[seat]
        tiles = [t for t in range(NUM_KINDS) for _ in range(hand[t])]
        meld_tiles = [t for m in melds for t in m.tiles]
        all_tiles = tiles + meld_tiles
        total = max(1, len(all_tiles))

        doras = rs.dora_tiles()
        dora = sum(all_tiles.count(d) for d in doras)

        yakuhai = 0.0
        for t in self._yakuhai_tiles(rs, seat):
            c = hand[t] + sum(3 for m in melds if m.is_triplet_like and m.base == t)
            if c >= 3:
                yakuhai += 1.5
            elif c == 2:
                yakuhai += 1.0

        # 染め手の進み具合
        flush = 0.0
        meld_suits = {suit_of(t) for t in meld_tiles if not is_honor(t)}
        if len(meld_suits) <= 1:
            best = 0
            for s in range(3):
                if meld_suits and s not in meld_suits:
                    continue
                c = sum(1 for t in all_tiles if suit_of(t) in (s, 3))
                best = max(best, c)
            frac = best / total
            flush = min(1.0, max(0.0, (frac - 0.6) / 0.4))

        # タンヤオの進み具合
        tanyao = 0.0
        if all(is_simple(t) for t in meld_tiles):
            frac = sum(1 for t in all_tiles if is_simple(t)) / total
            tanyao = min(1.0, max(0.0, (frac - 0.7) / 0.3))

        return {"dora": dora, "yakuhai": yakuhai, "flush": flush, "tanyao": tanyao}

    def _estimated_han(self, rs, seat, feats):
        han = feats["dora"] + (1 if feats["yakuhai"] >= 1.5 else 0)
        if feats["flush"] >= 0.9:
            han += 2
        if feats["tanyao"] >= 1.0:
            han += 1
        if rs.is_menzen(seat):
            han += 1  # リーチ分
        return han

    # ============================================================
    # 打牌選択
    # ============================================================
    def choose_discard(self, rs, seat, drawn, forbidden):
        hand = list(rs.hands[seat])
        k = len(rs.melds[seat])
        unseen = self._unseen(rs, seat)
        threats = self._threats(rs, seat) if self.skill >= 2 else []

        candidates = [t for t in range(NUM_KINDS) if hand[t] > 0 and t not in (forbidden or ())]
        if not candidates:
            candidates = [t for t in range(NUM_KINDS) if hand[t] > 0]

        sh_after = {}
        for t in candidates:
            hand[t] -= 1
            sh_after[t] = shanten(hand, k)
            hand[t] += 1
        min_sh = min(sh_after.values())

        scored = []
        for t in candidates:
            sh = sh_after[t]
            hand[t] -= 1
            if sh <= min_sh + 1:
                _, uk = ukeire(hand, k, unseen)
            else:
                uk = 0
            feats = self._value_features(rs, seat, hand)
            hand[t] += 1

            attack = -SHANTEN_UNIT * sh + (1.0 + self.p["speed_weight"]) * uk / 40.0
            value = (self.p["dora_weight"] * feats["dora"] * 0.8
                     + self.p["yakuhai_weight"] * feats["yakuhai"] * 0.6
                     + self.p["flush_weight"] * feats["flush"] * 1.5
                     + self.p["tanyao_weight"] * feats["tanyao"] * 1.0)

            defense = 0.0
            if threats:
                danger = sum(level * self._tile_danger(rs, seat, t, opp) for opp, level in threats)
                defense = self.p["defense_weight"] * danger * 4.0 * self._fold_factor(rs, seat, sh, feats)

            scored.append([attack + value - defense, t, sh, uk])

        if self.noise > 0:
            for row in scored:
                row[0] += self.rng.gauss(0, self.noise)
        scored.sort(key=lambda x: -x[0])

        if self.skill >= 5:
            self._refine_with_second_step(rs, seat, hand, k, unseen, scored)

        best = scored[0]
        discard = best[1]
        declare = False
        if best[2] == 0 and rs.is_menzen(seat) and not rs.riichi[seat]:
            hand[discard] -= 1
            declare = self._decide_riichi(rs, seat, hand, k, unseen, threats)
            hand[discard] += 1
        return discard, declare

    def _fold_factor(self, rs, seat, sh, feats):
        """1.0 = 完全にオリる、0 に近いほど押す"""
        if self.skill <= 2:
            return 1.0 if sh >= 1 else 0.3
        base = {0: 0.35, 1: 0.7}.get(sh, 1.0)
        power = min(1.0, self._estimated_han(rs, seat, feats) / 4.0)
        if sh == 0:
            power = min(1.0, power + 0.3)
        return base * max(0.05, 1.0 - self.p["push_weight"] / 10.0 * power)

    def _refine_with_second_step(self, rs, seat, hand, k, unseen, scored):
        """上位候補について、有効牌を引いた後の受け入れまで見て順位を調整する"""
        top_sh = scored[0][2]
        if top_sh <= 0:
            return
        top = [row for row in scored[:4] if row[2] == top_sh and scored[0][0] - row[0] < SHANTEN_UNIT * 0.5]
        if len(top) <= 1:
            return
        for row in top:
            t = row[1]
            hand[t] -= 1
            kinds, _ = ukeire(hand, k, unseen)
            total = 0
            for d in kinds:
                hand[d] += 1
                unseen[d] -= 1
                best_uk = 0
                for x in range(NUM_KINDS):
                    if hand[x] == 0:
                        continue
                    hand[x] -= 1
                    if shanten(hand, k) < top_sh:
                        _, uk = ukeire(hand, k, unseen)
                        best_uk = max(best_uk, uk)
                    hand[x] += 1
                unseen[d] += 1
                hand[d] -= 1
                total += (unseen[d]) * best_uk
            hand[t] += 1
            row[0] += total / 400.0
        scored.sort(key=lambda x: -x[0])

    # ============================================================
    # リーチ判断
    # ============================================================
    def _decide_riichi(self, rs, seat, hand13, k, unseen, threats):
        if rs.tiles_left() < 4 or rs.scores[seat] < rs.rules.riichi_min_score:
            return False
        waits = winning_tiles(hand13, k)
        live = sum(unseen[w] for w in waits)
        if self.skill <= 1:
            return True
        if live == 0:
            return False
        if self.skill <= 3:
            return True

        # ダマテンでの打点（ロン和了時の最大翻）
        dama_han = 0
        for w in waits:
            c = list(hand13)
            c[w] += 1
            ctx = WinContext(closed_counts=c, melds=rs.melds[seat], win_tile=w, is_tsumo=False,
                             seat_wind=rs.seat_wind(seat), round_wind=rs.round_wind,
                             is_dealer=(seat == rs.dealer), dora_indicators=rs.dora_indicators,
                             rules=rs.rules)
            res = evaluate_win(ctx)
            if res:
                dama_han = max(dama_han, 13 if res.yakuman else res.han)

        score = self.p["riichi_weight"] / 10.0
        if dama_han == 0:
            score += 0.6
        elif dama_han >= 4:
            score -= 0.5
        elif dama_han >= 3:
            score -= 0.3
        if live <= 2:
            score -= 0.2
        if rs.tiles_left() < 10:
            score -= 0.2
        if threats:
            score -= 0.1
        return score >= 0.5

    # ============================================================
    # 和了・鳴き
    # ============================================================
    def decide_tsumo(self, rs, seat, tile, result):
        return True

    def decide_ron(self, rs, seat, tile, from_seat, result):
        return True

    def decide_call(self, rs, seat, tile, from_seat, options):
        if self.skill <= 1:
            return None
        hand = list(rs.hands[seat])
        k = len(rs.melds[seat])
        cur_sh = shanten(hand, k)
        yakuhai_set = self._yakuhai_tiles(rs, seat)
        threats = self._threats(rs, seat)

        best_choice, best_score = None, 0.5
        kan_option = next((o for o in options if o[0] == "minkan"), None)
        for opt in options:
            kind, tiles = opt
            if kind == "minkan":
                continue
            used = list(tiles)
            used.remove(tile)
            for t in used:
                hand[t] -= 1
            new_sh = min(
                (self._sh_after_discard(hand, k + 1, d) for d in range(NUM_KINDS) if hand[d] > 0 and d != tile),
                default=99,
            )
            is_yakuhai_pon = kind == "pon" and tile in yakuhai_set
            path = self._yaku_path(rs, seat, hand, tiles, is_yakuhai_pon)
            for t in used:
                hand[t] += 1

            if self.skill == 2 and not is_yakuhai_pon:
                continue
            if not path:
                continue
            if is_yakuhai_pon:
                if new_sh > cur_sh:
                    continue
            elif new_sh >= cur_sh:
                continue

            score = self.p["call_weight"] / 10.0
            if is_yakuhai_pon:
                score += 0.3 + self.p["yakuhai_weight"] / 20.0
            if path == "flush":
                score += self.p["flush_weight"] / 30.0
            if path == "tanyao":
                score += self.p["tanyao_weight"] / 40.0
            if cur_sh >= 3:
                score -= 0.3
            if rs.is_menzen(seat):
                score -= self.p["riichi_weight"] / 40.0  # 門前（リーチ）への未練
            if threats and new_sh >= 1:
                score -= self.p["defense_weight"] / 20.0
            if score > best_score:
                best_choice, best_score = opt, score

        # 大明槓：ポンする価値がある場面で、槓子のまま使っても向聴数が悪くならず、鳴きに積極的なときだけ
        if kan_option and best_choice and best_choice[0] == "pon" and not threats:
            hand[tile] -= 3
            ok = shanten(hand, k + 1) <= cur_sh
            hand[tile] += 3
            if ok and self.p["call_weight"] >= 6.0:
                return kan_option
        return best_choice

    def decide_self_kan(self, rs, seat, options):
        """暗槓・加槓の判断。options: [("ankan"|"kakan", 牌)]"""
        if self.skill <= 1:
            return None
        hand = list(rs.hands[seat])
        k = len(rs.melds[seat])
        best_now = min(self._sh_after_discard(hand, k, d) for d in range(NUM_KINDS) if hand[d] > 0)
        threatened = bool(self._threats(rs, seat))
        for kind, t in options:
            if kind == "ankan":
                if rs.riichi[seat]:
                    return (kind, t)  # 待ちが変わらないことはエンジン側で確認済み
                hand[t] -= 4
                after = shanten(hand, k + 1)
                hand[t] += 4
                if after <= best_now and (not threatened or best_now == 0):
                    return (kind, t)
            else:
                if self._sh_after_discard(hand, k, t) <= best_now and not threatened:
                    return (kind, t)
        return None

    @staticmethod
    def _sh_after_discard(hand, k, d):
        hand[d] -= 1
        s = shanten(hand, k)
        hand[d] += 1
        return s

    def _yaku_path(self, rs, seat, hand_after, new_tiles, is_yakuhai_pon):
        """鳴いた後に役が付きそうか。付きそうなら役の系統名を返す"""
        yakuhai_set = self._yakuhai_tiles(rs, seat)
        melds_tiles = [list(m.tiles) for m in rs.melds[seat]] + [list(new_tiles)]
        if is_yakuhai_pon or any(m.is_triplet_like and m.base in yakuhai_set for m in rs.melds[seat]):
            return "yakuhai"
        if self.skill >= 3 and any(hand_after[t] >= 3 for t in yakuhai_set):
            return "yakuhai"
        flat = [t for m in melds_tiles for t in m]
        hand_tiles = [t for t in range(NUM_KINDS) for _ in range(hand_after[t])]
        if self.skill < 3:
            return None
        if all(is_simple(t) for t in flat) and sum(1 for t in hand_tiles if is_yaochu(t)) <= 1:
            return "tanyao"
        meld_suits = {suit_of(t) for t in flat if not is_honor(t)}
        if len(meld_suits) <= 1:
            s = next(iter(meld_suits)) if meld_suits else None
            off = sum(1 for t in hand_tiles if not is_honor(t) and suit_of(t) != s) if s is not None else 99
            if off <= 1:
                return "flush"
        return None
