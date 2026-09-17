package com.cyberrag.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.cyberrag.common.constants.Constants;
import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.dto.user.PasswordUpdateRequest;
import com.cyberrag.dto.user.ProfileUpdateRequest;
import com.cyberrag.entity.Role;
import com.cyberrag.entity.User;
import com.cyberrag.mapper.RoleMapper;
import com.cyberrag.mapper.UserMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.service.UserService;
import com.cyberrag.vo.UserVO;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

/**
 * 用户服务实现。
 */
@Service
@RequiredArgsConstructor
public class UserServiceImpl extends ServiceImpl<UserMapper, User> implements UserService {

    private final UserMapper userMapper;
    private final RoleMapper roleMapper;
    private final BCryptPasswordEncoder passwordEncoder;

    @Override
    public UserVO toVO(User user) {
        Role role = roleMapper.selectById(user.getRoleId());
        return UserVO.builder()
                .id(user.getId())
                .username(user.getUsername())
                .nickname(user.getNickname())
                .email(user.getEmail())
                .avatar(user.getAvatar())
                .roleId(user.getRoleId())
                .roleCode(role != null ? role.getCode() : Constants.ROLE_USER)
                .roleName(role != null ? role.getName() : "普通用户")
                .status(user.getStatus())
                .lastLoginAt(user.getLastLoginAt())
                .createdAt(user.getCreatedAt())
                .build();
    }

    @Override
    public UserVO updateProfile(ProfileUpdateRequest request) {
        User user = userMapper.selectById(AuthContext.getUserId());
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        user.setNickname(request.getNickname());
        user.setEmail(request.getEmail());
        user.setAvatar(request.getAvatar());
        userMapper.updateById(user);
        return toVO(user);
    }

    @Override
    public void updatePassword(PasswordUpdateRequest request) {
        User user = userMapper.selectById(AuthContext.getUserId());
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        if (!passwordEncoder.matches(request.getOldPassword(), user.getPassword())) {
            throw new BusinessException(400, "原密码错误");
        }
        user.setPassword(passwordEncoder.encode(request.getNewPassword()));
        userMapper.updateById(user);
    }

    @Override
    public IPage<UserVO> pageUsers(long page, long size, String keyword) {
        LambdaQueryWrapper<User> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(keyword)) {
            wrapper.like(User::getUsername, keyword).or().like(User::getNickname, keyword);
        }
        wrapper.orderByDesc(User::getCreatedAt);
        IPage<User> userPage = userMapper.selectPage(new Page<>(page, size), wrapper);
        return userPage.convert(this::toVO);
    }

    @Override
    public void updateUserStatus(long userId, int status) {
        if (userId == AuthContext.getUserId()) {
            throw new BusinessException(400, "不能禁用自己的账号");
        }
        if (status != 0 && status != 1) {
            throw new BusinessException(400, "非法状态值");
        }
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        user.setStatus(status);
        userMapper.updateById(user);
    }

    @Override
    public void resetPassword(long userId, String newPassword) {
        if (newPassword == null || newPassword.length() < 6) {
            throw new BusinessException(400, "新密码长度至少 6 位");
        }
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException(404, "用户不存在");
        }
        user.setPassword(passwordEncoder.encode(newPassword));
        userMapper.updateById(user);
    }
}
