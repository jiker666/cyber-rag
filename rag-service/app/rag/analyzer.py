"""Security-Aware Query Analyzer: 纯规则(Regex/词典/轻量逻辑)的查询理解, 亚毫秒级。

不调用 LLM —— 分析本身不引入生成延迟。
输出 QueryAnalysis 指导后续检索路由(见 adaptive.py), 并写入 Trace 供实验分析。

核心思想: 网络安全问题高频携带结构化安全实体(CVE/CWE/ATT&CK 编号等)与
明显的意图模式(什么是/如何/对比), 这些先验足以在检索前判断:
  - 该用精确匹配增强还是纯语义检索
  - 候选规模该多大
  - 是否可能需要多跳
"""
import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger("cyber-rag.rag.analyzer")

# ---------------------------------------------------------------- 实体识别
# 结构化安全标识符(精确 ID, 参与 exact-term boost)
ENTITY_PATTERNS: dict[str, re.Pattern] = {
    "cve": re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    "cwe": re.compile(r"\bCWE-\d{1,4}\b", re.IGNORECASE),
    "capec": re.compile(r"\bCAPEC-\d{1,4}\b", re.IGNORECASE),
    "attack_technique": re.compile(r"\bT\d{4}(?:\.\d{3})?\b"),
    "attack_group": re.compile(r"\b(?:APT\d{1,2}|G\d{4})\b"),
    "owasp": re.compile(r"\bOWASP(?:\s+(?:API\s+)?Security\s+Top\s+10)?\b", re.IGNORECASE),
}

# 协议名(小写匹配)
PROTOCOL_LEXICON = {
    "http", "https", "ssh", "ftp", "ftps", "smtp", "dns", "tcp", "udp", "tls", "ssl",
    "ldap", "ldaps", "rdp", "smb", "icmp", "snmp", "telnet", "smtps", "imap", "pop3",
    "kerberos", "ntlm", "oauth", "openid", "saml", "jwt", "wss", "grpc", "mqtt",
}

# 安全产品/组件名(小写匹配)
PRODUCT_LEXICON = {
    "log4j", "log4shell", "struts", "struts2", "spring", "spring boot", "tomcat",
    "nginx", "apache", "shiro", "fastjson", "weblogic", "jboss", "jackson",
    "docker", "kubernetes", "k8s", "redis", "mysql", "elasticsearch", "shindig",
    "waf", "ids", "ips", "siem", "soc", "bastion", "kms", "hsm",
}

# 攻击技术中文名
ATTACK_TECH_ZH = {
    "sql注入", "注入攻击", "xss", "跨站脚本", "csrf", "跨站请求伪造", "ssrf",
    "服务端请求伪造", "命令注入", "代码注入", "文件上传", "任意文件上传",
    "反序列化", "不安全反序列化", "路径穿越", "目录穿越", "越权", "水平越权",
    "垂直越权", "信息泄露", "暴力破解", "撞库", "钓鱼", "鱼叉钓鱼", "水坑攻击",
    "供应链攻击", "勒索软件", "挖矿", "webshell", "提权", "横向移动", "持久化",
    "凭证窃取", "密码喷洒", "会话劫持", "重放攻击", "点击劫持", "缓存投毒",
    "XXE", "RCE", "远程代码执行", "BOLA", "BFLA", "失效的对象级授权",
}

# 防御技术中文名
DEFENSE_TECH_ZH = {
    "参数化查询", "预编译", "输入校验", "输入过滤", "输出编码", "转义",
    "最小权限", "权限校验", "访问控制", "白名单", "黑名单", "内容安全策略",
    "CSP", "SameSite", "Token", "双因素认证", "多因素认证", "密码哈希",
    "盐值", "加密", "解密", "签名", "验签", "证书", "审计日志", "监控告警",
    "入侵检测", "漏洞扫描", "渗透测试", "安全编码", "安全配置", "沙箱隔离",
    "网络隔离", "零信任", "纵深防御", "安全头", "速率限制", "限流",
}

