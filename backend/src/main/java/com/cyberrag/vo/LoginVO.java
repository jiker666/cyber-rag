package com.cyberrag.vo;

import lombok.Builder;
import lombok.Data;

/**
 * 登录成功返回。
 */
@Data
@Builder
public class LoginVO {
    private String token;
    private Long expiresIn;
    private UserVO user;
}
