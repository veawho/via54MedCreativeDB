#!/usr/bin/env python3
"""
召回率评估脚本 — via54MedCreativeDB
用法: python3 scripts/evaluate_recall.py [--query-file FILE]

功能:
  1. 加载预设测试查询集（query + expected relevant dimensions）
  2. 对每个查询执行检索
  3. 计算 D1-D12 各维度的召回率
  4. 输出混淆矩阵风格的召回报告
  5. 识别检索薄弱维度

测试查询集说明:
  每个查询有 expected_relevant_dimensions（应该命中的维度），
  用于计算 recall = (hit_dimensions / expected_dimensions)
"""
import sys, json, sqlite3
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))
from via54_rag import search

DB_PATH = Path(__file__).parent.parent / "via54_rag" / "vector.db"

# ─────────────────────────────────────────────
# 测试查询集（query → 预期命中的维度列表）
# 格式：query: [预期相关 D 维度]
# ─────────────────────────────────────────────
TEST_QUERIES = {
    # D1 品牌背景
    "新品牌如何建立市场认知": ["D1"],
    "品牌转型期的创意策略": ["D1"],
    "老字号品牌如何年轻化": ["D1"],
    "B2B药企品牌建设案例": ["D1", "D2"],

    # D2 竞争定位
    "蓝海市场差异化策略": ["D2"],
    "仿制药品牌竞争策略": ["D2", "D12"],
    "市场挑战者的品牌定位": ["D2"],

    # D3 人群洞察
    "慢病患者人群画像": ["D3", "D4"],
    "医生群体的信息获取渠道": ["D3", "D5"],
    "患者家属的决策影响力": ["D3"],

    # D4 需求洞察
    "抑郁症患者的情感需求": ["D4", "D3"],
    "用药依从性提升策略": ["D4", "D3"],
    "未被满足的医疗需求": ["D4"],

    # D5 社媒偏好
    "抖音医药营销案例": ["D5", "D8"],
    "小红书皮肤科KOL合作": ["D5", "D3"],
    "微信私域患者运营": ["D5", "D8"],
    "节日热点借势营销": ["D5", "D7"],

    # D6 传播创意
    "医药品牌微电影创意": ["D6", "D9"],
    "H5互动疾病教育活动": ["D6", "D9"],
    "处方药合规传播创意": ["D6", "D10", "D12"],
    "情感共鸣创意策略": ["D6", "D4"],

    # D7 整合营销
    "ATL与BTL整合营销": ["D7"],
    "学术推广与数字营销结合": ["D7", "D8"],
    "新品上市整合营销规划": ["D7", "D8"],

    # D8 渠道触点
    "药店OTC铺货策略": ["D8"],
    "医院准入与学术推广": ["D8", "D7"],
    "电商私域联动": ["D8", "D7"],

    # D9 执行亮点
    "AIGC医药创意应用": ["D9", "D6"],
    "AR疾病教育体验": ["D9", "D12"],
    "包装设计创新案例": ["D9"],
    "创意装置线下活动": ["D9", "D6"],

    # D10 合规伦理
    "药品广告合规边界": ["D10"],
    "IRB伦理审查流程": ["D10"],
    "药物警戒传播": ["D10", "D12"],
    "处方药社交媒体合规": ["D10", "D5"],

    # D11 成果ROI
    "Cannes获奖案例ROI": ["D11", "D6"],
    "媒介投放效果归因": ["D11", "D7"],
    "品牌健康度衡量": ["D11", "D1"],
    "营销ROI计算框架": ["D11"],

    # D12 传播类型
    "患者教育传播案例": ["D12", "D4", "D3"],
    "疫苗公众认知传播": ["D12", "D10"],
    "医疗器械营销": ["D12", "D2"],
    "OTC产品消费营销": ["D12", "D3", "D8"],
}


def detect_dimension_from_result(text: str) -> set:
    """
    从检索结果文本中推断涉及的维度
    基于关键词匹配
    """
    text_lower = text.lower()
    dims = set()

    # D1 品牌背景
    if any(k in text_lower for k in ["品牌", "brand", "市场地位", "品牌转型", "new brand", "established"]):
        dims.add("D1")

    # D2 竞争定位
    if any(k in text_lower for k in ["竞争", "差异化", "蓝海", "竞争格局", "market leader", "challenger", "differentiation"]):
        dims.add("D2")

    # D3 人群洞察
    if any(k in text_lower for k in ["患者", "医生", "人群", "受众", "patient", "doctor", "audience", "demographics", "HCP"]):
        dims.add("D3")

    # D4 需求洞察
    if any(k in text_lower for k in ["需求", "洞察", "情感", "功能", "疗效", "need", "insight", "anxiety", "efficacy"]):
        dims.add("D4")

    # D5 社媒偏好
    if any(k in text_lower for k in ["抖音", "小红书", "微博", "微信", "B站", "KOL", "UGC", "Douyin", "RED", "social", "viral"]):
        dims.add("D5")

    # D6 传播创意
    if any(k in text_lower for k in ["创意", "微电影", "H5", "AR", "装置", "creative", "concept", "story", "narrative", "copywriting"]):
        dims.add("D6")

    # D7 整合营销
    if any(k in text_lower for k in ["整合营销", "ATL", "BTL", "公关", "媒介", "media", "PR", "GR", "launch"]):
        dims.add("D7")

    # D8 渠道触点
    if any(k in text_lower for k in ["医院", "药店", "电商", "私域", "渠道", "hospital", "pharmacy", "OTC", "private domain", "channel"]):
        dims.add("D8")

    # D9 执行亮点
    if any(k in text_lower for k in ["AIGC", "AR", "VR", "全息", "包装", "装置", "执行", "AIGC", "holographic", "execution", "packaging"]):
        dims.add("D9")

    # D10 合规伦理
    if any(k in text_lower for k in ["合规", "伦理", "NMPA", "FDA", "IRB", "药物警戒", "广告法", "compliance", "ethics", "pharmacovigilance"]):
        dims.add("D10")

    # D11 成果ROI
    if any(k in text_lower for k in ["ROI", "曝光", "互动", "转化", "Cannes", "奖项", "award", "impressions", "engagement", "conversion"]):
        dims.add("D11")

    # D12 传播类型
    if any(k in text_lower for k in ["处方药", "OTC", "器械", "疫苗", "疾病教育", "健康管理", "prescription", "Rx", "vaccine", "awareness"]):
        dims.add("D12")

    return dims


