"""Security-Aware Query Analyzer 测试: 实体识别 + 查询类型 + 复杂度。"""
from app.rag.analyzer import (
    analyze_query,
    COMPARATIVE,
    CONCEPT,
    EXACT_ENTITY,
    FACTUAL,
    MULTI_HOP,
    PROCEDURAL,
)


def test_cve_entity_recognized():
    a = analyze_query("CVE-2021-44228 漏洞的原理是什么")
    assert a.query_type == EXACT_ENTITY
    assert "CVE-2021-44228" in a.exact_identifiers
    assert a.entity_types.get("cve") == ["CVE-2021-44228"]
    assert a.recommended_strategy == "hybrid"  # 实体问题推荐混合(精确匹配优先)


def test_cwe_and_capec_entities():
    a = analyze_query("CWE-89 与 CAPEC-66 属于哪类漏洞")
    assert a.exact_identifiers == ["CWE-89", "CAPEC-66"]
    assert a.complexity > 3.0  # 多实体交叉 +1


def test_attack_technique_identifier():
    a = analyze_query("T1059 命令行解释器技术的检测方法")
    assert "T1059" in a.exact_identifiers


def test_apt_group_identifier():
    a = analyze_query("APT29 常用什么初始访问手段")
    assert "APT29" in a.exact_identifiers


def test_procedural_query():
    a = analyze_query("如何防御 SQL 注入攻击")
    assert a.query_type == PROCEDURAL
    assert a.recommended_strategy == "hybrid"


def test_concept_query():
    a = analyze_query("什么是零信任架构")
    assert a.query_type == CONCEPT


def test_factual_query():
    a = analyze_query("HTTPS 默认端口是多少")
    assert a.query_type == FACTUAL
    assert a.complexity <= 3.0


def test_comparative_query_two_subjects():
    a = analyze_query("SQL注入和XSS的区别是什么")
    assert a.query_type == COMPARATIVE
    assert a.need_rerank is True


def test_multi_hop_query():
    a = analyze_query("常见的Web漏洞有哪些以及如何检测")
    assert a.query_type == MULTI_HOP
    assert a.needs_multi_hop is True


def test_lexicon_entities():
    a = analyze_query("log4j 组件的远程代码执行漏洞如何修复")
    assert "log4j" in a.entity_types.get("product", [])
    assert "远程代码执行" in a.entity_types.get("attack_tech", [])


def test_protocol_entity():
    a = analyze_query("kerberos 协议的委派攻击原理")
    assert "kerberos" in a.entity_types.get("protocol", [])


def test_empty_and_normal_queries():
    assert analyze_query("").query_type == FACTUAL
    a = analyze_query("你好")
    assert a.query_type == FACTUAL
    assert a.confidence == 0.5  # 兜底置信度


def test_analysis_ms_and_dict():
    a = analyze_query("什么是 CSRF 跨站请求伪造")
    d = a.to_dict()
    assert d["queryType"] == CONCEPT
    assert "queryType" in d and "complexity" in d and "exactIdentifiers" in d
    assert a.analysis_ms >= 0


def test_analysis_is_fast():
    import time

    start = time.perf_counter()
    for _ in range(100):
        analyze_query("如何检测和防御 CVE-2021-44228 log4j 反序列化漏洞")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 2000  # 100 次 < 2s, 即单次平均 < 20ms(实际远低于)


def test_exact_entity_beats_procedural_intent():
    """优先级: 精确实体 > 过程意图(CVE 问题即使含"如何"也走实体路由)"""
    a = analyze_query("如何修复 CVE-2024-3094")
    assert a.query_type == EXACT_ENTITY
