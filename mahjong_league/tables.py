"""
雀士4人で半荘を打たせ、結果（Elo・通算成績・対局記録）を反映する。

半荘のシミュレーション自体は個体の状態に依存しない純粋な計算なので、複数の卓・半荘を
プロセスプールで並列に打ち、結果の反映（Elo更新など）だけを元の順番どおりに逐次行う。
並列数は環境変数 MAHJONG_WORKERS（既定: CPUコア数、1なら並列化しない）。
"""
import os
import random
from concurrent.futures import ProcessPoolExecutor

from mahjong_sim.ai import MahjongAI, noise_from_talent
from mahjong_sim.game import Game
from mahjong_sim.rules import RULESETS, rule_key_for_event

from .buffs import effective_params, effective_talent
from .elo import update_elo_table

FORM_SWING = 0.05             # ムラ気1.0あたりの、1半荘ごとの調子の振れ幅（技量換算）
INDIVIDUAL_SKILL = 4

_executor = None


def _get_executor():
    global _executor
    workers = int(os.environ.get("MAHJONG_WORKERS", os.cpu_count() or 1))
    if workers <= 1:
        return None
    if _executor is None:
        _executor = ProcessPoolExecutor(max_workers=workers)
    return _executor


def _spec(ind):
    return {"id": ind.id, "params": effective_params(ind), "talent": effective_talent(ind),
            "volatility": ind.volatility}


def _make_agent(spec, rng):
    """その半荘の調子を抽選し、技量を打牌の揺らぎに換算したAIを作る"""
    form = rng.gauss(0.0, FORM_SWING * spec["volatility"])
    talent = max(0.0, min(1.0, spec["talent"] + form))
    return MahjongAI(spec["params"], skill=INDIVIDUAL_SKILL, name=spec["id"],
                     noise=noise_from_talent(talent), rng=rng)


def simulate_hanchan(job):
    """プロセスプールで実行される1半荘。job = (席順のspec 4つ, 乱数シード, 牌譜を残すか, ルール名)"""
    specs, seed, keep_kifu, rule_key = job
    rng = random.Random(seed)
    agents = [_make_agent(s, rng) for s in specs]
    result = Game(agents, rules=RULESETS[rule_key], rng=rng).run()
    out = {
        "final_scores": result["final_scores"], "placement": result["placement"], "points": result["points"],
        "rounds": [{"round": r["round"], "honba": r["honba"], **summarize_round(r)} for r in result["rounds"]],
    }
    out["kifu"] = compact_kifu(result["rounds"])   # 牌譜は全半荘ぶん残す（keep_kifu は互換のため受け取るだけ）
    return out


def compact_kifu(rounds):
    """牌譜を保存用に圧縮する。牌は 0〜33 の整数（0-8:萬子 9-17:筒子 18-26:索子 27-33:東南西北白發中）。
    赤5は 34（赤五萬）・35（赤五筒）・36（赤五索）で表す。
    記号: t=ツモ d=打牌(*はツモ切り) r=リーチ c=チー p=ポン m=大明槓 a=暗槓 k=加槓 n=槓ドラ表示牌"""
    def code(pai, red):
        return 34 + pai // 9 if red else pai

    out = []
    for r in rounds:
        ev = r["events"]
        start = ev[0]
        seq = []
        for e in ev[1:]:
            t = e["type"]
            if t == "tsumo":
                seq.append(f"t{e['actor']} {code(e['pai'], e.get('red'))}")
            elif t == "dahai":
                seq.append(f"d{e['actor']} {code(e['pai'], e.get('red'))}{'*' if e.get('tsumogiri') else ''}")
            elif t == "reach":
                seq.append(f"r{e['actor']}")
            elif t in ("chi", "pon", "daiminkan"):
                kind = {"chi": "c", "pon": "p", "daiminkan": "m"}[t]
                consumed, red_left = [], e.get("consumed_red", False)
                for x in e["consumed"]:
                    if red_left and x in (4, 13, 22):
                        consumed.append(code(x, True))
                        red_left = False
                    else:
                        consumed.append(x)
                seq.append(f"{kind}{e['actor']} {code(e['pai'], e.get('red'))} {e['target']} {','.join(str(x) for x in consumed)}")
            elif t == "ankan":
                seq.append(f"a{e['actor']} {code(e['pai'], e.get('red'))}")
            elif t == "kakan":
                seq.append(f"k{e['actor']} {code(e['pai'], e.get('red'))}")
            elif t == "dora":
                seq.append(f"n0 {e['dora_marker']}")
        haipai = []
        for s, hand in enumerate(start["tehais"]):
            hand = list(hand)
            for k in (start.get("aka") or [[], [], [], []])[s]:
                hand[hand.index(k)] = code(k, True)
            haipai.append(hand)
        out.append({
            "round": r["round"], "honba": r["honba"], "kyotaku": start["kyotaku"], "oya": start["oya"],
            "dora": start["dora_marker"], "scores": start["scores"], "haipai": haipai,
            "seq": seq, "result": summarize_round(r),
        })
    return out


