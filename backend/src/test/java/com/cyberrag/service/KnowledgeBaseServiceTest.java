package com.cyberrag.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.cyberrag.BaseTest;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.kb.KbUpsertRequest;
import com.cyberrag.entity.KnowledgeBase;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 知识库 CRUD 测试。
 */
class KnowledgeBaseServiceTest extends BaseTest {

    @Autowired
    private KnowledgeBaseService kbService;

    private KbUpsertRequest request(String name) {
        KbUpsertRequest req = new KbUpsertRequest();
        req.setName(name);
        req.setDescription("测试知识库描述");
        req.setCategory("Java安全");
        return req;
    }

    @Test
    void create_and_query() {
        KnowledgeBase kb = kbService.create(request("测试知识库A"));
        assertNotNull(kb.getId());
        KnowledgeBase found = kbService.getById(kb.getId());
        assertEquals("测试知识库A", found.getName());
        assertEquals(0, found.getDocCount());
        assertTrue(found.getStatus() == 1);
    }

    @Test
    void create_rejects_duplicate_name() {
        kbService.create(request("重复知识库"));
        assertThrows(BusinessException.class, () -> kbService.create(request("重复知识库")));
    }

    @Test
    void update_changes_fields() {
        KnowledgeBase kb = kbService.create(request("待更新知识库"));
        KbUpsertRequest update = request("已更新知识库");
        update.setDescription("新描述");
        KnowledgeBase updated = kbService.update(kb.getId(), update);
        assertEquals("已更新知识库", updated.getName());
    }

    @Test
    void delete_empty_kb_succeeds() {
        KnowledgeBase kb = kbService.create(request("待删除知识库"));
        kbService.delete(kb.getId());
        // 逻辑删除后不再可见
        assertEquals(null, kbService.getById(kb.getId()));
    }

    @Test
    void page_returns_records() {
        kbService.create(request("分页知识库1"));
        kbService.create(request("分页知识库2"));
        IPage<KnowledgeBase> page = kbService.page(1, 10, "分页知识库", null);
        assertTrue(page.getRecords().size() >= 2);
    }
}
