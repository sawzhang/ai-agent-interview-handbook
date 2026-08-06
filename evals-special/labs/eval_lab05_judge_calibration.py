#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab05_judge_calibration.py — Judge 校准闭环（一致率 / Cohen's kappa / 迭代）
=================================================================================

【实验目的】
    LLM-as-Judge 不是"写个 judge prompt 就能用"。未经校准的 judge 会制造
    「误导性的信心」：分数看起来很精确，量出来的却是 rubric 的缺陷。本实验
    复刻 Airbnb 在 EDD（Eval-Driven Development）实践中报告的典型案例：
    一个"字面重叠式" judge 与人工标注的一致率只有 ~80%，因为它**误罚了
    正确的改述、放过了流畅的错误**；通过分析分歧样本、修订 rubric
    （放宽改述惩罚 + 增加事实核对项），一致率提升到 95%。你将实现整条闭环：
        1) 构建 60 条 gold set（含"正确的改述"与"流畅的错误"两类陷阱样本）；
        2) Judge v1（字面重叠 rubric）复现 ~80% 一致率的未校准状态；
        3) 混淆矩阵 / 一致率 / Cohen's kappa / 按错误类型分解的分歧分析；
        4) 校准循环：分歧分析 → rubric 修订补丁 → Judge v2（事实核对式）；
        5) judge 升级后的"重新校准"监控三件套：一致性、高风险漏判率、边界稳定性。

【对应章节】
    本特辑第 E05 章 · 评分三层之二：LLM-as-Judge 深入（Judge 校准五步法）
    素材来源：Airbnb《Eval-driven development: Lessons from evaluating
    GenAI at scale》—— gold set 50~100 条、一致率目标 high-80s~90s、
    分歧驱动 rubric 迭代、judge 变更后重新校准。
    与主仓库 labs/lab05_eval_harness.py（最小 judge harness 入门）互补：
    那里解决"怎么跑评估"，这里解决"judge 本身可不可信"。

【核心概念】
    - Gold set（金标校准集）: 50~100 条「人工已判定 good/bad」的样本，必须
      同时包含两类陷阱：
        * 正确的改述 —— 答案正确但与参考答案字面不同（考验 judge 是否死抠字眼）；
        * 流畅的错误 —— 读起来通顺、实则事实错误（考验 judge 能否核对事实）。
      只有好样本的 gold set 校准不出 judge 的"漏判"能力。
    - 一致率（agreement）: judge 与人工标签相同的比例。直观但有陷阱——若 90%
      样本是 good，judge 无脑全判 good 也有 90% 一致率（见第 4 节演示）。
    - Cohen's kappa: 扣除「随机一致」后的真实一致程度：
          kappa = (p_o - p_e) / (1 - p_e)
      p_o 为观测一致率，p_e 为按双方边际分布算出的期望随机一致率。
      常用解读：<0.2 差 / 0.2~0.4 弱 / 0.4~0.6 中等 / 0.6~0.8 良好 / >0.8 几乎完全一致。
    - 分歧分析: 把不一致样本按「样本类别 × 方向」（FN 误罚好答案 / FP 放过
      坏答案）聚类，让系统性失败模式显形——这是修订 rubric 的证据，
      而不是拍脑袋改 prompt。
    - 校准闭环: 分歧分析 → 修 rubric → 重新评测 → 看 kappa 是否提升。
      judge 每次升级（换 prompt / 换模型）都必须重跑监控三件套：
      一致性、高风险漏判率、边界样本稳定性，三项齐看才能放行。

【如何运行】
    cd evals-special/labs
    python3 eval_lab05_judge_calibration.py
    （纯标准库、零依赖、固定随机种子，任何机器上结果完全一致）

【思考题（面试延伸）】
    1. 为什么一致率不足以衡量 judge 质量？标签分布严重失衡（如 90% good）时
       一致率会给出怎样的假象？kappa 如何修正这一点，它自己又有什么局限
       （边际分布依赖、患病率问题 prevalence paradox）？
    2. Airbnb 案例中 judge 误罚"正确的改述"，本质是把「与参考答案字面相似」
       错当成「答案正确」。你的业务里还有哪些"字面 rubric 会系统性误判"的
       样本族（拒答、安全兜底话术、多轮澄清式回答）？如何在 gold set 中显式
       构造它们？
    3. 本实验 Judge v2 仍残留 3 条错误（2 条别名漏收的改述 + 1 条未登记的
       过度承诺），且 s03-para 在 v1 碰巧判对、v2 反而判错。这说明校准的
       终点是什么？（提示：没有终点——分歧样本是 rubric 演进的燃料；校准
       追求的是系统性失败模式的收敛，不是每一条样本的单调改善。）
    4. 为什么"高风险漏判率"要单独监控、不能只看总体一致率？一个总体一致率
       95% 的 judge 在什么情况下仍然不能上线？
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 全局固定随机种子：本实验唯一的随机性是"重复评测翻转"模拟，
# 固定种子后任何机器跑出的数字都一致，断言才可复现。
random.seed(20260805)


# ---------------------------------------------------------------------------
# 1. 文本基础设施：确定性的"字面重叠度"
# ---------------------------------------------------------------------------
# Judge v1 的 rubric 需要一个可计算但刻意"死板"的相似度：只看字面、不懂语义
# ——这正是它会被"正确改述"骗倒的原因。
#
# 设计选择：中文按「字符二元组 bigram」切分，英文/数字按整体词切分。
# 为什么不用单字？单字切分时任何同话题的中文句子都共享大量汉字，重叠度虚高，
# 区分不出"复述"与"改述"；bigram 保留相邻关系，一旦换词、调语序，重叠度
# 显著下降——恰好模拟了"字面 rubric 对改述敏感"这一缺陷。

_PIECE_RE = re.compile(r"[一-鿿]+|[A-Za-z0-9]+")


def surface_tokens(text: str) -> List[str]:
    """把文本切成"字面 token"列表（确定性、零依赖）。
    连续中文 -> 字符二元组（单字片段退化为单字）；英文/数字 -> 整词小写。
    标点自然被丢弃，避免标点差异影响重叠度。"""
    tokens: List[str] = []
    for piece in _PIECE_RE.findall(text.lower()):
        if "一" <= piece[0] <= "鿿":
            tokens.extend(piece[i:i + 2] for i in range(len(piece) - 1)
                          ) if len(piece) > 1 else tokens.append(piece)
        else:
            tokens.append(piece)
    return tokens


def dice(set_a: set, set_b: set) -> float:
    """Dice 系数 = 2|A∩B| / (|A|+|B|) ∈ [0,1]。
    相比 Jaccard，Dice 对长短差异更宽容，适合"候选 vs 参考"的比较。"""
    if not set_a and not set_b:
        return 0.0
    return 2 * len(set_a & set_b) / (len(set_a) + len(set_b))


def literal_overlap(reference: str, candidate: str) -> float:
    """字面重叠率：参考与候选的 bigram 集合 Dice 系数。
    这是 Judge v1 唯一的打分依据——记住这个局限，后面它会闯祸。"""
    return dice(set(surface_tokens(reference)), set(surface_tokens(candidate)))