def summarize_round(r):
    item = {"type": r["type"], "deltas": r["deltas"], "riichi": r.get("riichi")}
    if r["type"] in ("draw", "nagashi"):
        item["tenpai"] = r["tenpai"]
        if r.get("nagashi"):
            item["nagashi"] = r["nagashi"]
    else:
        item.update({"winner": r["winner"], "loser": r["loser"], "tile": r["tile"], "win": r["win"],
                     "hand": r.get("hand")})
        if r.get("pao") is not None:
            item["pao"] = r["pao"]
    return item


def play_sessions(sessions, rng):
    """
    sessions: [(メンバー4人, 半荘数, イベント情報, 牌譜を残すか)]
    各卓で同じ4人が半荘数だけ打つ（起家は半荘ごとにずらす）。全卓・全半荘を並列にシミュレートし、
    結果の反映は卓ごと・半荘順に行う。
    戻り値: [(各人の合計ポイント {id: pt}, 対局記録リスト)]（sessions と同じ順）
    """
    jobs, meta = [], []
    for s_idx, (members, games, event, keep_kifu) in enumerate(sessions):
        order = list(members)
        rng.shuffle(order)
        event = {**event, "rule": rule_key_for_event(event)}
        for g in range(games):
            seats = order[g % 4:] + order[:g % 4]
            jobs.append(([_spec(ind) for ind in seats], rng.getrandbits(64), keep_kifu, event["rule"]))
            meta.append((s_idx, seats, {**event, "game": g + 1}))

    executor = _get_executor()
    if executor is not None and len(jobs) > 1:
        results = list(executor.map(simulate_hanchan, jobs, chunksize=1))
    else:
        results = [simulate_hanchan(j) for j in jobs]

    outputs = [({ind.id: 0.0 for ind in members}, []) for members, _, _, _ in sessions]
    for (s_idx, seats, event), res in zip(meta, results):
        update_elo_table(seats, res["placement"])
        for s, ind in enumerate(seats):
            ind.record_game(res["placement"][s], res["points"][s], season=event.get("season"),
                            score=res["final_scores"][s])
            ind.record_rounds(s, res["rounds"])
        record = {"event": event, "seats": [ind.id for ind in seats],
                  "names": [ind.display_name for ind in seats], **res}
        totals, records = outputs[s_idx]
        for ind_id, pt in zip(record["seats"], record["points"]):
            totals[ind_id] = round(totals[ind_id] + pt, 1)
        records.append(record)
    return outputs


def play_session(members, games, event, rng=None, keep_kifu=False):
    """同じ4人で games 半荘を打つ（1卓）。戻り値: (各人の合計ポイント, 対局記録リスト)"""
    return play_sessions([(members, games, event, keep_kifu)], rng or random.Random())[0]
