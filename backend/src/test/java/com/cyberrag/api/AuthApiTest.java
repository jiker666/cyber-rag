package com.cyberrag.api;

import com.cyberrag.BaseTest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * API 鉴权集成测试: 登录 / 未登录 401 / 普通用户访问管理接口 403。
 */
class AuthApiTest extends BaseTest {

    @Autowired
    private WebApplicationContext context;

    @Test
    void login_returns_token_and_user() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"admin123\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.token").isNotEmpty())
                .andExpect(jsonPath("$.data.user.roleCode").value("ADMIN"));
    }

    @Test
    void login_with_wrong_password_returns_401_code() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"bad-pass\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void protected_api_without_token_returns_401() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        mvc.perform(get("/api/kb/enabled"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void protected_api_with_token_passes() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        String body = mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"admin123\"}"))
                .andReturn().getResponse().getContentAsString();
        String token = com.fasterxml.jackson.databind.json.JsonMapper.builder()
                .build().readTree(body).path("data").path("token").asText();
        mvc.perform(get("/api/kb/enabled").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0));
    }

    @Test
    void admin_api_rejects_normal_user() throws Exception {
        MockMvc mvc = MockMvcBuilders.webAppContextSetup(context).build();
        String body = mvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"user\",\"password\":\"admin123\"}"))
                .andReturn().getResponse().getContentAsString();
        String token = com.fasterxml.jackson.databind.json.JsonMapper.builder()
                .build().readTree(body).path("data").path("token").asText();
        // user 账号密码同为 admin123(测试库), 访问管理接口应 403
        mvc.perform(get("/api/admin/users")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isForbidden());
    }
}
