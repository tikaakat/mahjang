"""
鳳凰戦（通年リーグ）：A〜Dの4リーグ。各リーグは「節」ごとに4人卓を組み直し、1節4半荘を打つ。
年間の合計ポイントで順位を決め、昇降級・引退・新弟子の補充（師弟制度）を行う。
"""
import random

from mahjong_sim.ai import PARAM_KEYS

from .individual import LeagueIndividual
from .buffs import maybe_awaken
from .tables import play_sessions

LEAGUES = ("A", "B", "C", "D")
LEAGUE_CAPACITY = {"A": 16, "B": 16, "C": 20, "D": 24}   # 4の倍数（卓を組むため）
SECTIONS = {"A": 5, "B": 4, "C": 4, "D": 3}             # 年間の節数（1節=4半荘）
GAMES_PER_SECTION = 4

# 昇降級人数（上位リーグの下位 n 名 ⇔ 下位リーグの上位 n 名）
MOVES = {("A", "B"): 3, ("B", "C"): 3, ("C", "D"): 4}

RETIREMENT_AGE = 70
D_CONSECUTIVE_LOSING_LIMIT = 2     # Dリーグで2年連続マイナスなら引退
D_MIN_NEWCOMER_SLOTS = 2           # 毎年最低限確保する新人枠
MASTER_MIN_AGE = 30
CLAN_BRANCH_CHANCE = 0.08
CLAN_NEW_FOUNDER_CHANCE = 0.08
AWAKENED_INITIAL_AGE_RANGE = (16, 18)

# 初期ロスターの技量レンジ（リーグが上ほど高い）
INITIAL_TALENT = {"A": (0.70, 0.90), "B": (0.60, 0.80), "C": (0.50, 0.72), "D": (0.40, 0.65)}


def random_style():
    return {k: round(random.uniform(0.5, 10.0), 3) for k in PARAM_KEYS}


def bootstrap_rosters(registry):
    rosters = {}
    for league in LEAGUES:
        lo, hi = INITIAL_TALENT[league]
        members = []
        for i in range(LEAGUE_CAPACITY[league]):
            ind = LeagueIndividual(
                f"{league}0-{i:03d}", league, params=random_style(),
                talent=round(random.uniform(lo, hi), 3),
                display_name=registry.generate(), initial_age=random.randint(20, RETIREMENT_AGE - 5),
            )
            ind.volatility = round(random.uniform(0.3, 2.0), 2)
            members.append(ind)
        rosters[league] = members
    return rosters


# ============================================================
# リーグ戦
# ============================================================
def _group_tables(members, met, rng):
    """同卓回数がなるべく偏らないように4人卓を組む"""
    pool = list(members)
    rng.shuffle(pool)
    tables = []
    while len(pool) >= 4:
        table = [pool.pop(0)]
        while len(table) < 4:
            best = min(pool, key=lambda c: (sum(met.get(frozenset((c.id, m.id)), 0) for m in table), rng.random()))
            pool.remove(best)
            table.append(best)
        tables.append(table)
    return tables, pool   # pool = 抜け番


def run_league(members, league_name, season, rng, sections=None):
    """
    戻り値: (順位順の個体リスト, 対局記録, 成績 {id: {"points", "games", "placements"}})
    """
    sections = sections or SECTIONS[league_name]
    met = {}
    stats = {ind.id: {"points": 0.0, "games": 0, "placements": [0, 0, 0, 0]} for ind in members}
    records = []

    for sec in range(1, sections + 1):
        tables, resting = _group_tables(members, met, rng)
        for table in tables:
            for i in range(4):
                for j in range(i + 1, 4):
                    key = frozenset((table[i].id, table[j].id))
                    met[key] = met.get(key, 0) + 1
        sessions = [(table, GAMES_PER_SECTION,
                     {"kind": "league", "league": league_name, "season": season, "section": sec, "table": t_idx + 1},
                     False) for t_idx, table in enumerate(tables)]
        for totals, recs in play_sessions(sessions, rng):
            for rec in recs:
                for ind_id, p in zip(rec["seats"], rec["placement"]):
                    stats[ind_id]["games"] += 1
                    stats[ind_id]["placements"][p - 1] += 1
            for ind_id, pt in totals.items():
                stats[ind_id]["points"] = round(stats[ind_id]["points"] + pt, 1)
            records += recs
        print(f"    {league_name}リーグ 第{sec}節 終了（{len(tables)}卓" + (f"・抜け番{len(resting)}名" if resting else "") + "）")

    # 抜け番で対局数が揃わない場合は、1半荘平均×最大対局数に換算して比較する
    max_games = max((s["games"] for s in stats.values()), default=0)

    def score(ind):
        s = stats[ind.id]
        if s["games"] and s["games"] != max_games:
            return s["points"] / s["games"] * max_games
        return s["points"]

    ranked = sorted(members, key=lambda ind: (-score(ind), -ind.elo))
    for ind in ranked:
        ind.points_this_season = stats[ind.id]["points"]
    return ranked, records, stats


