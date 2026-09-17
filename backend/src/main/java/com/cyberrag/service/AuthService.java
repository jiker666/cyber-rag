package com.cyberrag.service;

import com.cyberrag.dto.auth.LoginRequest;
import com.cyberrag.dto.auth.RegisterRequest;
import com.cyberrag.vo.LoginVO;
import com.cyberrag.vo.UserVO;

/**
 * 认证服务。
 */
public interface AuthService {

    LoginVO login(LoginRequest request);

    LoginVO register(RegisterRequest request);

    UserVO currentUserProfile();
}
