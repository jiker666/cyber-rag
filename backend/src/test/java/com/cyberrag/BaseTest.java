package com.cyberrag;

import com.cyberrag.security.AuthContext;
import com.cyberrag.entity.User;
import com.cyberrag.mapper.UserMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

/**
 * 测试基类: H2 数据库 + Mock RAG 客户端 + 登录上下文。
 */
@SpringBootTest
public abstract class BaseTest {

    @MockitoBean
    protected com.cyberrag.integration.RagServiceClient ragServiceClient;

    @Autowired
    protected UserMapper userMapper;

    @BeforeEach
    void loginAsAdmin() {
        User admin = userMapper.selectById(1L);
        AuthContext.set(new AuthContext.CurrentUser(
                admin.getId(), admin.getUsername(), admin.getNickname(),
                admin.getRoleId(), "ADMIN"));
    }

    @AfterEach
    void clearContext() {
        AuthContext.clear();
    }
}