# ============================================================
# 昇降級・引退
# ============================================================
def relegate_and_retire(ranked, exempt, titleholder_ids, exempt_next_ids=frozenset()):
    """
    ranked: {"A": [...], ...} 今季の順位順（exempt は対局免除でリーグ戦に参加しなかった個体、所属リーグ付き）
    exempt_next_ids: 来季に対局免除となる個体（鳳凰位保持者）。定員の外枠として扱う
    戻り値: (新ロスター, 引退者リスト)
    """
    protected = set(titleholder_ids)
    retired = []

    def age_filter(members):
        keep = []
        for ind in members:
            if ind.age >= RETIREMENT_AGE and ind.id not in protected:
                ind.retired = True
                retired.append(ind)
            else:
                keep.append(ind)
        return keep

    lists = {lg: list(ranked[lg]) for lg in LEAGUES}
    moved = {lg: {"up": [], "down": []} for lg in LEAGUES}
    for (upper, lower), n in MOVES.items():
        up_list, low_list = lists[upper], lists[lower]
        n = min(n, len(up_list), len(low_list))
        # 上位リーグ下位のうちタイトル保持者は降級しない（1つ上の順位の者が代わりに降級）
        demote = [ind for ind in reversed(up_list) if ind.id not in protected][:n]
        promote = low_list[:n]
        moved[upper]["down"] = demote
        moved[lower]["up"] = promote

    new = {}
    for lg in LEAGUES:
        stay = [ind for ind in lists[lg] if ind not in moved[lg]["down"] and ind not in moved[lg]["up"]]
        idx = LEAGUES.index(lg)
        from_above = moved[LEAGUES[idx - 1]]["down"] if idx > 0 else []
        from_below = moved[LEAGUES[idx + 1]]["up"] if idx < len(LEAGUES) - 1 else []
        new[lg] = stay + from_below + from_above
    for lg, members in exempt.items():
        new[lg] = members + new[lg]

    # Dリーグ：2年連続マイナスで引退（今季Dで打った者のみ対象）
    d_played = {ind.id for ind in lists["D"]}
    keep_d = []
    for ind in new["D"]:
        if ind.id in d_played and ind not in moved["D"]["up"]:
            ind.consecutive_losing_seasons = ind.consecutive_losing_seasons + 1 if ind.points_this_season < 0 else 0
            if ind.consecutive_losing_seasons >= D_CONSECUTIVE_LOSING_LIMIT and ind.id not in protected:
                ind.retired = True
                retired.append(ind)
                continue
        else:
            ind.consecutive_losing_seasons = 0
        keep_d.append(ind)
    new["D"] = keep_d

    for lg in LEAGUES:
        new[lg] = age_filter(new[lg])

    # 定員超過（前年の保持者が失冠して戻った等）は下位リーグへ押し出し、定員割れは下から繰り上げる
    # （対局免除の鳳凰位保持者は定員の外枠として数えない）
    exempt_ids = set(exempt_next_ids)

    def playing(lg):
        return sum(1 for ind in new[lg] if ind.id not in exempt_ids)

    for i, lg in enumerate(LEAGUES[:-1]):
        lower = LEAGUES[i + 1]
        cap = LEAGUE_CAPACITY[lg]
        while playing(lg) > cap:
            candidates = [ind for ind in new[lg] if ind.id not in protected]
            victim = candidates[-1] if candidates else new[lg][-1]
            new[lg].remove(victim)
            new[lower].insert(0, victim)
        while playing(lg) < cap and new[lower]:
            new[lg].append(new[lower].pop(0))

    # Dの新人枠を毎年最低限確保（定員ぎりぎりなら、成績下位を追加で引退させる）
    d_cap = LEAGUE_CAPACITY["D"]
    need_cut = len(new["D"]) - (d_cap - D_MIN_NEWCOMER_SLOTS)
    if need_cut > 0:
        cuttable = [ind for ind in reversed(new["D"]) if ind.id not in protected and ind.id in d_played]
        for ind in cuttable[:need_cut]:
            ind.retired = True
            retired.append(ind)
            new["D"].remove(ind)

    for lg in LEAGUES:
        for ind in new[lg]:
            if ind.league != lg:
                ind.league = lg
                ind.seasons_in_league = 0
            else:
                ind.seasons_in_league += 1
            ind.total_seasons += 1
    for ind in retired:
        ind.total_seasons += 1
    return new, retired


