"""
和了形の判定と点数計算（役・符・翻）。

対応ルール（簡略化あり）:
  - 赤ドラなし・カンなし（嶺上開花・槍槓・四槓子などは存在しない）
  - 喰いタンあり、後付けあり
  - 数え役満あり、ダブル役満は役満の複合のみ（四暗刻単騎などの2倍扱いはしない）
"""
from dataclasses import dataclass, field

from .tiles import (
    NUM_KINDS, WINDS, DRAGONS, GREEN_TILES, YAOCHU,
    is_honor, is_terminal, is_yaochu, is_simple, suit_of, dora_from_indicator,
)
from .shanten import shanten


@dataclass
class Meld:
    kind: str            # "pon" または "chi"
    tiles: tuple         # 構成牌（昇順）
    called_tile: int     # 鳴いた牌
    from_seat: int       # 誰から鳴いたか

    @property
    def base(self):
        return self.tiles[0]

    def to_dict(self):
        return {"kind": self.kind, "tiles": list(self.tiles), "called": self.called_tile, "from": self.from_seat}


@dataclass
class WinContext:
    closed_counts: list          # 和了牌を含む門前部分の枚数
    melds: list                  # Meld のリスト
    win_tile: int
    is_tsumo: bool
    seat_wind: int
    round_wind: int
    is_dealer: bool
    riichi: bool = False
    double_riichi: bool = False
    ippatsu: bool = False
    haitei: bool = False
    houtei: bool = False
    dora_indicators: list = field(default_factory=list)
    ura_indicators: list = field(default_factory=list)


@dataclass
class WinResult:
    han: int
    fu: int
    yaku: list          # [(役名, 翻数)]
    yakuman: int        # 役満の倍数（0なら通常役）
    base: int           # 基本点

    def ron_points(self, is_dealer):
        return _ceil100(self.base * (6 if is_dealer else 4))

    def tsumo_points(self, is_dealer):
        """(親の支払い, 子の支払い)。親の和了なら子は全員同額"""
        if is_dealer:
            each = _ceil100(self.base * 2)
            return each, each
        return _ceil100(self.base * 2), _ceil100(self.base)

    def label(self):
        if self.yakuman:
            return "役満" if self.yakuman == 1 else f"{self.yakuman}倍役満"
        if self.han >= 13:
            return "数え役満"
        if self.han >= 11:
            return "三倍満"
        if self.han >= 8:
            return "倍満"
        if self.han >= 6:
            return "跳満"
        if self.base >= 2000:
            return "満貫"
        return f"{self.fu}符{self.han}翻"

    def to_dict(self):
        return {"han": self.han, "fu": self.fu, "yaku": [[n, h] for n, h in self.yaku],
                "yakuman": self.yakuman, "label": self.label()}


