package com.cyberrag.api;

import com.cyberrag.BaseTest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 健康检查端点: 免鉴权(供 docker healthcheck / 部署冒烟测试)。
 */
class HealthApiTest extends BaseTest {

    @Autowired
    private WebApplicationContext context;

    @Test
    void health_endpoint_is_public_and_returns_up() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        // 不携带 Token 也应放行
        mvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.status").value("UP"));
    }
}