# ---------------------------------------------------------------- 意图模式
_COMPARATIVE_RE = re.compile(
    r"(和|与|跟|对比|比较|区别|差异|不同|分别|哪个更|vs\.?)", re.IGNORECASE
)
_PROCEDURAL_RE = re.compile(
    r"(如何|怎么|怎样|怎么才能|步骤|方法|措施|方案|手段|实践|部署|配置|加固|修复| remediate|防御|防护|防止|防范|检测|排查|防范|应对|实现|编写|代码)"
)
_CONCEPT_RE = re.compile(r"(什么是|是什么|何为|指的是|原理|概念|定义|介绍|解释|概述|理解|通俗)")
_FACTUAL_RE = re.compile(r"(哪些|哪个|多少|谁|何时|什么时候|版本|默认|支持|属于|包括|包含|名单|列举)")
_MULTI_HOP_RE = re.compile(
    r"(哪些.{2,24}(如何|怎么|怎样|检测|防御)|(以及|然后|接着|并且|同时|再).{0,14}"
    r"(如何|怎么|怎样|为什么|检测|防御|防范|修复)|这些(技术|方法|漏洞).{0,10}(如何|怎么|怎样))"
)
_CODE_RE = re.compile(r"(代码|示例|例子|命令|配置文件|写一个|实现一个|code)")

_ASCII_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,30}")
_CJK_RUN_RE = re.compile(r"[一-鿿]{2,8}")

# 查询类型
EXACT_ENTITY = "EXACT_ENTITY"
FACTUAL = "FACTUAL"
PROCEDURAL = "PROCEDURAL"
CONCEPT = "CONCEPT"
COMPARATIVE = "COMPARATIVE"
MULTI_HOP = "MULTI_HOP"

# 类型 → 基础复杂度(0-10)
_BASE_COMPLEXITY = {
    EXACT_ENTITY: 2.0,
    FACTUAL: 1.5,
    CONCEPT: 3.0,
    PROCEDURAL: 4.0,
    COMPARATIVE: 6.5,
    MULTI_HOP: 8.0,
}

# 类型 → 推荐检索策略与 Top-K(路由初始值, 实验校准)
_RECOMMENDED = {
    EXACT_ENTITY: ("hybrid", 5),
    FACTUAL: ("vector", 3),
    CONCEPT: ("vector", 5),
    PROCEDURAL: ("hybrid", 5),
    COMPARATIVE: ("hybrid", 6),
    MULTI_HOP: ("hybrid", 8),
}


@dataclass
class QueryAnalysis:
    """查询理解结果(与论文/前端"RAG 决策"面板字段一一对应)。"""

    query_type: str = FACTUAL
    complexity: float = 1.5  # 0-10
    security_entities: list[str] = field(default_factory=list)  # 命中的全部安全实体
    entity_types: dict[str, list[str]] = field(default_factory=dict)  # {cve: [...], ...}
    exact_identifiers: list[str] = field(default_factory=list)  # 参与精确强匹配的 ID(大写)
    keywords: list[str] = field(default_factory=list)  # 内容词(ascii 术语 + 中文术语)
    needs_multi_hop: bool = False
    recommended_strategy: str = "vector"
    recommended_top_k: int = 5
    need_rerank: bool = False  # 检索前预判(比较/多跳 → 倾向重排)
    confidence: float = 0.5  # 分类置信度(规则匹配强度)
    analysis_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "queryType": self.query_type,
            "complexity": round(self.complexity, 1),
            "securityEntities": self.security_entities,
            "entityTypes": self.entity_types,
            "exactIdentifiers": self.exact_identifiers,
            "keywords": self.keywords[:12],
            "needsMultiHop": self.needs_multi_hop,
            "recommendedStrategy": self.recommended_strategy,
            "recommendedTopK": self.recommended_top_k,
            "needRerank": self.need_rerank,
            "confidence": round(self.confidence, 2),
            "analysisMs": self.analysis_ms,
        }


def _extract_entities(text: str) -> tuple[list[str], dict[str, list[str]], list[str]]:
    entities: list[str] = []
    by_type: dict[str, list[str]] = {}
    exact_ids: list[str] = []
    lowered = text.lower()
    for etype, pattern in ENTITY_PATTERNS.items():
        for m in pattern.finditer(text):
            raw = m.group(0)
            if etype == "attack_technique" and re.fullmatch(r"T\d{4}", raw):
                # 排除误命中: T1059 合法, 但 "T1234" 形态在纯中文语境极少误报, 保留
                pass
            normalized = raw.upper() if etype in ("cve", "cwe", "capec", "owasp") else raw
            if normalized not in by_type.setdefault(etype, []):
                by_type[etype].append(normalized)
                entities.append(normalized)
                if etype in ("cve", "cwe", "capec", "attack_technique", "attack_group"):
                    exact_ids.append(normalized)
    # 词典实体(协议/产品/攻击技术/防御技术)
    for proto in PROTOCOL_LEXICON:
        if re.search(rf"\b{re.escape(proto)}\b", lowered):
            by_type.setdefault("protocol", []).append(proto)
            entities.append(proto)
    for product in PRODUCT_LEXICON:
        if product in lowered:
            by_type.setdefault("product", []).append(product)
            entities.append(product)
    for tech in ATTACK_TECH_ZH:
        if tech.lower() in lowered:
            by_type.setdefault("attack_tech", []).append(tech)
            entities.append(tech)
    for tech in DEFENSE_TECH_ZH:
        if tech.lower() in lowered:
            by_type.setdefault("defense_tech", []).append(tech)
            entities.append(tech)
    return entities, by_type, exact_ids


