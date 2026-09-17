package com.cyberrag.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenAPI 文档配置。
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI cyberRagOpenAPI() {
        return new OpenAPI().info(new Info()
                .title("Cyber RAG 后端 API")
                .description("基于 RAG 的网络安全知识智能问答系统 - 业务后端接口文档")
                .version("1.0.0"));
    }
}