# ---------------------------------------------------------------------------
# 2. Gold set：60 条人工标注样本（12 场景 × 5 变体，含两类陷阱 + 高风险标记）
# ---------------------------------------------------------------------------
# 每个场景的 5 种变体及人工真值：
#   literal_repeat     照搬参考答案              -> good（两版 judge 的舒适区）
#   correct_paraphrase 正确的改述（陷阱①）      -> good（字面 rubric 容易误罚）
#   fluent_wrong       流畅的错误（陷阱②）      -> bad（字面 rubric 容易放过）
#   incomplete         残缺/含糊（缺关键事实）   -> bad
#   off_topic          完全跑题                  -> bad
# 改述分三档：light=轻度改写（字面相似度高）/ deep=深度改写 /
#             hard=深度改写且用了别名表之外的说法（v2 的"残留错误"来源）。
# 流畅的错误分三档：swap=句式照抄只换关键事实 / fabricated=自信编造 /
#                   trap=事实全对+一条未登记的过度承诺（v2 黑名单抓不到）。
#
# 每条样本携带两份"裁判辅助材料"（真实系统里写在 judge prompt 中）：
#   facts        关键事实及其合法表述（别名表）——Judge v2 的事实核对项；
#   wrong_claims 从 badcase 归纳的"已知错误说法"黑名单。
# v1 与 v2 看到的输入完全相同，差别只在 rubric 如何使用这些材料——
# 这保证实验比较的是"rubric 设计"，而不是"信息多寡"。

@dataclass(frozen=True)
class Fact:
    """一条关键事实：aliases 是参考表述与合法改述表述。
    别名表永远不可能穷尽人类说法——这个"不完备性"正是 v2 残留错误的根源。"""
    key: str
    aliases: Tuple[str, ...]


@dataclass(frozen=True)
class Scenario:
    """一个客服问答场景，以及为它预制好的各类变体文本。"""
    sid: str
    topic: str
    question: str
    reference: str
    facts: Tuple[Fact, ...]
    wrong_claims: Tuple[str, ...]
    para_kind: str                 # light / deep / hard
    para_text: str                 # 正确的改述
    wrong_kind: str                # swap / fabricated / trap
    wrong_text: str                # 流畅的错误
    partial_text: Optional[str]    # 残缺文本；None = 套用"含糊话术池"
    high_risk: bool                # 该场景的坏样本是否高风险（资损/合规）


def F(key: str, *aliases: str) -> Fact:
    """Fact 的简写构造器，让场景表更紧凑。"""
    return Fact(key=key, aliases=tuple(aliases))


# ---- 含糊话术池：听着客气、实则什么关键信息都没给（incomplete 的低相似变体）----
EVASIVE_POOL: Tuple[str, ...] = (
    "这个问题需要进一步核实，请您耐心等待后续通知。",
    "我们已经记录了您的问题，会尽快为您跟进处理。",
    "具体情况请以页面展示的最新信息为准。",
    "建议您直接联系商家确认该项信息。",
    "不同订单情况可能不同，请以您的实际订单为准。",
    "该功能正在持续优化中，请您关注后续更新。",
    "您可以在 App 的设置页查看相关说明。",
    "如有疑问，欢迎联系在线客服为您核实。",
    "一般会按照标准流程处理，请您放心。",
    "我们已收到您的反馈，将安排专员跟进。",
)

# ---- 跑题池：与任何问题都不相干的闲聊（off_topic 变体）----
OFFTOPIC_POOL: Tuple[str, ...] = (
    "今天天气真不错，适合出门走走。",
    "我最近学了一道新菜，打算周末试试。",
    "这首歌真好听，我循环播放了一整天。",
    "早高峰堵车太严重了，路上花了一个小时。",
    "昨晚看了一部电影，结局出乎意料。",
    "我家的猫又把水杯打翻了。",
    "最近几天的空气质量很好。",
    "下个月打算去旅行，还没想好去哪儿。",
    "阳台上的花开了，心情特别好。",
    "刚读完一本书，写得真不错。",
    "楼下新开的咖啡馆味道很好。",
    "昨天熬夜了，今天有点犯困。",
)


