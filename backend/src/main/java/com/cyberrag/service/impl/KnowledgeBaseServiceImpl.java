package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.kb.KbUpsertRequest;
import com.cyberrag.entity.KnowledgeBase;
import com.cyberrag.integration.RagServiceClient;
import com.cyberrag.mapper.KnowledgeBaseMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.KnowledgeBaseService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;

/**
 * 知识库服务实现。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeBaseServiceImpl extends ServiceImpl<KnowledgeBaseMapper, KnowledgeBase>
        implements KnowledgeBaseService {

    private final KnowledgeBaseMapper kbMapper;
    private final RagServiceClient ragClient;

    @Override
    public KnowledgeBase create(KbUpsertRequest request) {
        Long exists = kbMapper.selectCount(new LambdaQueryWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getName, request.getName()));
        if (exists > 0) {
            throw new BusinessException(409, "知识库名称已存在");
        }
        KnowledgeBase kb = new KnowledgeBase();
        kb.setName(request.getName());
        kb.setDescription(request.getDescription());
        kb.setCategory(request.getCategory());
        kb.setCoverColor(StringUtils.hasText(request.getCoverColor()) ? request.getCoverColor() : "#409EFF");
        kb.setDocCount(0);
        kb.setChunkCount(0);
        kb.setStatus(request.getStatus() != null ? request.getStatus() : 1);
        kb.setCreatedBy(AuthContext.getUserId());
        kbMapper.insert(kb);
        log.info("创建知识库: id={}, name={}", kb.getId(), kb.getName());
        return kb;
    }

    @Override
    public KnowledgeBase update(long id, KbUpsertRequest request) {
        KnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        kb.setName(request.getName());
        kb.setDescription(request.getDescription());
        kb.setCategory(request.getCategory());
        kb.setCoverColor(request.getCoverColor());
        if (request.getStatus() != null) {
            kb.setStatus(request.getStatus());
        }
        kbMapper.updateById(kb);
        return kb;
    }

    @Override
    public void delete(long id) {
        KnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        if (kb.getDocCount() != null && kb.getDocCount() > 0) {
            throw new BusinessException(400, "知识库下仍有 " + kb.getDocCount() + " 个文档, 请先清空文档");
        }
        kbMapper.deleteById(id);
        ragClient.deleteCollection(id); // 同步清理向量集合(忽略不存在)
        log.info("删除知识库: id={}", id);
    }

    @Override
    public IPage<KnowledgeBase> page(long page, long size, String keyword, String category) {
        LambdaQueryWrapper<KnowledgeBase> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(keyword)) {
            wrapper.like(KnowledgeBase::getName, keyword)
                    .or().like(KnowledgeBase::getDescription, keyword);
        }
        if (StringUtils.hasText(category)) {
            wrapper.eq(KnowledgeBase::getCategory, category);
        }
        wrapper.orderByDesc(KnowledgeBase::getUpdatedAt);
        return kbMapper.selectPage(new Page<>(page, size), wrapper);
    }

    @Override
    public List<KnowledgeBase> listEnabled() {
        return kbMapper.selectList(new LambdaQueryWrapper<KnowledgeBase>()
                .eq(KnowledgeBase::getStatus, 1)
                .orderByDesc(KnowledgeBase::getUpdatedAt));
    }

    @Override
    public KnowledgeBase refreshStats(long id) {
        KnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        try {
            Map<String, Object> stats = ragClient.ingestStats(id);
            kb.setChunkCount(((Number) stats.getOrDefault("chunkCount", 0)).intValue());
            kb.setDocCount(((Number) stats.getOrDefault("documentCount", 0)).intValue());
            kbMapper.updateById(kb);
        } catch (BusinessException e) {
            log.warn("刷新知识库统计失败(向量服务不可用): {}", e.getMessage());
        }
        return kb;
    }

    @Override
    public void increaseDocCount(long id, int delta) {
        KnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            return;
        }
        kb.setDocCount(Math.max(0, (kb.getDocCount() == null ? 0 : kb.getDocCount()) + delta));
        kbMapper.updateById(kb);
    }

    @Override
    public void updateChunkCount(long id, int chunkCount) {
        KnowledgeBase kb = kbMapper.selectById(id);
        if (kb == null) {
            return;
        }
        kb.setChunkCount(Math.max(0, chunkCount));
        kbMapper.updateById(kb);
    }
}
