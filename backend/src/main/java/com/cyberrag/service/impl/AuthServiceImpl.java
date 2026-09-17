package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.auth.LoginRequest;
import com.cyberrag.dto.auth.RegisterRequest;
import com.cyberrag.entity.Role;
import com.cyberrag.entity.User;
import com.cyberrag.mapper.RoleMapper;
import com.cyberrag.mapper.UserMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.security.JwtUtil;
import com.cyberrag.service.AuthService;
import com.cyberrag.service.UserService;
import com.cyberrag.vo.LoginVO;
import com.cyberrag.vo.UserVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 认证服务实现: 注册(BCrypt 加密) / 登录(JWT 签发)。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final UserService userService;
    private final JwtUtil jwtUtil;
    private final BCryptPasswordEncoder passwordEncoder;

    @Override
    public LoginVO login(LoginRequest request) {
        User user = userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, request.getUsername()));
        if (user == null || !passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BusinessException(401, "用户名或密码错误");
        }
        if (user.getStatus() != 1) {
            throw new BusinessException(403, "账号已被禁用, 请联系管理员");
        }
        Role role = roleMapper.selectById(user.getRoleId());
        String roleCode = role != null ? role.getCode() : Constants.ROLE_USER;

        user.setLastLoginAt(LocalDateTime.now());
        userMapper.updateById(user);

        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), roleCode);
        log.info("用户登录成功: {}, role={}", user.getUsername(), roleCode);
        return LoginVO.builder()
                .token(token)
                .expiresIn(jwtUtil.getExpireHours() * 3600)
                .user(userService.toVO(user))
                .build();
    }

    @Override
    public LoginVO register(RegisterRequest request) {
        Long exists = userMapper.selectCount(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, request.getUsername()));
        if (exists > 0) {
            throw new BusinessException(409, "用户名已存在");
        }
        User user = new User();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setNickname(request.getNickname());
        user.setEmail(request.getEmail());
        user.setRoleId(Constants.ROLE_ID_USER);
        user.setStatus(1);
        user.setLastLoginAt(LocalDateTime.now());
        userMapper.insert(user);

        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), Constants.ROLE_USER);
        log.info("新用户注册: {}", user.getUsername());
        return LoginVO.builder()
                .token(token)
                .expiresIn(jwtUtil.getExpireHours() * 3600)
                .user(userService.toVO(user))
                .build();
    }

    @Override
    public UserVO currentUserProfile() {
        User user = userMapper.selectById(AuthContext.getUserId());
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        return userService.toVO(user);
    }
}
