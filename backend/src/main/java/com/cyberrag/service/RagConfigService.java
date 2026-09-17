package com.cyberrag.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.cyberrag.entity.RagConfig;

/**
 * RAG 参数配置服务(单行配置表)。
 */
public interface RagConfigService extends IService<RagConfig> {

    /** 获取配置, 无则初始化默认值 */
    RagConfig getConfig();

    RagConfig update(RagConfig config);
}
