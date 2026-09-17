package com.cyberrag.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 应用自定义配置(均由环境变量注入)。
 */
@Data
@Component
@ConfigurationProperties(prefix = "app")
public class AppProperties {

    private Rag rag = new Rag();
    private Jwt jwt = new Jwt();
    private Upload upload = new Upload();

    @Data
    public static class Rag {
        /** Python RAG 服务地址 */
        private String serviceUrl = "http://127.0.0.1:8000";
        /** 内部通信令牌 */
        private String internalToken = "";
        /** 调用超时(秒) */
        private int timeoutSeconds = 180;
    }

    @Data
    public static class Jwt {
        private String secret;
        private long expireHours = 24;
    }

    @Data
    public static class Upload {
        private String dir = "./data/uploads";
        private int maxSizeMb = 20;
    }
}
