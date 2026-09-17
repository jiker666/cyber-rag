package com.cyberrag.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.cyberrag.dto.kb.KbUpsertRequest;
import com.cyberrag.entity.KnowledgeBase;

import java.util.List;

/**
 * 知识库服务。
 */
public interface KnowledgeBaseService extends IService<KnowledgeBase> {

    KnowledgeBase create(KbUpsertRequest request);

    KnowledgeBase update(long id, KbUpsertRequest request);

    void delete(long id);

    IPage<KnowledgeBase> page(long page, long size, String keyword, String category);

    List<KnowledgeBase> listEnabled();

    /** 从向量库同步 chunk/doc 统计并刷新 */
    KnowledgeBase refreshStats(long id);

    void increaseDocCount(long id, int delta);

    void updateChunkCount(long id, int chunkCount);
}