def build_scenarios() -> List[Scenario]:
    """12 个场景的文本全部手写——这是校准集最有价值的"人工资产"。
    注意别名表是故意不完备的：s03/s11 的改述用了别名表之外的说法，
    用来演示 v2 的残留错误与"校准没有终点"。"""
    S: List[Scenario] = []

    # s01 押金退款（高风险；wrong 用"偷换事实"：句式照抄、只换关键数值）
    S.append(Scenario(
        sid="s01", topic="押金退款",
        question="退房后押金多久能退回来？",
        reference="退房验收通过后，押金会在7个工作日内原路退回到您的支付账户。",
        facts=(F("退款时限", "7个工作日", "七个工作日"),
               F("前置条件", "退房验收通过后", "验收通过后"),
               F("退款路径", "原路退回到您的支付账户", "原支付渠道", "原支付方式")),
        wrong_claims=("24小时内", "秒到账"),
        para_kind="deep",
        para_text="验收通过后，押金将在七个工作日内退还至您的原支付渠道。",
        wrong_kind="swap",
        wrong_text="退房验收通过后，押金会在24小时内退给您，秒到账，请放心。",
        partial_text=None, high_risk=True))

    # s02 早餐政策（light 改述：几乎照搬，字面 rubric 也能判对）
    S.append(Scenario(
        sid="s02", topic="早餐政策",
        question="房费里包含早餐吗？包含几份？",
        reference="豪华房型含双人免费早餐，供应时间为每天6:30至9:30，地点在二楼大堂餐厅。",
        facts=(F("早餐份数", "双人免费早餐", "双份早餐"),
               F("供应时间", "每天6:30至9:30", "6:30至9:30", "6:30到9:30"),
               F("供应地点", "二楼大堂餐厅", "大堂餐厅")),
        wrong_claims=("单份早餐", "周末不供应", "前台领取"),
        para_kind="light",
        para_text="豪华房型的房费包含双人免费早餐，每天6:30到9:30在二楼大堂餐厅供应。",
        wrong_kind="fabricated",
        wrong_text="早餐是免费提供的，不过需要早点去占位置，去晚了可能没有座位。",
        partial_text=None, high_risk=False))

    # s03 房东取消赔付（高风险；hard 改述："不超过两百元"未收录进别名表）
    S.append(Scenario(
        sid="s03", topic="房东取消赔付",
        question="房东临时取消订单，平台怎么赔？",
        reference="房东在入住前24小时内取消订单的，平台赔付首晚房费30%的优惠券，上限200元。",
        facts=(F("触发条件", "入住前24小时内取消", "入住前24小时内"),
               F("赔付比例", "首晚房费30%的优惠券", "首晚房费30%"),
               F("赔付上限", "上限200元", "最高200元")),
        wrong_claims=("全额赔付", "赔付现金"),
        para_kind="hard",
        para_text="若房东在入住前24小时内取消，您可获得首晚房费30%的优惠券，赔付不超过两百元。",
        wrong_kind="fabricated",
        wrong_text="房东取消订单后平台会全额赔付现金，您不需要做任何操作。",
        partial_text=None, high_risk=True))

    # s04 免费取消（高风险；incomplete 用"删除关键事实、其余照抄"的高相似残缺）
    S.append(Scenario(
        sid="s04", topic="免费取消",
        question="最晚几点前可以免费取消？",
        reference="灵活价订单可在入住日当天18点前免费取消，超时取消将收取首晚房费作为违约金。",
        facts=(F("适用范围", "灵活价订单", "灵活价"),
               F("免费取消截止", "入住日当天18点前", "入住日18点前", "入住日当天18点之前"),
               F("超时后果", "收取首晚房费作为违约金", "扣除首晚房费", "首晚房费收取违约金")),
        wrong_claims=("随时免费取消", "不收取任何费用"),
        para_kind="deep",
        para_text="灵活价订单在入住日当天18点之前都能免费取消；超过这个时间点，会按首晚房费收取违约金。",
        wrong_kind="fabricated",
        wrong_text="您随时都可以免费取消订单，不收取任何费用，请放心预订。",
        # 删掉"入住日当天18点前"这一关键事实，其余基本照抄 -> 字面相似度仍很高
        partial_text="灵活价订单可免费取消，超时取消将收取首晚房费作为违约金。",
        high_risk=True))

    # s05 设施补偿（高风险；wrong 为 trap：三条事实全对 + 一条未登记的过度承诺）
    S.append(Scenario(
        sid="s05", topic="设施问题补偿",
        question="房间设施有问题，能申请什么补偿？",
        reference="确认设施问题后，可申请免费换房、50元优惠券或双倍积分三者之一。",
        facts=(F("补偿方式一", "免费换房", "免费更换房间"),
               F("补偿方式二", "50元优惠券", "五十元优惠券"),
               F("补偿方式三", "双倍积分", "积分双倍")),
        # 故意不收录"现金补偿"——它是 v2 尚未见过的错误模式
        wrong_claims=("无条件补偿", "三倍房费赔付"),
        para_kind="deep",
        para_text="设施问题核实后，您可以在免费换房、50元优惠券和双倍积分中任选其一。",
        wrong_kind="trap",
        # 事实全对 + 未登记的过度承诺 -> 人工判 bad，v2 黑名单抓不到
        wrong_text="确认设施问题后，您可以申请免费换房、50元优惠券或双倍积分，另外平台还会提供100元现金补偿。",
        partial_text=None, high_risk=True))

    # s06 发票开具（light 改述）
    S.append(Scenario(
        sid="s06", topic="发票开具",
        question="能开发票吗？怎么开？",
        reference="离店后30天内可在 App 订单详情页申请电子发票，一般3个工作日内开具完成。",
        facts=(F("申请期限", "离店后30天内", "离店后30天之内"),
               F("申请渠道", "App 订单详情页", "订单详情页"),
               F("开具时效", "3个工作日内", "三个工作日内")),
        wrong_claims=("无法开具发票", "只能开纸质发票"),
        para_kind="light",
        para_text="离店后30天之内，通过订单详情页就能申请电子发票，一般三个工作日内开完。",
        wrong_kind="fabricated",
        wrong_text="发票离店时找前台开就行，现场只能拿到纸质发票。",
        partial_text=None, high_risk=False))

    # s07 宠物政策（deep 改述）
    S.append(Scenario(
        sid="s07", topic="宠物政策",
        question="可以带宠物入住吗？要额外收费吗？",
        reference="宠物友好房型允许携带1只10公斤以下的宠物，每晚会加收80元清洁费。",
        facts=(F("数量限制", "1只", "一只"),
               F("重量限制", "10公斤以下", "十公斤以下"),
               F("清洁费", "每晚加收80元清洁费", "80元清洁费")),
        wrong_claims=("不允许携带宠物", "不额外收费"),
        para_kind="deep",
        para_text="宠物友好房型可以带一只十公斤以下的宠物入住，按每晚80元清洁费收取。",
        wrong_kind="fabricated",
        wrong_text="一般是可以带宠物入住的，工作人员通常不会仔细检查，您不用太担心。",
        partial_text=None, high_risk=False))

    # s08 会员权益（高风险；wrong 用"偷换事实"：句式照抄、三个事实全部换错）
    S.append(Scenario(
        sid="s08", topic="会员权益",
        question="升级白金会员有什么权益？",
        reference="升级白金会员后，可享受延迟退房至14点、免费双份早餐和免费升房三项权益。",
        facts=(F("延迟退房", "延迟退房至14点", "延迟退房到14点"),
               F("早餐权益", "免费双份早餐", "免费双人早餐"),
               F("升房权益", "免费升房", "免费升级房型")),
        wrong_claims=("延迟退房至18点", "三份早餐", "额外付费"),
        para_kind="deep",
        para_text="白金会员能延迟退房到14点，含免费双份早餐，还可免费升级房型。",
        wrong_kind="swap",
        wrong_text="升级白金会员后，可享受延迟退房至18点、免费三份早餐，升房服务需额外付费。",
        partial_text=None, high_risk=True))

    # s09 订单修改（incomplete 用"删除关键事实、其余照抄"的高相似残缺）
    S.append(Scenario(
        sid="s09", topic="订单修改",
        question="下单后能改入住日期吗？",
        reference="灵活价订单支持免费改期两次，需未开始入住且在原入住时间前48小时以上操作。",
        facts=(F("改期次数", "免费改期两次", "两次免费改期"),
               F("时间要求", "原入住时间前48小时以上", "提前48小时", "48小时之前"),
               F("前置条件", "未开始入住", "尚未入住", "还没入住")),
        wrong_claims=("无限次修改", "随时可改"),
        para_kind="deep",
        para_text="灵活价订单有两次免费改期的机会，前提是还没入住，并且要在原入住时间48小时之前操作。",
        wrong_kind="fabricated",
        wrong_text="日期随便改，想改几次都行，系统里操作一下就可以了。",
        # 删掉"48小时"这一关键事实 -> 字面 rubric 依旧判 good（漏判）
        partial_text="灵活价订单支持免费改期两次，需未开始入住。",
        high_risk=False))

    # s10 延迟退房（light 改述）
    S.append(Scenario(
        sid="s10", topic="延迟退房",
        question="怎么申请延迟退房？",
        reference="退房日当天中午12点前，可在前台或通过客房智能音箱申请延迟退房，视房态情况而定。",
        facts=(F("申请时间", "退房日当天中午12点前", "退房日12点前"),
               F("申请渠道", "前台或通过客房智能音箱", "前台或客房智能音箱"),
               F("限制条件", "视房态情况而定", "视当日房态而定")),
        wrong_claims=("无条件延迟", "自动延迟"),
        para_kind="light",
        para_text="退房日当天中午12点前，通过前台或客房智能音箱都能申请延迟退房，具体视当日房态而定。",
        wrong_kind="fabricated",
        wrong_text="延迟退房不用申请，想什么时候走就什么时候走，酒店不会管的。",
        partial_text=None, high_risk=False))

    # s11 押金预授权（hard 改述："一周内"与"3个工作日"语义兼容，但别名表只收了后者）
    S.append(Scenario(
        sid="s11", topic="押金预授权",
        question="为什么我的卡被预授权了500元？",
        reference="500元预授权是杂费押金，退房后3个工作日内自动解冻，不是实际扣款。",
        facts=(F("款项性质", "杂费押金", "杂费预授权"),
               F("解冻时效", "退房后3个工作日内", "退房后三个工作日内"),
               F("扣款说明", "不是实际扣款", "并非实际扣款")),
        wrong_claims=("实际消费扣款", "不予退还"),
        para_kind="hard",
        para_text="这500元是杂费押金，退房后一周内会自动解冻，并非实际扣款。",
        wrong_kind="fabricated",
        wrong_text="这笔钱是实际消费扣款，按您在房内的使用金额扣除，不予退还。",
        partial_text=None, high_risk=False))

    # s12 取消险理赔（高风险）
    S.append(Scenario(
        sid="s12", topic="取消险理赔",
        question="取消险保哪些情况？怎么赔？",
        reference="取消险承保因疾病、航班取消或自然灾害导致的取消损失，审核通过后以现金赔付至原支付方式。",
        facts=(F("承保原因", "疾病、航班取消或自然灾害", "疾病、航班取消、自然灾害",
                 "因病、航班取消或自然灾害"),
               F("理赔前提", "审核通过后", "审核通过后"),
               F("赔付方式", "现金赔付至原支付方式", "现金退回原支付渠道")),
        wrong_claims=("无条件赔付", "以优惠券赔付"),
        para_kind="deep",
        para_text="因病、航班取消或自然灾害导致取消的，审核通过后损失会以现金退回原支付渠道。",
        wrong_kind="fabricated",
        wrong_text="只要您不想去了就能无条件赔付，赔的是优惠券。",
        partial_text=None, high_risk=True))

    return S


