package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.entity.Document;
import com.cyberrag.entity.KnowledgeBase;
import com.cyberrag.entity.RagConfig;
import com.cyberrag.integration.RagServiceClient;
import com.cyberrag.mapper.DocumentMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.DocumentService;
import com.cyberrag.service.KnowledgeBaseService;
import com.cyberrag.service.RagConfigService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 文档服务实现。
 *
 * 安全设计:
 * - 扩展名白名单校验
 * - 随机文件名存储(防目录穿越/恶意文件名)
 * - 存储路径规范化后必须位于上传根目录内
 * - 文件大小双重限制(Multipart 层 + 业务层)
 */
@Slf4j
@Service
public class DocumentServiceImpl extends ServiceImpl<DocumentMapper, Document> implements DocumentService {

    private final DocumentMapper documentMapper;
    private final KnowledgeBaseService kbService;
    private final RagConfigService ragConfigService;
    private final RagServiceClient ragClient;
    private final Path uploadRoot;
    private final ExecutorService ingestExecutor = Executors.newFixedThreadPool(2, r -> {
        Thread t = new Thread(r, "doc-ingest");
        t.setDaemon(true);
        return t;
    });

    public DocumentServiceImpl(DocumentMapper documentMapper,
                               KnowledgeBaseService kbService,
                               RagConfigService ragConfigService,
                               RagServiceClient ragClient,
                               @Value("${app.upload.dir:./data/uploads}") String uploadDir) {
        this.documentMapper = documentMapper;
        this.kbService = kbService;
        this.ragConfigService = ragConfigService;
        this.ragClient = ragClient;
        this.uploadRoot = Paths.get(uploadDir).toAbsolutePath().normalize();
        try {
            Files.createDirectories(uploadRoot);
        } catch (IOException e) {
            throw new IllegalStateException("无法创建上传目录: " + uploadRoot, e);
        }
    }

    @Override
    public Document upload(MultipartFile file, long knowledgeBaseId) {
        KnowledgeBase kb = kbService.getById(knowledgeBaseId);
        if (kb == null) {
            throw new BusinessException(404, "知识库不存在");
        }
        String originalName = file.getOriginalFilename();
        if (!StringUtils.hasText(originalName)) {
            throw new BusinessException(400, "文件名不能为空");
        }
        // 仅保留文件名部分, 防目录穿越; 白名单校验扩展名
        originalName = Paths.get(originalName).getFileName().toString();
        String ext = StringUtils.getFilenameExtension(originalName);
        if (ext == null || !Constants.ALLOWED_EXTENSIONS.contains(ext.toLowerCase(Locale.ROOT))) {
            throw new BusinessException(400, "仅支持 PDF/TXT/Markdown/DOCX 格式文档");
        }
        if (file.getSize() > Constants.MAX_FILE_SIZE_MB * 1024L * 1024L) {
            throw new BusinessException(413, "文件大小超过 " + Constants.MAX_FILE_SIZE_MB + "MB 限制");
        }

        // 随机文件名落盘
        String storedName = UUID.randomUUID().toString().replace("-", "") + "." + ext.toLowerCase(Locale.ROOT);
        Path target = uploadRoot.resolve(storedName).normalize();
        if (!target.startsWith(uploadRoot)) {
            throw new BusinessException(400, "非法文件路径");
        }
        try {
            file.transferTo(target);
        } catch (IOException e) {
            log.error("文件保存失败", e);
            throw new BusinessException(500, "文件保存失败");
        }

        Document doc = new Document();
        doc.setKnowledgeBaseId(knowledgeBaseId);
        doc.setName(originalName);
        doc.setFileType(ext.toLowerCase(Locale.ROOT));
        doc.setFileSize(file.getSize());
        doc.setFilePath(storedName);
        doc.setChunkCount(0);
        doc.setCharCount(0);
        doc.setStatus(Constants.DOC_PENDING);
        doc.setCreatedBy(AuthContext.getUserId());
        documentMapper.insert(doc);
        kbService.increaseDocCount(knowledgeBaseId, 1);
        log.info("文档上传: id={}, name={}, size={}KB, kb={}", doc.getId(), originalName,
                file.getSize() / 1024, knowledgeBaseId);

        // 异步执行入库(解析/切片/向量化), 前端轮询状态
        long docId = doc.getId();
        ingestExecutor.submit(() -> {
            try {
                process(docId);
            } catch (Exception e) {
                log.error("文档异步入库异常: docId={}", docId, e);
                markFailed(docId, "系统异常: " + e.getMessage());
            }
        });
        return doc;
    }