def evaluate_recall(top_k: int = 5):
    """
    对测试查询集执行召回率评估

    Returns:
        dict: {
            dimension_recall: {dim: (hit, total, recall_rate)},
            query_results: {query: {expected, retrieved_dims, hit_dims, hit_rate}},
            weak_dimensions: [dim,...],
            strong_dimensions: [dim,...]
        }
    """
    dim_hits = defaultdict(int)
    dim_totals = defaultdict(int)

    query_results = {}

    for query, expected_dims in TEST_QUERIES.items():
        results = search(query, top_k=top_k)

        # 合并所有检索结果的文本
        all_text = " ".join(r.get("text", "") for r in results)
        retrieved_dims = detect_dimension_from_result(all_text)

        hit_dims = set(expected_dims) & retrieved_dims
        miss_dims = set(expected_dims) - retrieved_dims

        # 记录各维度
        for dim in expected_dims:
            dim_totals[dim] += 1
            if dim in hit_dims:
                dim_hits[dim] += 1

        recall_rate = len(hit_dims) / len(expected_dims) if expected_dims else 0
        query_results[query] = {
            "expected": expected_dims,
            "retrieved_dims": sorted(retrieved_dims),
            "hit_dims": sorted(hit_dims),
            "miss_dims": sorted(miss_dims),
            "recall": round(recall_rate, 2),
            "top_k": top_k,
        }

    # 汇总各维度召回率
    dimension_recall = {}
    for dim in sorted(dim_totals.keys()):
        hits = dim_hits[dim]
        total = dim_totals[dim]
        rate = hits / total if total else 0
        dimension_recall[dim] = (hits, total, rate)

    # 识别强弱维度
    weak = [dim for dim, (_, _, r) in dimension_recall.items() if r < 0.5]
    strong = [dim for dim, (_, _, r) in dimension_recall.items() if r >= 0.8]

    return {
        "dimension_recall": dimension_recall,
        "query_results": query_results,
        "weak_dimensions": weak,
        "strong_dimensions": strong,
        "total_queries": len(TEST_QUERIES),
        "top_k": top_k,
    }


def print_report(report: dict):
    print("=" * 60)
    print("📊 召回率评估报告")
    print(f"   测试查询数: {report['total_queries']}")
    print(f"   Top-K: {report['top_k']}")
    print("=" * 60)

    print("\n🔍 各维度召回率")
    print(f"   {'维度':<6} {'命中':<8} {'总数':<6} {'召回率':<10} {'评级'}")
    print(f"   {'-'*6} {'-'*8} {'-'*6} {'-'*10} {'-'*6}")

    for dim in sorted(report["dimension_recall"].keys()):
        hits, total, rate = report["dimension_recall"][dim]
        if rate >= 0.8:
            rating = "🟢 强"
        elif rate >= 0.5:
            rating = "🟡 中"
        else:
            rating = "🔴 弱"
        print(f"   {dim:<6} {hits:<8} {total:<6} {rate:.1%}{'':5} {rating}")

    # 整体召回率
    all_hits = sum(v[0] for v in report["dimension_recall"].values())
    all_totals = sum(v[1] for v in report["dimension_recall"].values())
    overall = all_hits / all_totals if all_totals else 0
    print(f"\n   整体召回率: {overall:.1%}")

    # 薄弱维度详情
    if report["weak_dimensions"]:
        print(f"\n⚠️  薄弱维度（召回率 < 50%）:")
        for dim in report["weak_dimensions"]:
            print(f"   {dim}: {report['dimension_recall'][dim][2]:.1%}")
        print("\n   建议: 增加相关检索词，扩充知识库内容")

    # 详细查询结果
    print("\n" + "=" * 60)
    print("📋 详细查询结果")
    print("=" * 60)

    for query, res in report["query_results"].items():
        status = "🟢" if res["recall"] == 1.0 else ("🟡" if res["recall"] >= 0.5 else "🔴")
        print(f"\n{status} {query}")
        print(f"   预期: {res['expected']} | 命中: {res['hit_dims']} | 缺失: {res['miss_dims']} | 召回率: {res['recall']:.0%}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="召回率评估")
    parser.add_argument("--top-k", "-k", type=int, default=5,
                        help="检索返回结果数（默认 5）")
    parser.add_argument("--json", "-j", action="store_true",
                        help="输出 JSON 格式（供程序消费）")
    args = parser.parse_args()

    report = evaluate_recall(top_k=args.top_k)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
