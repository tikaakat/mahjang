"""
キャラクリエイト：サイトから投稿された雀士（名前・打ち筋）を検証し、個体を作る。
検証ルールはサイト側（server/lib.php）と揃えること。
"""
import random

from mahjong_sim.ai import PARAM_KEYS

from .buffs import maybe_awaken
from .individual import LeagueIndividual, roll_initial_age

PARAM_MIN = 0.5
PARAM_MAX = 10.0
PARAM_BUDGET = 45.0          # 9項目の合計の上限（サイトの割り振りUIと一致させる）
NAME_MAX_LEN = 12
CREATION_AWAKENING_CHANCE = 0.05
CREATION_TALENT_RANGE = (0.45, 0.62)

# 打ち筋のプリセット（割り振りの出発点。サイトと同じ値）
PRESETS = {
    "balanced": {"speed_weight": 6, "dora_weight": 4, "yakuhai_weight": 4, "flush_weight": 3, "tanyao_weight": 4,
                 "call_weight": 5, "riichi_weight": 6, "defense_weight": 7, "push_weight": 6},
    "attack": {"speed_weight": 8, "dora_weight": 6, "yakuhai_weight": 4, "flush_weight": 3, "tanyao_weight": 4,
               "call_weight": 4, "riichi_weight": 9, "defense_weight": 2, "push_weight": 5},
    "defense": {"speed_weight": 6, "dora_weight": 3, "yakuhai_weight": 3, "flush_weight": 2, "tanyao_weight": 3,
                "call_weight": 3, "riichi_weight": 5, "defense_weight": 10, "push_weight": 10},
    "caller": {"speed_weight": 7, "dora_weight": 4, "yakuhai_weight": 8, "flush_weight": 5, "tanyao_weight": 7,
               "call_weight": 9, "riichi_weight": 1, "defense_weight": 2, "push_weight": 2},
    "flush": {"speed_weight": 4, "dora_weight": 4, "yakuhai_weight": 6, "flush_weight": 10, "tanyao_weight": 1,
              "call_weight": 8, "riichi_weight": 3, "defense_weight": 5, "push_weight": 4},
}


def normalize_params(raw):
    """範囲外は切り詰め、合計が予算を超えたら比率を保って縮める。不正なら None"""
    if not isinstance(raw, dict):
        return None
    values = {}
    for k in PARAM_KEYS:
        v = raw.get(k)
        if not isinstance(v, (int, float)) or v != v:
            return None
        values[k] = max(PARAM_MIN, min(PARAM_MAX, float(v)))
    total = sum(values.values())
    if total > PARAM_BUDGET:
        scale = PARAM_BUDGET / total
        values = {k: max(PARAM_MIN, v * scale) for k, v in values.items()}
    return {k: round(v, 3) for k, v in values.items()}


def clean_name(name):
    name = "".join(ch for ch in str(name or "") if ch.isprintable()).strip()
    return name[:NAME_MAX_LEN] or None


def request_params(request):
    params = normalize_params(request.get("params"))
    if params is None:
        preset = PRESETS.get(request.get("type"), PRESETS["balanced"])
        params = {k: round(v * random.uniform(0.8, 1.2), 3) for k, v in preset.items()}
        params = normalize_params(params)
    return params


def build_created_individual(request, ind_id, master=None, clan_branch_chance=0.08):
    """
    投稿から個体を作る。打ち筋は本人の指定を使い（師匠からは継承しない）、師匠は所属の証として付く。
    request に "talent"/"awakened_param" が入っていれば再抽選しない（新人リーグで戦った個体と、
    実際に入門する個体を一致させるため）。
    """
    params = request.get("resolved_params") or request_params(request)
    if "talent" in request:
        talent, awakened = request["talent"], request.get("awakened_param")
    else:
        talent = round(random.uniform(*CREATION_TALENT_RANGE), 3)
        params, talent, awakened = maybe_awaken(params, talent, individual_id=ind_id,
                                                chance=CREATION_AWAKENING_CHANCE)
        request["resolved_params"] = params
        request["talent"] = talent
        request["awakened_param"] = awakened
    if master is not None:
        clan_root = ind_id if random.random() < clan_branch_chance else master.clan_root_id
    else:
        clan_root = ind_id
    ind = LeagueIndividual(
        ind_id, "D", params=params, talent=talent, generation=(master.generation + 1) if master else 0,
        parent_a_id=master.id if master else None, display_name=clean_name(request.get("name")) or ind_id,
        clan_root_id=clan_root,
        initial_age=roll_initial_age(bool(awakened)),
    )
    ind.awakened_param = awakened
    ind.volatility = request.setdefault("volatility", round(random.uniform(0.3, 2.0), 2))
    ind.created = True
    ind.submission_id = request.get("submission_id")
    ind.creator = clean_name(request.get("creator"))
    return ind