# ============================================================
# 成長：若手は技量が伸び、ベテランは緩やかに衰える
# ============================================================
def develop(ind):
    age = ind.age
    if age < 30:
        delta = random.uniform(0.005, 0.03)
    elif age < 45:
        delta = random.uniform(-0.005, 0.012)
    elif age < 60:
        delta = random.uniform(-0.012, 0.005)
    else:
        delta = random.uniform(-0.025, 0.0)
    ind.talent = round(max(0.05, min(0.99, ind.talent + delta)), 3)


# ============================================================
# 新弟子（師弟制度）
# ============================================================
def _master_weight(ind, titleholder_ids):
    elo_bonus = max(0.0, (ind.elo - 1500) / 300)
    title_bonus = 2.0 if ind.id in titleholder_ids else 0.0
    return 1.0 + elo_bonus + title_bonus


def _pick_master(eligible, titleholder_ids):
    if not eligible or random.random() < CLAN_NEW_FOUNDER_CHANCE:
        return None
    weights = [_master_weight(ind, titleholder_ids) for ind in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]


def mutate_params(master):
    """師匠の打ち筋を継承しつつ、弟子ごとに±15%程度の変異を加える"""
    return {k: max(0.1, round(master.params.get(k, 1.0) * random.uniform(0.85, 1.15), 3)) for k in PARAM_KEYS}


def generate_disciples(count, season, pool, registry, titleholder_ids=frozenset()):
    disciples = []
    active = [ind for ind in pool if not ind.retired]
    eligible = [ind for ind in active if ind.age >= MASTER_MIN_AGE] or active
    for i in range(count):
        ind_id = f"D{season}-{i:03d}"
        master = _pick_master(eligible, titleholder_ids)
        if master:
            params = mutate_params(master)
            # 弟子の技量は師匠より控えめに始まり、若いうちに伸びる
            talent = master.talent * random.uniform(0.65, 0.9)
            gen = master.generation + 1
            clan_root = ind_id if random.random() < CLAN_BRANCH_CHANCE else master.clan_root_id
            vol = master.volatility + random.uniform(-0.2, 0.2)
        else:
            params = random_style()
            talent = random.uniform(0.4, 0.6)
            gen = 0
            clan_root = ind_id
            vol = random.uniform(0.3, 2.0)
        params, talent, awakened = maybe_awaken(params, talent, individual_id=ind_id)
        ind = LeagueIndividual(
            ind_id, "D", params=params, talent=round(min(0.99, talent), 3), generation=gen,
            parent_a_id=master.id if master else None, display_name=registry.generate(),
            clan_root_id=clan_root,
            initial_age=random.randint(*AWAKENED_INITIAL_AGE_RANGE) if awakened else None,
        )
        ind.awakened_param = awakened
        ind.volatility = max(0.1, min(3.0, round(vol, 2)))
        disciples.append(ind)
    return disciples


def recruit_d_league(rosters, season, registry, titleholder_ids=frozenset()):
    vacancy = LEAGUE_CAPACITY["D"] - len(rosters["D"])
    if vacancy <= 0:
        return rosters, []
    pool = [ind for lg in LEAGUES for ind in rosters[lg]]
    new = generate_disciples(vacancy, season, pool, registry, titleholder_ids)
    rosters["D"] = rosters["D"] + new
    return rosters, new
