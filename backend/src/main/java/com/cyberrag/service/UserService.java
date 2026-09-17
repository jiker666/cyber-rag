package com.cyberrag.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.service.IService;
import com.cyberrag.dto.user.PasswordUpdateRequest;
import com.cyberrag.dto.user.ProfileUpdateRequest;
import com.cyberrag.entity.User;
import com.cyberrag.vo.UserVO;

/**
 * 用户服务。
 */
public interface UserService extends IService<User> {

    UserVO toVO(User user);

    UserVO updateProfile(ProfileUpdateRequest request);

    void updatePassword(PasswordUpdateRequest request);

    IPage<UserVO> pageUsers(long page, long size, String keyword);

    void updateUserStatus(long userId, int status);

    void resetPassword(long userId, String newPassword);
}