    @Override
    public void process(long documentId) {
        Document doc = documentMapper.selectById(documentId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }
        RagConfig config = ragConfigService.getConfig();
        Path path = uploadRoot.resolve(doc.getFilePath()).normalize();
        if (!path.startsWith(uploadRoot) || !Files.exists(path)) {
            markFailed(documentId, "源文件不存在或已丢失");
            throw new BusinessException(404, "源文件不存在");
        }
        try {
            updateStatus(documentId, Constants.DOC_PARSING, null);
            updateStatus(documentId, Constants.DOC_EMBEDDING, null);
            var result = ragClient.ingestFile(
                    path.toFile(), doc.getName(), doc.getKnowledgeBaseId(), documentId,
                    config.getChunkSize(), config.getChunkOverlap());
            doc.setChunkCount(result.getChunkCount());
            doc.setCharCount(result.getCharCount());
            doc.setStatus(Constants.DOC_COMPLETED);
            doc.setErrorMsg(null);
            documentMapper.updateById(doc);
            kbService.refreshStats(doc.getKnowledgeBaseId());
            log.info("文档入库完成: id={}, chunks={}", documentId, result.getChunkCount());
        } catch (Exception e) {
            log.error("文档入库失败: docId={}", documentId, e);
            markFailed(documentId, e.getMessage());
            throw e instanceof BusinessException be ? be : new BusinessException(500, "入库失败");
        }
    }

    @Override
    public void reingest(long documentId) {
        Document doc = documentMapper.selectById(documentId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }
        long docId = doc.getId();
        ingestExecutor.submit(() -> {
            try {
                process(docId);
            } catch (Exception e) {
                log.error("重新向量化失败: docId={}", docId, e);
                markFailed(docId, "重新向量化失败: " + e.getMessage());
            }
        });
    }

    @Override
    public void deleteDocument(long documentId) {
        Document doc = documentMapper.selectById(documentId);
        if (doc == null) {
            throw new BusinessException(404, "文档不存在");
        }
        // 先删向量库数据, 再删业务记录与源文件
        try {
            ragClient.deleteDocumentVectors(doc.getKnowledgeBaseId(), documentId);
        } catch (BusinessException e) {
            log.warn("删除向量数据失败(继续删除业务记录): {}", e.getMessage());
        }
        documentMapper.deleteById(documentId);
        kbService.increaseDocCount(doc.getKnowledgeBaseId(), -1);
        kbService.refreshStats(doc.getKnowledgeBaseId());
        try {
            Files.deleteIfExists(uploadRoot.resolve(doc.getFilePath()));
        } catch (IOException e) {
            log.warn("源文件删除失败: {}", doc.getFilePath());
        }
        log.info("文档删除: id={}, name={}", documentId, doc.getName());
    }

    @Override
    public IPage<Document> page(long page, long size, long knowledgeBaseId, String keyword, String status) {
        LambdaQueryWrapper<Document> wrapper = new LambdaQueryWrapper<>();
        if (knowledgeBaseId > 0) {
            wrapper.eq(Document::getKnowledgeBaseId, knowledgeBaseId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.like(Document::getName, keyword);
        }
        if (StringUtils.hasText(status)) {
            wrapper.eq(Document::getStatus, status);
        }
        wrapper.orderByDesc(Document::getCreatedAt);
        return documentMapper.selectPage(new Page<>(page, size), wrapper);
    }

    private void updateStatus(long id, String status, String error) {
        Document doc = documentMapper.selectById(id);
        if (doc != null) {
            doc.setStatus(status);
            doc.setErrorMsg(error);
            documentMapper.updateById(doc);
        }
    }

    private void markFailed(long id, String error) {
        updateStatus(id, Constants.DOC_FAILED, error == null ? "未知错误" : error.substring(0, Math.min(1000, error.length())));
    }
}
