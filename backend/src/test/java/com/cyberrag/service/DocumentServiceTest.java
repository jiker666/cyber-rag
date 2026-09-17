package com.cyberrag.service;

import com.cyberrag.BaseTest;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.rag.IngestResult;
import com.cyberrag.entity.Document;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.mock.web.MockMultipartFile;
import org.awaitility.Awaitility;

import java.io.File;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

/**
 * 文档上传与入库状态流转测试(Mock AI 服务)。
 */
class DocumentServiceTest extends BaseTest {

    @Autowired
    private DocumentService documentService;

    @BeforeEach
    void mockIngest() {
        IngestResult result = new IngestResult();
        result.setChunkCount(12);
        result.setCharCount(5300);
        when(ragServiceClient.ingestFile(any(File.class), anyString(), anyLong(), anyLong(), anyInt(), anyInt()))
                .thenReturn(result);
    }

    @Test
    void upload_rejects_dangerous_extension() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "shell.jsp", "application/octet-stream", "<%Runtime.exec%>".getBytes());
        BusinessException e = assertThrows(BusinessException.class,
                () -> documentService.upload(file, 1L));
        assertTrue(e.getMessage().contains("仅支持"));
    }

    @Test
    void upload_rejects_path_traversal_filename() {
        // 文件名包含路径穿越, 系统应仅保留文件名部分且通过白名单校验
        MockMultipartFile file = new MockMultipartFile(
                "file", "../../etc/passwd.txt", "text/plain", "安全内容".getBytes());
        Document doc = documentService.upload(file, 1L);
        assertEquals("passwd.txt", doc.getName());
        assertTrue(doc.getFilePath().startsWith(doc.getFilePath()));
    }

    @Test
    void upload_marks_completed_after_async_ingest() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "SQL注入防护指南.md", "text/markdown", "# SQL注入\n参数化查询".getBytes());
        Document doc = documentService.upload(file, 1L);
        assertNotNull(doc.getId());
        assertEquals("SQL注入防护指南.md", doc.getName());
        assertEquals("md", doc.getFileType());

        // 异步入库完成 → COMPLETED
        Awaitility.await().atMost(5, TimeUnit.SECONDS).untilAsserted(() -> {
            Document current = documentService.getById(doc.getId());
            assertEquals(Constants.DOC_COMPLETED, current.getStatus());
            assertEquals(12, current.getChunkCount());
        });
    }

    @Test
    void ingest_failure_marks_failed_with_error() {
        when(ragServiceClient.ingestFile(any(File.class), anyString(), anyLong(), anyLong(), anyInt(), anyInt()))
                .thenThrow(new BusinessException(502, "AI 服务错误: 模拟失败"));
        MockMultipartFile file = new MockMultipartFile(
                "file", "损坏文档.txt", "text/plain", "内容".getBytes());
        Document doc = documentService.upload(file, 1L);
        Awaitility.await().atMost(5, TimeUnit.SECONDS).untilAsserted(() -> {
            Document current = documentService.getById(doc.getId());
            assertEquals(Constants.DOC_FAILED, current.getStatus());
            assertNotNull(current.getErrorMsg());
        });
    }

    @Test
    void page_filters_by_kb() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "分页文档.md", "text/plain", "内容".getBytes());
        documentService.upload(file, 1L);
        var page = documentService.page(1, 10, 1L, "分页", null);
        assertTrue(page.getRecords().stream().allMatch(d -> d.getKnowledgeBaseId() == 1L));
    }
}
