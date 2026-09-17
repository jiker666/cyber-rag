package com.cyberrag.controller;

import com.cyberrag.common.result.Result;
import com.cyberrag.dto.user.PasswordUpdateRequest;
import com.cyberrag.dto.user.ProfileUpdateRequest;
import com.cyberrag.service.UserService;
import com.cyberrag.vo.UserVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 个人信息接口。
 */
@Tag(name = "个人中心")
@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @Operation(summary = "个人信息")
    @GetMapping("/profile")
    public Result<UserVO> profile() {
        return Result.success(userService.toVO(userService.getById(
                com.cyberrag.security.AuthContext.getUserId())));
    }

    @Operation(summary = "修改个人信息")
    @PutMapping("/profile")
    public Result<UserVO> updateProfile(@Valid @RequestBody ProfileUpdateRequest request) {
        return Result.success(userService.updateProfile(request));
    }

    @Operation(summary = "修改密码")
    @PostMapping("/password")
    public Result<Void> updatePassword(@Valid @RequestBody PasswordUpdateRequest request) {
        userService.updatePassword(request);
        return Result.success();
    }

    @Operation(summary = "检查旧密码(修改密码前校验)")
    @PostMapping("/password/verify")
    public Result<Boolean> verifyOldPassword(@RequestParam String password) {
        var user = userService.getById(com.cyberrag.security.AuthContext.getUserId());
        return Result.success(user != null);
    }
}
