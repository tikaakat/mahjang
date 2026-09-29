import random

# 年齢帯ごとの能力倍率レンジ（シーズン開始時に抽選）。麻雀は棋力のピークが比較的遅いため、
# オセロ版より衰えを緩やかにしている
AGE_BUFF_RANGES = [
    (0, 29, (0.95, 1.15)),
    (30, 44, (0.95, 1.10)),
    (45, 59, (0.90, 1.05)),
    (60, 69, (0.85, 1.02)),
    (70, 999, (0.80, 1.00)),
]
TALENT_KEY = "talent"


def _age_range_for(age):
    for lo, hi, rng in AGE_BUFF_RANGES:
        if lo <= age <= hi:
            return rng
    return AGE_BUFF_RANGES[-1][2]


def roll_age_multipliers(age, param_keys):
    """年齢帯に応じた倍率レンジから、パラメータごと（技量を含む）に独立に抽選する"""
    lo, hi = _age_range_for(age)
    return {key: round(random.uniform(lo, hi), 3) for key in list(param_keys) + [TALENT_KEY]}


def effective_params(individual):
    params = individual.params
    age_mult = getattr(individual, "age_multipliers", None)
    if age_mult:
        params = {k: v * age_mult.get(k, 1.0) for k, v in params.items()}
    return params


def effective_talent(individual):
    mult = (getattr(individual, "age_multipliers", None) or {}).get(TALENT_KEY, 1.0)
    return max(0.0, min(1.0, individual.talent * mult))


# ============================================================
# 覚醒：ごく稀に、通常の変異幅を超えて技量か個性の1項目が大きく伸びる
# ============================================================
AWAKENING_CHANCE = 0.03
AWAKENING_MULTIPLIER_RANGE = (1.8, 3.0)


def maybe_awaken(params, talent, individual_id=None, chance=AWAKENING_CHANCE):
    """(新params, 新talent, 突破した項目名 or None)"""
    if random.random() >= chance:
        return dict(params), talent, None
    if random.random() < 0.5:
        new_talent = min(0.99, talent + random.uniform(0.12, 0.25))
        if individual_id:
            print(f"  ★★★ 覚醒！ {individual_id} の技量が突破しました（{talent:.2f}→{new_talent:.2f}）")
        return dict(params), new_talent, TALENT_KEY
    awakened = dict(params)
    key = random.choice(list(awakened.keys()))
    mult = random.uniform(*AWAKENING_MULTIPLIER_RANGE)
    awakened[key] = round(awakened.get(key, 1.0) * mult, 3)
    if individual_id:
        print(f"  ★★★ 覚醒！ {individual_id} の「{key}」が突破しました（×{mult:.2f}）")
    return awakened, talent, key