def _extract_keywords(text: str) -> list[str]:
    """内容词: ASCII 术语(≥2 字符, 去停用词) + 中文连串片段。"""
    stop = {"如何", "怎么", "怎样", "什么", "哪些", "为什么", "是否", "以及", "然后",
            "the", "is", "are", "what", "how", "why", "and", "or", "in", "of", "a"}
    words: list[str] = []
    for m in _ASCII_TERM_RE.finditer(text):
        w = m.group(0)
        if w.lower() not in stop:
            words.append(w)
    for m in _CJK_RUN_RE.finditer(text):
        run = m.group(0)
        if run not in stop and len(run) >= 2:
            words.append(run)
    # 保序去重
    seen: set[str] = set()
    return [w for w in words if not (w in seen or seen.add(w))]


def analyze_query(question: str) -> QueryAnalysis:
    """规则式查询理解入口(亚毫秒)。"""
    start = time.perf_counter()
    text = (question or "").strip()

    entities, by_type, exact_ids = _extract_entities(text)
    is_multi_hop = bool(_MULTI_HOP_RE.search(text))
    comparative_mark = _COMPARATIVE_RE.search(text)

    # ---- 查询类型判定(优先级: 多跳 > 比较 > 精确实体 > 过程 > 概念 > 事实) ----
    if is_multi_hop:
        qtype, confidence = MULTI_HOP, 0.85
    elif comparative_mark and _has_two_subjects(text):
        qtype, confidence = COMPARATIVE, 0.85
    elif exact_ids:
        # 有精确编号但问句主体是比较时上面已拦截; 其余视为实体直查
        qtype, confidence = EXACT_ENTITY, 0.95
    elif _PROCEDURAL_RE.search(text):
        qtype, confidence = PROCEDURAL, 0.9
    elif _CONCEPT_RE.search(text):
        qtype, confidence = CONCEPT, 0.9
    elif _FACTUAL_RE.search(text):
        qtype, confidence = FACTUAL, 0.75
    else:
        qtype, confidence = FACTUAL, 0.5  # 兜底

    # ---- 复杂度(0-10) ----
    complexity = _BASE_COMPLEXITY[qtype]
    if len(exact_ids) >= 2:
        complexity += 1.0  # 多实体交叉
    if len(text) > 40:
        complexity += 0.5
    if len(text) > 80:
        complexity += 0.5
    intents = len(re.findall(r"如何|怎么|怎样|为什么|什么", text))
    if intents >= 2:
        complexity += 1.0
    if _CODE_RE.search(text):
        complexity += 0.5
    complexity = min(complexity, 10.0)

    strategy, top_k = _RECOMMENDED[qtype]
    analysis = QueryAnalysis(
        query_type=qtype,
        complexity=round(complexity, 1),
        security_entities=entities,
        entity_types=by_type,
        exact_identifiers=exact_ids,
        keywords=_extract_keywords(text),
        needs_multi_hop=is_multi_hop or complexity >= 9.0,
        recommended_strategy=strategy,
        recommended_top_k=top_k,
        need_rerank=qtype in (COMPARATIVE, MULTI_HOP),
        confidence=confidence,
    )
    analysis.analysis_ms = int((time.perf_counter() - start) * 1000)
    return analysis


def _has_two_subjects(text: str) -> bool:
    """比较类问题需要两个主体: "X 和 Y 区别" 或 "X 与 Y" (X/Y 为非空内容词)。"""
    m = re.search(r"(.{1,24}?)(?:和|与|跟|vs\.?|对比)(.{1,24}?)(?:的)?(?:区别|差异|不同)", text, re.IGNORECASE)
    if m:
        return bool(m.group(1).strip()) and bool(m.group(2).strip())
    return bool(_COMPARATIVE_RE.search(text)) and len(_extract_keywords(text)) >= 2
