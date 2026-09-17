package com.cyberrag.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.cyberrag.entity.Document;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文档服务: 上传/入库/删除/重新向量化。
 */
public interface DocumentService extends IService<Document> {

    /** 上传并异步入库, 返回创建的文档记录(PENDING 状态) */
    Document upload(MultipartFile file, long knowledgeBaseId);

    /** 同步执行入库流程(状态流转 PENDING→PARSING→EMBEDDING→COMPLETED/FAILED) */
    void process(long documentId);

    /** 重新向量化(重新读取已保存文件) */
    void reingest(long documentId);

    void deleteDocument(long documentId);

    IPage<Document> page(long page, long size, long knowledgeBaseId, String keyword, String status);
}
