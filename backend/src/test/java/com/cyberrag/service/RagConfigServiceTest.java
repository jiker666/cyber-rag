package com.cyberrag.service;

import com.cyberrag.BaseTest;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.entity.RagConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * RAG 全局配置测试: 重点回归 retrievalStrategy 必须随保存请求持久化
 * (历史缺陷: update() 未回写该字段, 设置页切换混合检索被静默丢弃)。
 */
class RagConfigServiceTest extends BaseTest {

    @Autowired
    private RagConfigService ragConfigService;

    @Test
    void update_persists_retrieval_strategy() {
        RagConfig config = ragConfigService.getConfig();
        config.setRetrievalStrategy("hybrid");
        ragConfigService.update(config);

        assertEquals("hybrid", ragConfigService.getConfig().getRetrievalStrategy());

        // 还原, 避免影响同上下文的其他测试
        config.setRetrievalStrategy("vector");
        ragConfigService.update(config);
    }

    @Test
    void update_rejects_invalid_strategy() {
        RagConfig config = ragConfigService.getConfig();
        config.setRetrievalStrategy("bm25");
        assertThrows(BusinessException.class, () -> ragConfigService.update(config));
    }

    @Test
    void update_blank_strategy_falls_back_to_vector() {
        RagConfig config = ragConfigService.getConfig();
        config.setRetrievalStrategy("  ");
        assertEquals("vector", ragConfigService.update(config).getRetrievalStrategy());
    }
}
