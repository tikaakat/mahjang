"""
牌の表現。牌種は 0〜33 の整数で扱う。
  0〜8   萬子 1m〜9m
  9〜17  筒子 1p〜9p
  18〜26 索子 1s〜9s
  27〜30 風牌 東南西北
  31〜33 三元牌 白發中
各牌種は4枚ずつ、合計136枚（赤ドラなし）。
"""
import random

NUM_KINDS = 34
EAST, SOUTH, WEST, NORTH = 27, 28, 29, 30
HAKU, HATSU, CHUN = 31, 32, 33
WINDS = (EAST, SOUTH, WEST, NORTH)
DRAGONS = (HAKU, HATSU, CHUN)
TERMINALS = (0, 8, 9, 17, 18, 26)
YAOCHU = TERMINALS + WINDS + DRAGONS
GREEN_TILES = (19, 20, 21, 23, 25, HATSU)  # 緑一色に使える牌: 2s3s4s6s8s發

_HONOR_NAMES = ["東", "南", "西", "北", "白", "發", "中"]
_SUIT_CHARS = ["m", "p", "s"]


def is_honor(t):
    return t >= 27


def is_terminal(t):
    return t < 27 and t % 9 in (0, 8)


def is_yaochu(t):
    return is_honor(t) or is_terminal(t)


def is_simple(t):
    return not is_yaochu(t)


def suit_of(t):
    """0=萬子 1=筒子 2=索子 3=字牌"""
    return 3 if t >= 27 else t // 9


def number_of(t):
    """数牌の数字（1〜9）。字牌は0"""
    return 0 if t >= 27 else t % 9 + 1


def tile_name(t):
    if t >= 27:
        return _HONOR_NAMES[t - 27]
    return f"{t % 9 + 1}{_SUIT_CHARS[t // 9]}"


def tiles_to_str(tiles):
    return " ".join(tile_name(t) for t in sorted(tiles))


def counts_to_str(counts):
    tiles = []
    for t, c in enumerate(counts):
        tiles.extend([t] * c)
    return tiles_to_str(tiles)


def dora_from_indicator(ind):
    """ドラ表示牌から実際のドラを求める"""
    if ind < 27:
        base = ind - ind % 9
        return base + (ind % 9 + 1) % 9
    if ind <= NORTH:
        return EAST + (ind - EAST + 1) % 4
    return HAKU + (ind - HAKU + 1) % 3


def parse_tiles(text):
    """テスト用: "123m456p789s東東" のような表記を牌種のリストへ変換する"""
    result = []
    pending = []
    for ch in text.replace(" ", ""):
        if ch.isdigit():
            pending.append(int(ch))
        elif ch in "mps":
            base = {"m": 0, "p": 9, "s": 18}[ch]
            result.extend(base + n - 1 for n in pending)
            pending = []
        elif ch in _HONOR_NAMES:
            result.append(27 + _HONOR_NAMES.index(ch))
        else:
            raise ValueError(f"unknown tile char: {ch}")
    if pending:
        raise ValueError("数字の後に m/p/s がありません")
    return result


def to_counts(tiles):
    counts = [0] * NUM_KINDS
    for t in tiles:
        counts[t] += 1
    return counts


def new_wall(rng=random):
    wall = [t for t in range(NUM_KINDS) for _ in range(4)]
    rng.shuffle(wall)
    return wall
