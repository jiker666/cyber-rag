package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.entity.RagConfig;
import com.cyberrag.mapper.RagConfigMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.RagConfigService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * RAG 配置服务实现。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RagConfigServiceImpl extends ServiceImpl<RagConfigMapper, RagConfig> implements RagConfigService {

    private final RagConfigMapper configMapper;

    @Override
    public RagConfig getConfig() {
        RagConfig config = configMapper.selectById(1L);
        if (config == null) {
            config = defaultConfig();
            configMapper.insert(config);
        }
        return config;
    }

    @Override
    public RagConfig update(RagConfig config) {
        validate(config);
        RagConfig current = configMapper.selectById(1L);
        if (current == null) {
            current = defaultConfig();
        }
        current.setChunkSize(config.getChunkSize());
        current.setChunkOverlap(config.getChunkOverlap());
        current.setTopK(config.getTopK());
        current.setTemperature(config.getTemperature());
        current.setScoreThreshold(config.getScoreThreshold());
        current.setEnableReranker(config.getEnableReranker());
        current.setRerankTopN(config.getRerankTopN());
        current.setRetrievalStrategy(normalizeStrategy(config.getRetrievalStrategy()));
        current.setHistoryWindow(config.getHistoryWindow());
        current.setUpdatedBy(AuthContext.getUserId());
        if (current.getId() == null) {
            current.setId(1L);
            configMapper.insert(current);
        } else {
            configMapper.updateById(current);
        }
        log.info("RAG 配置已更新: topK={}, chunkSize={}, overlap={}, strategy={}, reranker={}",
                current.getTopK(), current.getChunkSize(), current.getChunkOverlap(),
                current.getRetrievalStrategy(), current.getEnableReranker());
        return current;
    }

    /** 检索策略仅允许 vector/hybrid, 空值回退 vector。 */
    private String normalizeStrategy(String strategy) {
        if (strategy == null || strategy.isBlank()) {
            return "vector";
        }
        String normalized = strategy.trim().toLowerCase();
        if (!"vector".equals(normalized) && !"hybrid".equals(normalized)) {
            throw new BusinessException(400, "检索策略仅支持 vector 或 hybrid");
        }
        return normalized;
    }

    private void validate(RagConfig c) {
        if (c.getChunkSize() == null || c.getChunkSize() < 64 || c.getChunkSize() > 4096) {
            throw new BusinessException(400, "Chunk Size 取值范围 64-4096");
        }
        if (c.getChunkOverlap() == null || c.getChunkOverlap() < 0 || c.getChunkOverlap() >= c.getChunkSize()) {
            throw new BusinessException(400, "Chunk Overlap 必须满足 0 ≤ overlap < chunkSize");
        }
        if (c.getTopK() == null || c.getTopK() < 1 || c.getTopK() > 50) {
            throw new BusinessException(400, "Top-K 取值范围 1-50");
        }
        if (c.getTemperature() == null
                || c.getTemperature().compareTo(BigDecimal.ZERO) < 0
                || c.getTemperature().compareTo(new BigDecimal("2")) > 0) {
            throw new BusinessException(400, "Temperature 取值范围 0-2");
        }
        if (c.getRerankTopN() == null || c.getRerankTopN() < 1) {
            c.setRerankTopN(3);
        }
        if (c.getHistoryWindow() == null || c.getHistoryWindow() < 0) {
            c.setHistoryWindow(6);
        }
        if (c.getEnableReranker() == null) {
            c.setEnableReranker(0);
        }
    }

    private RagConfig defaultConfig() {
        RagConfig c = new RagConfig();
        c.setId(1L);
        c.setChunkSize(512);
        c.setChunkOverlap(100);
        c.setTopK(5);
        c.setTemperature(new BigDecimal("0.30"));
        c.setScoreThreshold(new BigDecimal("0.30"));
        c.setEnableReranker(0);
        c.setRerankTopN(3);
        c.setRetrievalStrategy("vector");
        c.setHistoryWindow(6);
        return c;
    }
}
