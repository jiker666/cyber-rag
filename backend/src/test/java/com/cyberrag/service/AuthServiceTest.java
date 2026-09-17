package com.cyberrag.service;

import com.cyberrag.BaseTest;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.auth.LoginRequest;
import com.cyberrag.dto.auth.RegisterRequest;
import com.cyberrag.vo.LoginVO;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 认证服务测试: 注册 / 登录 / 密码错误 / 重复注册。
 */
class AuthServiceTest extends BaseTest {

    @Autowired
    private AuthService authService;

    @Test
    void register_creates_user_and_returns_token() {
        RegisterRequest request = new RegisterRequest();
        request.setUsername("newuser1");
        request.setPassword("pass123456");
        request.setNickname("新用户");
        request.setEmail("new@local");
        LoginVO vo = authService.register(request);
        assertNotNull(vo.getToken());
        assertEquals("newuser1", vo.getUser().getUsername());
        assertEquals("USER", vo.getUser().getRoleCode());
    }

    @Test
    void register_rejects_duplicate_username() {
        RegisterRequest request = new RegisterRequest();
        request.setUsername("admin");
        request.setPassword("pass123456");
        request.setNickname("重复");
        assertThrows(BusinessException.class, () -> authService.register(request));
    }

    @Test
    void login_with_correct_password() {
        LoginRequest request = new LoginRequest();
        request.setUsername("admin");
        request.setPassword("admin123");
        LoginVO vo = authService.login(request);
        assertNotNull(vo.getToken());
        assertEquals("ADMIN", vo.getUser().getRoleCode());
    }

    @Test
    void login_with_wrong_password_throws() {
        LoginRequest request = new LoginRequest();
        request.setUsername("admin");
        request.setPassword("wrong-password");
        BusinessException e = assertThrows(BusinessException.class,
                () -> authService.login(request));
        assertEquals(401, e.getCode());
    }
}