@dataclass(frozen=True)
class GoldSample:
    """一条 gold 样本：人工标签是"唯一真值"，judge 的一切表现都以它为准。"""
    sample_id: str
    scenario_id: str
    category: str          # literal_repeat / correct_paraphrase / fluent_wrong / incomplete / off_topic
    subkind: str           # 更细的构造手法（para_light/para_deep/para_hard/swap/trap/...）
    question: str
    reference: str
    candidate: str
    human_label: str       # good / bad —— 人工真值
    facts: Tuple[Fact, ...]
    wrong_claims: Tuple[str, ...]
    high_risk: bool        # 高风险坏样本（资损/合规）：漏判代价高，需单独监控


def build_gold_set() -> List[GoldSample]:
    """把 12 个场景展开为 60 条样本。变体分配全部确定性（按场景顺序取池），
    不使用随机数——校准集本身必须是可审计、可追溯的静态资产。"""
    scenarios = build_scenarios()
    assert len(scenarios) == 12, "场景数应为 12（12 × 5 = 60 条样本）"
    evasive_idx = 0
    samples: List[GoldSample] = []
    for i, sc in enumerate(scenarios):
        # ① 照搬参考答案：字面 rubric 的"舒适区"，两版 judge 都应判对
        samples.append(GoldSample(
            f"{sc.sid}-repeat", sc.sid, "literal_repeat", "repeat",
            sc.question, sc.reference, sc.reference, "good",
            sc.facts, sc.wrong_claims, False))
        # ② 正确的改述：陷阱①，人工判 good
        samples.append(GoldSample(
            f"{sc.sid}-para", sc.sid, "correct_paraphrase", f"para_{sc.para_kind}",
            sc.question, sc.reference, sc.para_text, "good",
            sc.facts, sc.wrong_claims, False))
        # ③ 流畅的错误：陷阱②，人工判 bad
        samples.append(GoldSample(
            f"{sc.sid}-fluent", sc.sid, "fluent_wrong", f"wrong_{sc.wrong_kind}",
            sc.question, sc.reference, sc.wrong_text, "bad",
            sc.facts, sc.wrong_claims, sc.high_risk))
        # ④ 残缺/含糊：缺关键事实或含糊其辞，人工判 bad
        if sc.partial_text is not None:
            partial_text, subkind = sc.partial_text, "partial_strip"
        else:
            partial_text, subkind = EVASIVE_POOL[evasive_idx], "partial_evasive"
            evasive_idx += 1
        samples.append(GoldSample(
            f"{sc.sid}-partial", sc.sid, "incomplete", subkind,
            sc.question, sc.reference, partial_text, "bad",
            sc.facts, sc.wrong_claims, sc.high_risk))
        # ⑤ 完全跑题：两版 judge 都应判 bad 的"底线样本"
        samples.append(GoldSample(
            f"{sc.sid}-offtopic", sc.sid, "off_topic", "offtopic",
            sc.question, sc.reference, OFFTOPIC_POOL[i], "bad",
            sc.facts, sc.wrong_claims, False))
    return samples


# ---------------------------------------------------------------------------
# 3. Rubric 配置与 MockJudge（chat()/__call__ 与真实 LLM 客户端同构）
# ---------------------------------------------------------------------------
# Rubric 是一个"配置对象"：同一套 judge 代码 + 不同 rubric 配置 = 不同版本。
# 这样"修订 rubric"在代码里就是一次显式的配置变换，而不是一句
# "我们改了 prompt"的口头交代。

@dataclass(frozen=True)
class RubricConfig:
    name: str                    # 版本名，如 judge-v1-literal
    mode: str                    # literal_overlap=字面重叠式 / fact_check=事实核对式
    threshold: float             # literal 模式为相似度阈值；fact_check 为覆盖率门槛
    paraphrase_tolerant: bool    # 是否容忍改述（不以字面相似度为准绳）
    fact_check: bool             # 是否启用事实核对项 + 已知错误说法黑名单


# v1：只有字面重叠一条标准。阈值 0.60 是 rubric"操作化定义"的一部分；
# 后面会看到，深度改述恰好落在阈值下方——这不是巧合，而是字面 rubric 的
# 结构性缺陷（改述必然降低字面重叠，而答案正确性与字面重叠是两回事）。
RUBRIC_V1 = RubricConfig(
    name="judge-v1-literal", mode="literal_overlap", threshold=0.60,
    paraphrase_tolerant=False, fact_check=False)


