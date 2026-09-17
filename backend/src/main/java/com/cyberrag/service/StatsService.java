package com.cyberrag.service;

import java.util.List;
import java.util.Map;

/**
 * 后台统计服务。
 */
public interface StatsService {

    /** Dashboard 总览卡片 */
    Map<String, Object> overview();

    /** 最近 N 天问答趋势 */
    List<Map<String, Object>> qaTrend(int days);

    /** 热门问题类别(按知识库类别统计问答量) */
    List<Map<String, Object>> hotCategories(int limit);

    /** 知识库使用占比 */
    List<Map<String, Object>> kbUsage(int limit);

    /** 最近问答记录 */
    List<Map<String, Object>> recentQa(int limit);
}