def _ceil100(x):
    return -(-x // 100) * 100


def base_points(han, fu, yakuman=0):
    if yakuman:
        return 8000 * yakuman
    if han >= 13:
        return 8000
    if han >= 11:
        return 6000
    if han >= 8:
        return 4000
    if han >= 6:
        return 3000
    if han >= 5:
        return 2000
    return min(2000, fu * 2 ** (han + 2))


# ============================================================
# 手牌の分解
# ============================================================
def _decompose_mentsu(counts):
    """門前部分（雀頭を除いた後）を面子だけに分解する全パターン"""
    i = 0
    while i < NUM_KINDS and counts[i] == 0:
        i += 1
    if i == NUM_KINDS:
        return [[]]
    results = []
    if counts[i] >= 3:
        counts[i] -= 3
        for rest in _decompose_mentsu(counts):
            results.append([("koutsu", i)] + rest)
        counts[i] += 3
    if i < 27 and i % 9 <= 6 and counts[i + 1] and counts[i + 2]:
        counts[i] -= 1; counts[i + 1] -= 1; counts[i + 2] -= 1
        for rest in _decompose_mentsu(counts):
            results.append([("shuntsu", i)] + rest)
        counts[i] += 1; counts[i + 1] += 1; counts[i + 2] += 1
    return results


def regular_decompositions(closed_counts):
    """[(雀頭, [(種類, 先頭牌), ...]), ...]"""
    c = list(closed_counts)
    out = []
    for h in range(NUM_KINDS):
        if c[h] >= 2:
            c[h] -= 2
            for blocks in _decompose_mentsu(c):
                out.append((h, blocks))
            c[h] += 2
    return out


def is_chiitoitsu(closed_counts):
    return sum(1 for x in closed_counts if x == 2) == 7


def is_kokushi(closed_counts):
    return all(closed_counts[t] >= 1 for t in YAOCHU) and sum(closed_counts) == 14


# ============================================================
# 役判定
# ============================================================
def _block_tiles(kind, t):
    return [t, t, t] if kind == "koutsu" else [t, t + 1, t + 2]


def _all_tiles(ctx):
    tiles = []
    for t, c in enumerate(ctx.closed_counts):
        tiles.extend([t] * c)
    for m in ctx.melds:
        tiles.extend(m.tiles)
    return tiles


def _count_dora(ctx, tiles):
    dora = sum(tiles.count(dora_from_indicator(i)) for i in ctx.dora_indicators)
    ura = 0
    if ctx.riichi or ctx.double_riichi:
        ura = sum(tiles.count(dora_from_indicator(i)) for i in ctx.ura_indicators)
    return dora, ura


def _common_yaku(ctx, menzen, tiles):
    """手の形に依らない役"""
    yaku = []
    if ctx.double_riichi:
        yaku.append(("ダブル立直", 2))
    elif ctx.riichi:
        yaku.append(("立直", 1))
    if ctx.ippatsu and (ctx.riichi or ctx.double_riichi):
        yaku.append(("一発", 1))
    if menzen and ctx.is_tsumo:
        yaku.append(("門前清自摸和", 1))
    if ctx.haitei and ctx.is_tsumo:
        yaku.append(("海底摸月", 1))
    if ctx.houtei and not ctx.is_tsumo:
        yaku.append(("河底撈魚", 1))
    if all(is_simple(t) for t in tiles):
        yaku.append(("断么九", 1))
    suits = {suit_of(t) for t in tiles}
    number_suits = suits - {3}
    if len(number_suits) == 1:
        if 3 in suits:
            yaku.append(("混一色", 3 if menzen else 2))
        else:
            yaku.append(("清一色", 6 if menzen else 5))
    return yaku


def _yakuman_common(ctx, tiles):
    ym = []
    if all(is_honor(t) for t in tiles):
        ym.append("字一色")
    if all(t in GREEN_TILES for t in tiles):
        ym.append("緑一色")
    if all(is_terminal(t) for t in tiles):
        ym.append("清老頭")
    return ym


def _evaluate_regular(ctx, head, blocks, wait, menzen, tiles):
    """
    blocks: [(種類, 先頭牌, 副露/明刻か)]（和了牌によるロン明刻は副露扱い済み）
    wait: "ryanmen" / "kanchan" / "penchan" / "shanpon" / "tanki"
    戻り値: (翻, 符, 役リスト, 役満数)
    """
    shuntsu = [t for k, t, _ in blocks if k == "shuntsu"]
    koutsu = [(t, o) for k, t, o in blocks if k == "koutsu"]
    ankou = [t for t, o in koutsu if not o]
    koutsu_tiles = [t for t, _ in koutsu]

    # --- 役満 ---
    ym = _yakuman_common(ctx, tiles)
    if len(ankou) == 4:
        ym.append("四暗刻")
    dragon_trips = sum(1 for t in koutsu_tiles if t in DRAGONS)
    if dragon_trips == 3:
        ym.append("大三元")
    wind_trips = sum(1 for t in koutsu_tiles if t in WINDS)
    if wind_trips == 4:
        ym.append("大四喜")
    elif wind_trips == 3 and head in WINDS:
        ym.append("小四喜")
    if menzen and len({suit_of(t) for t in tiles}) == 1 and not is_honor(tiles[0]):
        c = [0] * 9
        for t in tiles:
            c[t % 9] += 1
        need = [3, 1, 1, 1, 1, 1, 1, 1, 3]
        if all(c[i] >= need[i] for i in range(9)):
            ym.append("九蓮宝燈")
    if ym:
        return 0, 0, [(n, 13) for n in ym], len(ym)

    yaku = _common_yaku(ctx, menzen, tiles)

    def yakuhai_value(t):
        v = 0
        if t in DRAGONS:
            v += 1
        if t == ctx.seat_wind:
            v += 1
        if t == ctx.round_wind:
            v += 1
        return v

    # 平和
    pinfu = (menzen and len(shuntsu) == 4 and wait == "ryanmen" and yakuhai_value(head) == 0)
    if pinfu:
        yaku.append(("平和", 1))

    # 一盃口・二盃口（門前のみ）
    if menzen:
        pairs_of_same = 0
        seen = {}
        for s in shuntsu:
            seen[s] = seen.get(s, 0) + 1
        for v in seen.values():
            pairs_of_same += v // 2
        if pairs_of_same == 2:
            yaku.append(("二盃口", 3))
        elif pairs_of_same == 1:
            yaku.append(("一盃口", 1))

    # 役牌
    for t in koutsu_tiles:
        if t in DRAGONS:
            yaku.append(({31: "役牌 白", 32: "役牌 發", 33: "役牌 中"}[t], 1))
        if t == ctx.seat_wind:
            yaku.append(("自風牌", 1))
        if t == ctx.round_wind:
            yaku.append(("場風牌", 1))

    # 三色同順・一気通貫
    for n in range(7):
        if n in shuntsu and n + 9 in shuntsu and n + 18 in shuntsu:
            yaku.append(("三色同順", 2 if menzen else 1))
            break
    for s in range(3):
        base = s * 9
        if base in shuntsu and base + 3 in shuntsu and base + 6 in shuntsu:
            yaku.append(("一気通貫", 2 if menzen else 1))
            break

    # 三色同刻
    for n in range(9):
        if n in koutsu_tiles and n + 9 in koutsu_tiles and n + 18 in koutsu_tiles:
            yaku.append(("三色同刻", 2))
            break

    # 対々和・三暗刻
    if len(koutsu) == 4:
        yaku.append(("対々和", 2))
    if len(ankou) == 3:
        yaku.append(("三暗刻", 2))

    # 小三元
    if dragon_trips == 2 and head in DRAGONS:
        yaku.append(("小三元", 2))

    # 混老頭 / 混全帯么九 / 純全帯么九
    if all(is_yaochu(t) for t in tiles):
        yaku.append(("混老頭", 2))
    else:
        def block_has_yaochu(k, t):
            return any(is_yaochu(x) for x in _block_tiles(k, t))
        if is_yaochu(head) and all(block_has_yaochu(k, t) for k, t, _ in blocks) and shuntsu:
            if any(is_honor(t) for t in tiles):
                yaku.append(("混全帯么九", 2 if menzen else 1))
            else:
                yaku.append(("純全帯么九", 3 if menzen else 2))

    han = sum(h for _, h in yaku)
    if han == 0:
        return 0, 0, [], 0

    # --- 符計算 ---
    if pinfu:
        fu = 20 if ctx.is_tsumo else 30
    else:
        fu = 20
        if menzen and not ctx.is_tsumo:
            fu += 10
        if ctx.is_tsumo:
            fu += 2
        for t, is_open in koutsu:
            f = 2 if is_open else 4
            if is_yaochu(t):
                f *= 2
            fu += f
        fu += 2 * yakuhai_value(head)
        if wait in ("kanchan", "penchan", "tanki"):
            fu += 2
        fu = -(-fu // 10) * 10
        if fu == 20:
            fu = 30  # 喰い平和形のロンなど
    return han, fu, yaku, 0


def evaluate_win(ctx):
    """和了形なら最も高くなる解釈の WinResult を、役なし・非和了なら None を返す"""
    closed = ctx.closed_counts
    if shanten(closed, len(ctx.melds)) != -1:
        return None
    menzen = len(ctx.melds) == 0
    tiles = _all_tiles(ctx)
    dora, ura = _count_dora(ctx, tiles)

    candidates = []  # (han, fu, yaku, yakuman)

    # 国士無双
    if menzen and is_kokushi(closed):
        candidates.append((0, 0, [("国士無双", 13)], 1))

    # 七対子
    if menzen and is_chiitoitsu(closed):
        ym = _yakuman_common(ctx, tiles)
        if ym:
            candidates.append((0, 0, [(n, 13) for n in ym], len(ym)))
        else:
            yaku = [("七対子", 2)] + _common_yaku(ctx, menzen, tiles)
            if all(is_yaochu(t) for t in tiles):
                yaku.append(("混老頭", 2))
            candidates.append((sum(h for _, h in yaku), 25, yaku, 0))

    # 通常形
    meld_blocks = [("koutsu" if m.kind == "pon" else "shuntsu", m.base, True) for m in ctx.melds]
    w = ctx.win_tile
    for head, closed_blocks in regular_decompositions(closed):
        interpretations = []
        if head == w:
            interpretations.append(("tanki", None))
        for idx, (k, t) in enumerate(closed_blocks):
            if k == "koutsu" and t == w:
                interpretations.append(("shanpon", idx))
            elif k == "shuntsu" and t <= w <= t + 2:
                pos = w - t
                if pos == 1:
                    wait = "kanchan"
                elif (pos == 0 and t % 9 == 6) or (pos == 2 and t % 9 == 0):
                    wait = "penchan"
                else:
                    wait = "ryanmen"
                interpretations.append((wait, idx))
        seen = set()
        for wait, idx in interpretations:
            key = (wait, closed_blocks[idx] if idx is not None else None)
            if key in seen:
                continue
            seen.add(key)
            blocks = []
            for j, (k, t) in enumerate(closed_blocks):
                opened = (wait == "shanpon" and j == idx and not ctx.is_tsumo)
                blocks.append((k, t, opened))
            blocks += meld_blocks
            han, fu, yaku, ym = _evaluate_regular(ctx, head, blocks, wait, menzen, tiles)
            if yaku:
                candidates.append((han, fu, yaku, ym))

    best = None
    for han, fu, yaku, ym in candidates:
        if not ym:
            yaku = list(yaku)
            if dora:
                yaku.append(("ドラ", dora))
            if ura:
                yaku.append(("裏ドラ", ura))
            han = sum(h for _, h in yaku)
        res = WinResult(han=han, fu=fu, yaku=yaku, yakuman=ym, base=base_points(han, fu, ym))
        if best is None or (res.base, res.han, res.fu) > (best.base, best.han, best.fu):
            best = res
    return best


def has_yaku_shape(ctx):
    """点数計算を行わず、役があるかだけを知りたい場合の簡易ラッパー"""
    return evaluate_win(ctx) is not None