class MockJudge:
    """确定性 Mock Judge。对外接口与主仓库 labs/llm_client.py 的 QwenLLM 同构：
    chat(messages, ...) 接收 Anthropic 风格消息列表，返回带 content/usage 的
    响应；生产环境可把本类整体替换为真实 LLM 客户端而上层评测代码不动。
    行为完全由传入的 RubricConfig 决定——同一个类既是 v1 也是 v2。"""

    def __init__(self, rubric: RubricConfig):
        self.rubric = rubric

    # ---- 对外接口①：chat()，与真实 LLM 客户端签名一致 ---------------------
    def chat(self, messages: List[dict], tools=None, system=None,
             max_tokens=None, temperature=None) -> dict:
        # 约定最后一条 user 消息为 JSON 载荷：问题、参考答案、候选与辅助材料
        payload = json.loads(messages[-1]["content"])
        judgment = self._judge_payload(payload)
        text = json.dumps(judgment, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            # mock 的 token 用量：真实系统据此核算 judge 成本
            "usage": {"input_tokens": sum(len(m.get("content", "")) for m in messages) // 2,
                      "output_tokens": len(text) // 2},
        }

    # ---- 对外接口②：__call__()，便于脚本里直接调用 -------------------------
    def __call__(self, question: str, reference: str, candidate: str,
                 facts: Tuple[Fact, ...] = (),
                 wrong_claims: Tuple[str, ...] = ()) -> dict:
        payload = {
            "question": question, "reference": reference, "candidate": candidate,
            "facts": [{"key": f.key, "aliases": list(f.aliases)} for f in facts],
            "wrong_claims": list(wrong_claims),
        }
        resp = self.chat([{"role": "user",
                           "content": json.dumps(payload, ensure_ascii=False)}])
        return json.loads(resp["content"][0]["text"])

    # ---- 内部：按 rubric 打分（完全确定性，无随机数） -----------------------
    def _judge_payload(self, payload: dict) -> dict:
        reference, candidate = payload["reference"], payload["candidate"]

        if self.rubric.mode == "literal_overlap":
            # v1 逻辑：只算字面重叠率并与阈值比较。它故意无视 payload 里的
            # facts——"没写进 rubric 的信息等于不存在"，这正是真实系统中
            # rubric 缺陷的产生机制。
            score = literal_overlap(reference, candidate)
            verdict = "good" if score >= self.rubric.threshold else "bad"
            reasons = [f"字面重叠率={score:.3f}，阈值={self.rubric.threshold}"]
            return {"verdict": verdict, "score": round(score, 4),
                    "margin": round(abs(score - self.rubric.threshold), 4),
                    "reasons": reasons}

        # v2 逻辑（fact_check）：逐条核对关键事实 + 已知错误说法黑名单。
        # 改述不再被惩罚：只要事实的全部合法表述之一出现在候选中即算覆盖。
        facts = payload["facts"]
        hits = [f["key"] for f in facts
                if any(alias in candidate for alias in f["aliases"])]
        missed = [f["key"] for f in facts if f["key"] not in hits]
        coverage = len(hits) / max(1, len(facts))
        wrong_hits = [w for w in payload["wrong_claims"] if w in candidate]

        # 判定：关键事实全覆盖，且没有命中已知错误说法
        verdict = ("good" if coverage >= self.rubric.threshold and not wrong_hits
                   else "bad")
        # margin（到决策边界的距离）：覆盖率按 1/3 档位离散取值，所以 v2 的
        # 样本要么离边界很远、要么差整整一档——这解释了为什么 v2 的边界样本
        # 几乎为零、重复评测极其稳定。
        coverage_margin = abs(coverage - self.rubric.threshold)
        margin = min(coverage_margin, 0.25) if wrong_hits else coverage_margin

        reasons = [f"事实覆盖={len(hits)}/{len(facts)}"]
        if missed:
            reasons.append(f"缺失事实: {'、'.join(missed)}")
        if wrong_hits:
            reasons.append(f"命中已知错误说法: {'、'.join(wrong_hits)}")
        return {"verdict": verdict, "score": round(coverage, 4),
                "margin": round(margin, 4), "reasons": reasons}


def run_judge(judge: MockJudge, gold: List[GoldSample]) -> Dict[str, dict]:
    """用 judge 跑一遍 gold set：每条样本都走 chat() 接口（模拟真实调用链）。
    返回 sample_id -> {verdict, score, margin, reasons}。"""
    return {s.sample_id: judge(s.question, s.reference, s.candidate,
                               facts=s.facts, wrong_claims=s.wrong_claims)
            for s in gold}


# ---------------------------------------------------------------------------
# 4. 校准度量：混淆矩阵 / 一致率 / Cohen's kappa / 分歧分解
# ---------------------------------------------------------------------------

def confusion_matrix(gold: List[GoldSample],
                     judgments: Dict[str, dict]) -> Dict[str, int]:
    """以 good 为正类统计混淆矩阵。
    TP=人判good且judge判good；FN=人判good但judge误罚（误杀好答案）；
    FP=人判bad但judge放过（漏判坏答案）；TN=双方都判bad。"""
    cm = {"TP": 0, "FN": 0, "FP": 0, "TN": 0}
    key_of = {("good", "good"): "TP", ("good", "bad"): "FN",
              ("bad", "good"): "FP", ("bad", "bad"): "TN"}
    for s in gold:
        cm[key_of[(s.human_label, judgments[s.sample_id]["verdict"])]] += 1
    return cm


def agreement(cm: Dict[str, int]) -> float:
    """观测一致率 p_o = (TP+TN)/N。"""
    return (cm["TP"] + cm["TN"]) / sum(cm.values())


def cohens_kappa(cm: Dict[str, int]) -> float:
    """Cohen's kappa = (p_o - p_e) / (1 - p_e)。
    p_e 用双方各自的边际分布乘积之和计算——它回答的问题是：
    "如果 judge 只是按它自己的判 good 倾向随机乱判，能蒙对多少？"
    扣掉这部分，剩下的才是真本事。"""
    n = sum(cm.values())
    p_o = agreement(cm)
    human_good = (cm["TP"] + cm["FN"]) / n
    judge_good = (cm["TP"] + cm["FP"]) / n
    p_e = human_good * judge_good + (1 - human_good) * (1 - judge_good)
    if p_e >= 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def kappa_paradox_demo() -> Tuple[float, float]:
    """演示"为什么不能只看一致率"：
    假设标签严重失衡（90% good），judge 无脑全判 good——
    一致率高达 90%，但 kappa = 0（和瞎蒙没有任何区别）。
    这也是 gold set 要刻意平衡 good/bad 比例的原因之一。"""
    cm = {"TP": 90, "FN": 0, "FP": 10, "TN": 0}   # 100 条中 90 条人工判 good
    return agreement(cm), cohens_kappa(cm)


def disagreement_breakdown(gold: List[GoldSample],
                           judgments: Dict[str, dict]) -> List[dict]:
    """按「样本类别 × 分歧方向」分解所有不一致样本。
    这是校准循环的"显微镜"：系统性错误会在这里显形——
    FN 集中在 correct_paraphrase，就说明 rubric 在惩罚改述。"""
    rows: List[dict] = []
    for s in gold:
        jv = judgments[s.sample_id]["verdict"]
        if jv == s.human_label:
            continue
        rows.append({
            "sample_id": s.sample_id, "category": s.category, "subkind": s.subkind,
            "direction": "FN(误罚好答案)" if s.human_label == "good" else "FP(放过坏答案)",
            "human": s.human_label, "judge": jv,
            "reasons": judgments[s.sample_id]["reasons"], "candidate": s.candidate,
        })
    return rows


# ---------------------------------------------------------------------------
# 5. 校准循环：分歧分析 -> rubric 修订补丁 -> Judge v2
# ---------------------------------------------------------------------------
# 真实团队里这一步是"人工读分歧样本 + 讨论 + 改 prompt"。这里把推理过程
# 显式写成规则，让读者看清"补丁是从证据里长出来的"：每一类高频分歧模式，
# 对应一条 rubric 修订动作。

def diagnose(disagreements: List[dict]) -> List[dict]:
    """从分歧样本归纳失败模式，产出（证据, 结论, 修订动作）三元组列表。"""
    fn_by_cat: Dict[str, int] = {}
    fp_by_cat: Dict[str, int] = {}
    for d in disagreements:
        bucket = fn_by_cat if d["direction"].startswith("FN") else fp_by_cat
        bucket[d["category"]] = bucket.get(d["category"], 0) + 1

    findings: List[dict] = []
    para_fn = fn_by_cat.get("correct_paraphrase", 0)
    if para_fn > 0:
        findings.append({
            "evidence": f"FN（误罚好答案）中有 {para_fn} 条集中在 correct_paraphrase，"
                        f"judge 理由均为'字面重叠率低于阈值'",
            "conclusion": "rubric 把「字面相似」错当成「答案正确」，系统性误罚正确改述",
            "action": "放宽改述惩罚：判定不再依赖字面重叠率",
        })
    fluent_fp = fp_by_cat.get("fluent_wrong", 0)
    partial_fp = fp_by_cat.get("incomplete", 0)
    if fluent_fp + partial_fp > 0:
        findings.append({
            "evidence": f"FP（放过坏答案）中 fluent_wrong {fluent_fp} 条、"
                        f"incomplete {partial_fp} 条，它们的字面相似度都不低",
            "conclusion": "只看字面无法识别'流畅的错误'与'缺关键事实的残缺答案'",
            "action": "增加事实核对项：关键事实逐条核对，并附已知错误说法黑名单",
        })
    return findings


def derive_rubric_patch(findings: List[dict]) -> dict:
    """把诊断结论翻译成 rubric 配置补丁（即"修订后的 rubric 要点"本体）。"""
    patch = {"paraphrase_tolerant": False, "fact_check": False}
    for f in findings:
        if "放宽改述惩罚" in f["action"]:
            patch["paraphrase_tolerant"] = True
        if "事实核对项" in f["action"]:
            patch["fact_check"] = True
    return patch


def apply_patch(base: RubricConfig, patch: dict) -> RubricConfig:
    """生成 Judge v2 的 rubric：事实核对式，覆盖率门槛 0.9。
    门槛取 0.9 而不是 1.0：判定语义仍是"全部关键事实必须覆盖"
    （覆盖率按 1/3 档位取值，2/3≈0.667 < 0.9 必然判 bad），但给 margin
    计算留出非零安全边距，避免"正好压线"的退化情形。"""
    return RubricConfig(
        name="judge-v2-factcheck", mode="fact_check", threshold=0.9,
        paraphrase_tolerant=patch["paraphrase_tolerant"],
        fact_check=patch["fact_check"])


# ---------------------------------------------------------------------------
# 6. Judge 升级后的"重新校准"监控三件套
# ---------------------------------------------------------------------------
# 经验法则：judge 每次升级（rubric / 模型变更）都必须重新产出这三项统计，
# 全部达标才允许进入日常自动化评测：
#   ① 一致性        —— 一致率 + kappa（与人工标注的吻合度）；
#   ② 高风险漏判率  —— 高风险坏样本被 judge 放过的比例（资损/合规红线）；
#   ③ 边界稳定性    —— 得分贴近决策边界的样本有多少、重复评测会不会翻转。
# 总体一致率再高，只要 ② 或 ③ 恶化，升级就不能放行。

BOUNDARY_EPS = 0.08  # |score 到阈值距离| < 0.08 视为"边界样本"


def high_risk_miss_rate(gold: List[GoldSample],
                        judgments: Dict[str, dict]) -> Tuple[int, int, float]:
    """高风险样本中「人工判 bad 但 judge 判 good」的比例。
    这类漏判的代价远高于普通误判：放过一条错误的退款承诺 = 真实资损。"""
    hr_bad = [s for s in gold if s.high_risk and s.human_label == "bad"]
    missed = sum(1 for s in hr_bad if judgments[s.sample_id]["verdict"] == "good")
    return missed, len(hr_bad), (missed / len(hr_bad) if hr_bad else 0.0)


def boundary_stats(gold: List[GoldSample],
                   judgments: Dict[str, dict]) -> Tuple[int, List[str]]:
    """统计边界样本（离决策边界 < BOUNDARY_EPS）。
    边界样本是"评测噪声"的温床：judge 措辞稍变、temperature 稍高，判定就可能
    翻转。一个稳健的 rubric 应让样本远离边界，而不是堆在阈值两侧。"""
    ids = [s.sample_id for s in gold
           if judgments[s.sample_id]["margin"] < BOUNDARY_EPS]
    return len(ids), ids


def simulate_repeated_evals(gold: List[GoldSample],
                            judgments: Dict[str, dict],
                            trials: int = 20, seed: int = 11) -> float:
    """模拟"同一 judge 重复评测 N 次"的翻转情况，返回稳定率 ∈ [0,1]。
    真实 LLM judge 受采样随机性影响，贴边样本容易翻转；这里用固定种子的
    随机数按 margin 分档模拟翻转概率：
        margin < 0.08（贴边） -> 每次重复有 35% 概率翻转；
        margin >= 0.08（远离）-> 不翻转。
    模拟完全确定性（seed 固定），用于对比两版 rubric 的"抗噪声能力"。"""
    rng = random.Random(seed)
    flips, total = 0, 0
    for s in gold:
        p_flip = 0.35 if judgments[s.sample_id]["margin"] < BOUNDARY_EPS else 0.0
        for _ in range(trials):
            total += 1
            if rng.random() < p_flip:
                flips += 1
    return 1.0 - flips / total


def calibration_monitor(gold: List[GoldSample], judge: MockJudge,
                        judgments: Dict[str, dict]) -> dict:
    """一次性产出监控三件套 + 混淆矩阵，作为 judge 版本的"体检报告"。"""
    cm = confusion_matrix(gold, judgments)
    missed, hr_total, miss_rate = high_risk_miss_rate(gold, judgments)
    b_count, _ = boundary_stats(gold, judgments)
    return {
        "judge": judge.rubric.name, "confusion": cm,
        "agreement": agreement(cm), "kappa": cohens_kappa(cm),
        "high_risk_missed": missed, "high_risk_total": hr_total,
        "high_risk_miss_rate": miss_rate, "boundary_count": b_count,
        "stability": simulate_repeated_evals(gold, judgments),
    }


# ---------------------------------------------------------------------------
# 7. 自检：断言本实验的全部核心结论（不是断言"跑完了"）
# ---------------------------------------------------------------------------

def run_self_checks(gold, j1, rep1, j2, rep2, rubric_v2) -> None:
    by_cat = lambda cat: [s for s in gold if s.category == cat]  # noqa: E731
    cm1, cm2 = rep1["confusion"], rep2["confusion"]
    n_good = sum(1 for s in gold if s.human_label == "good")

    # ---- (a) gold set 结构本身必须正确 -------------------------------------
    assert len(gold) == 60, f"gold set 应为 60 条，实际 {len(gold)}"
    assert n_good == 24 and sum(1 for s in gold if s.human_label == "bad") == 36, \
        "good/bad 标签分布应为 24/36（刻意平衡，避免一致率假象）"
    for cat in ("literal_repeat", "correct_paraphrase", "fluent_wrong",
                "incomplete", "off_topic"):
        assert len(by_cat(cat)) == 12, f"类别 {cat} 应为 12 条"
    assert rep1["high_risk_total"] == 12, "高风险坏样本应为 12 条"
    # 两类陷阱样本确实存在：hard 改述 x2、trap 流畅错误 x1
    assert sum(1 for s in by_cat("correct_paraphrase") if s.subkind == "para_hard") == 2
    assert sum(1 for s in by_cat("fluent_wrong") if s.subkind == "wrong_trap") == 1

    # ---- (b) v1 复现 Airbnb 式缺陷：一致率 ~80%，误罚改述、放过流畅错误 ------
    assert cm1 == {"TP": 16, "FN": 8, "FP": 4, "TN": 32}, f"v1 混淆矩阵异常: {cm1}"
    assert abs(rep1["agreement"] - 0.80) < 1e-12, "v1 一致率应为 0.80"
    assert rep1["agreement"] < 0.82, "v1 一致率必须 <0.82（复现未校准状态）"
    para_fn_v1 = sum(1 for s in by_cat("correct_paraphrase")
                     if j1[s.sample_id]["verdict"] == "bad")
    assert para_fn_v1 == 8 > 0, "v1 必须系统性误罚正确改述（Airbnb 案例复现）"
    fluent_fp_v1 = sum(1 for s in by_cat("fluent_wrong")
                       if j1[s.sample_id]["verdict"] == "good")
    assert fluent_fp_v1 >= 1, "v1 必须放过至少 1 条流畅的错误"

    # ---- (c) 校准后：v2 一致率 ≥ 85%，kappa 同步提升 ------------------------
    assert cm2 == {"TP": 22, "FN": 2, "FP": 1, "TN": 35}, f"v2 混淆矩阵异常: {cm2}"
    assert rep2["agreement"] >= 0.85, f"v2 一致率应 ≥0.85，实际 {rep2['agreement']:.3f}"
    assert rep2["kappa"] > rep1["kappa"], "kappa 应随校准提升"
    assert rep1["kappa"] < 0.65 <= rep2["kappa"], \
        f"kappa 应从'中等'提升到'良好以上'：v1={rep1['kappa']:.3f}, v2={rep2['kappa']:.3f}"

    # ---- (d) 改述误判显著减少：v1=8 条 -> v2=2 条，且残留全是"别名漏收"型 ----
    para_fn_v2 = sum(1 for s in by_cat("correct_paraphrase")
                     if j2[s.sample_id]["verdict"] == "bad")
    assert para_fn_v2 < para_fn_v1, "v2 在改述样本上的误判必须少于 v1"
    assert para_fn_v2 <= para_fn_v1 // 3, \
        f"改述误判应显著减少：v1={para_fn_v1}, v2={para_fn_v2}"
    assert all(s.subkind == "para_hard" for s in by_cat("correct_paraphrase")
               if j2[s.sample_id]["verdict"] == "bad"), \
        "v2 残留的改述误判应全部是'别名漏收'型（校准没有终点）"

    # ---- (e) 高风险漏判率必须下降，且 v2 达到可上线水位 ----------------------
    assert rep1["high_risk_miss_rate"] > rep2["high_risk_miss_rate"], \
        "高风险漏判率应随校准下降"
    assert (rep1["high_risk_missed"], rep2["high_risk_missed"]) == (3, 1)
    assert rep2["high_risk_miss_rate"] <= 0.10, "v2 高风险漏判率应 ≤10%"

    # ---- (f) 边界稳定性：v2 贴边样本更少、重复评测更稳 -----------------------
    assert rep1["boundary_count"] == 9 > rep2["boundary_count"] == 0, \
        "v2 的边界样本应清零（覆盖率离散档位让样本远离边界）"
    assert rep2["stability"] > rep1["stability"], "v2 的重复评测稳定率应更高"
    assert abs(rep2["stability"] - 1.0) < 1e-12, "v2 无边界样本，稳定率应为 1.0"
    assert 0.90 < rep1["stability"] < 1.0, "v1 有贴边样本，稳定率应低于 1"

    # ---- (g) 度量实现自身的正确性（防止指标代码有 bug） -----------------------
    n = len(gold)
    assert cm1["TP"] + cm1["FN"] == n_good, "混淆矩阵行和应等于人工 good 数"
    assert cm1["FP"] + cm1["TN"] == n - n_good, "混淆矩阵行和应等于人工 bad 数"
    # 手工重算 v2 的 kappa，验证公式实现
    p_o = (cm2["TP"] + cm2["TN"]) / n
    hg = (cm2["TP"] + cm2["FN"]) / n
    jg = (cm2["TP"] + cm2["FP"]) / n
    p_e = hg * jg + (1 - hg) * (1 - jg)
    assert abs(rep2["kappa"] - (p_o - p_e) / (1 - p_e)) < 1e-12, "kappa 实现错误"
    # 完全一致时 kappa 应为 1
    perfect = {"TP": n_good, "FN": 0, "FP": 0, "TN": n - n_good}
    assert abs(agreement(perfect) - 1.0) < 1e-12 and abs(cohens_kappa(perfect) - 1.0) < 1e-12
    # kappa 悖论：90% good 的失衡标签下，"全判 good"一致率 0.9 但 kappa=0
    paradox_agr, paradox_k = kappa_paradox_demo()
    assert abs(paradox_agr - 0.9) < 1e-12 and abs(paradox_k) < 1e-12, \
        "kappa 悖论演示失败：无脑 judge 的高一致率必须被 kappa 识破"

    # ---- (h) 确定性：同一 rubric 再跑一遍，60 条判定逐条一致 ------------------
    j2_again = run_judge(MockJudge(rubric_v2), gold)
    assert all(j2_again[s.sample_id]["verdict"] == j2[s.sample_id]["verdict"]
               for s in gold), "评测必须确定性可复现"


# ---------------------------------------------------------------------------
# 8. 演示入口：完整走一遍校准闭环
# ---------------------------------------------------------------------------

def _pad(s: str, width: int) -> str:
    """中文按 2 列宽对齐的简易 pad。"""
    w = sum(2 if ord(ch) > 127 else 1 for ch in s)
    return s + " " * max(0, width - w)


def print_confusion(cm: Dict[str, int], title: str) -> None:
    print(f"\n   {title}（正类=good）")
    print(f"   {'':<16}{'judge=good':>12}{'judge=bad':>12}")
    print(f"   {_pad('人工=good', 16)}{cm['TP']:>12}{cm['FN']:>12}")
    print(f"   {_pad('人工=bad', 16)}{cm['FP']:>12}{cm['TN']:>12}")


def main() -> None:
    print("=" * 68)
    print("EVAL LAB 05 · Judge 校准闭环：一致率 / Cohen's kappa / rubric 迭代")
    print("=" * 68)

    # [1/6] 构建 gold set ----------------------------------------------------
    gold = build_gold_set()
    n_good = sum(1 for s in gold if s.human_label == "good")
    print(f"\n[1/6] 构建 gold set：{len(gold)} 条人工标注样本"
          f"（good {n_good} / bad {len(gold) - n_good}，刻意平衡以防一致率假象）")
    cat_count: Dict[str, int] = {}
    for s in gold:
        cat_count[s.category] = cat_count.get(s.category, 0) + 1
    for cat, c in cat_count.items():
        print(f"      - {_pad(cat, 20)} x {c}")
    n_hr = sum(1 for s in gold if s.high_risk)
    print(f"      其中高风险坏样本 {n_hr} 条（资损/合规相关，漏判代价高）")

    # [2/6] Judge v1（字面重叠 rubric）跑 gold set ----------------------------
    judge_v1 = MockJudge(RUBRIC_V1)
    j1 = run_judge(judge_v1, gold)
    rep1 = calibration_monitor(gold, judge_v1, j1)
    print(f"\n[2/6] Judge v1（{RUBRIC_V1.name}，字面重叠阈值 "
          f"{RUBRIC_V1.threshold}）评测结果：")
    print_confusion(rep1["confusion"], "v1 混淆矩阵")
    print(f"   一致率 = {rep1['agreement']:.3f}   "
          f"Cohen's kappa = {rep1['kappa']:.3f}（中等一致，不可直接上线）")

    # [3/6] 分歧分析：错误集中在哪些样本族 -------------------------------------
    dis1 = disagreement_breakdown(gold, j1)
    print(f"\n[3/6] 分歧分析：v1 共 {len(dis1)} 条与人工不一致")
    findings = diagnose(dis1)
    for f in findings:
        print(f"   证据 : {f['evidence']}")
        print(f"   结论 : {f['conclusion']}")
        print(f"   动作 : {f['action']}")
    # 展示几条典型分歧样本（改述误罚 / 偷换事实漏判 / 高相似残缺漏判）
    for d in dis1:
        if d["subkind"] in ("para_deep", "wrong_swap", "wrong_trap", "partial_strip"):
            print(f"   例 [{d['direction']}] {d['sample_id']}: "
                  f"{d['candidate'][:26]}...  judge理由: {d['reasons'][0]}")

    # [4/6] 应用 rubric 补丁 -> Judge v2 ---------------------------------------
    patch = derive_rubric_patch(findings)
    rubric_v2 = apply_patch(RUBRIC_V1, patch)
    judge_v2 = MockJudge(rubric_v2)
    j2 = run_judge(judge_v2, gold)
    rep2 = calibration_monitor(gold, judge_v2, j2)
    print(f"\n[4/6] 应用修订补丁 {patch} -> {rubric_v2.name}")
    print_confusion(rep2["confusion"], "v2 混淆矩阵")
    print(f"   一致率 = {rep2['agreement']:.3f}   "
          f"Cohen's kappa = {rep2['kappa']:.3f}（几乎完全一致）")
    para_fn_v1 = sum(1 for s in gold if s.category == "correct_paraphrase"
                     and j1[s.sample_id]["verdict"] == "bad")
    para_fn_v2 = sum(1 for s in gold if s.category == "correct_paraphrase"
                     and j2[s.sample_id]["verdict"] == "bad")
    print(f"   改述误罚：{para_fn_v1} 条 -> {para_fn_v2} 条"
          f"（残留均为'别名漏收'型，需下一轮迭代补别名表）")
    print("   注意：s03-para 在 v1 碰巧判对（字面相似度恰在阈值上），v2 反而判错——")
    print("   校准追求的是系统性失败模式的收敛，不是每条样本的单调改善。")

    # [5/6] judge 升级后的重新校准监控三件套 ------------------------------------
    print("\n[5/6] 重新校准监控三件套（每次 judge 升级都必须产出）：")
    agr1, agr2 = f"{rep1['agreement']:.3f}", f"{rep2['agreement']:.3f}"
    kap1, kap2 = f"{rep1['kappa']:.3f}", f"{rep2['kappa']:.3f}"
    risk1 = (f"{rep1['high_risk_missed']}/{rep1['high_risk_total']} = "
             f"{rep1['high_risk_miss_rate']:.1%}")
    risk2 = (f"{rep2['high_risk_missed']}/{rep2['high_risk_total']} = "
             f"{rep2['high_risk_miss_rate']:.1%}")
    stb1, stb2 = f"{rep1['stability']:.3f}", f"{rep2['stability']:.3f}"
    print(f"   {_pad('指标', 24)}{_pad('Judge v1', 18)}Judge v2")
    print(f"   {_pad('① 一致率', 24)}{_pad(agr1, 18)}{agr2}")
    print(f"   {_pad('① Cohen kappa', 24)}{_pad(kap1, 18)}{kap2}")
    print(f"   {_pad('② 高风险漏判率', 24)}{_pad(risk1, 18)}{risk2}")
    print(f"   {_pad('③ 边界样本数(<0.08)', 24)}"
          f"{_pad(str(rep1['boundary_count']), 18)}{rep2['boundary_count']}")
    print(f"   {_pad('③ 重复评测稳定率', 24)}{_pad(stb1, 18)}{stb2}")
    print("   结论：v2 三项全面改善，允许进入日常自动化评测；"
          "残留分歧样本入库，驱动下一轮 rubric 迭代。")

    # [6/6] 自检 ----------------------------------------------------------------
    print("\n[6/6] 自检：断言核心结论...")
    run_self_checks(gold, j1, rep1, j2, rep2, rubric_v2)
    print(f"   v1 一致率 {rep1['agreement']:.3f} (<0.82) < "
          f"v2 一致率 {rep2['agreement']:.3f} (≥0.85) ✔")
    print(f"   kappa {rep1['kappa']:.3f} -> {rep2['kappa']:.3f} ✔   "
          f"改述误罚 {para_fn_v1} -> {para_fn_v2} 条 ✔")
    print(f"   高风险漏判率 {rep1['high_risk_miss_rate']:.1%} -> "
          f"{rep2['high_risk_miss_rate']:.1%} ✔   "
          f"边界样本 {rep1['boundary_count']} -> {rep2['boundary_count']} ✔")
    print("\n✅ 自检通过：eval_lab05_judge_calibration.py 全部断言成立")


if __name__ == "__main__":
    main()
