"""
ルール設定。既定値は日本プロ麻雀連盟の公式ルール（タイトル戦ルール）に準拠する。

確認できている項目:
  30000点持ち30000返し、順位点 +15/+5/-5/-15（オカなし）、一発・裏ドラ・槓ドラ・赤ドラなし、
  途中流局なし（2023年改正）、数え役満なし（11翻以上は三倍満）、純粋な役満の複合はダブル役満以上を認める
公式サイトで要確認のため設定で切り替えられるようにしている項目:
  流し満貫、オーラス親のアガリ止め・テンパイ止め、連風牌の雀頭符、同点時の順位点の扱い
"""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class RuleSet:
    name: str = "日本プロ麻雀連盟 公式ルール"
    game_length: str = "south"          # "east"=東風戦 / "south"=半荘戦
    start_score: int = 30000
    return_score: int = 30000
    uma: tuple = (15, 5, -5, -15)        # 千点単位
    ippatsu: bool = False
    ura_dora: bool = False
    kan_dora: bool = False
    kazoe_yakuman: bool = False          # False なら 13翻以上も三倍満止め
    double_yakuman: bool = True          # 役満の複合を認める
    nagashi_mangan: bool = True
    agari_yame: bool = False             # オーラス親のアガリ止め・テンパイ止め
    tobi: bool = False                   # 持ち点がマイナスになっても続行
    renpuu_pair_fu: int = 2              # 連風牌の雀頭符（2 または 4）
    tie_split_uma: bool = True           # 同点は順位点を等分する
    riichi_min_score: int = 1000
    noten_penalty: int = 3000
    honba_ron: int = 300
    pao: bool = True                     # 大三元・大四喜・四槓子の責任払い
    max_kans: int = 4

    def to_dict(self):
        d = asdict(self)
        d["uma"] = list(self.uma)
        return d


RENMEI = RuleSet()

# 以前の自作ルール相当（天鳳風）。テストやデバッグ用
TENHOU_LIKE = RuleSet(
    name="天鳳風（赤なし）", game_length="south", start_score=25000, return_score=30000,
    uma=(30, 10, -10, -30), ippatsu=True, ura_dora=True, kan_dora=True, kazoe_yakuman=True,
    nagashi_mangan=False, agari_yame=True, tobi=True, tie_split_uma=False,
)
