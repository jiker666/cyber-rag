package com.cyberrag.controller.admin;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.cyberrag.common.result.Result;
import com.cyberrag.security.RequireAdmin;
import com.cyberrag.service.UserService;
import com.cyberrag.vo.UserVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 管理员-用户管理接口。
 */
@Tag(name = "管理员-用户管理")
@RestController
@RequestMapping("/api/admin/users")
@RequiredArgsConstructor
@RequireAdmin
public class AdminUserController {

    private final UserService userService;

    @Operation(summary = "分页查询用户")
    @GetMapping
    public Result<IPage<UserVO>> page(@RequestParam(defaultValue = "1") long page,
                                      @RequestParam(defaultValue = "10") long size,
                                      @RequestParam(required = false) String keyword) {
        return Result.success(userService.pageUsers(page, size, keyword));
    }

    @Operation(summary = "启用/禁用用户")
    @PutMapping("/{id}/status")
    public Result<Void> updateStatus(@PathVariable long id, @RequestBody Map<String, Integer> body) {
        userService.updateUserStatus(id, body.getOrDefault("status", 1));
        return Result.success();
    }

    @Operation(summary = "重置用户密码")
    @PostMapping("/{id}/reset-password")
    public Result<Void> resetPassword(@PathVariable long id, @RequestBody Map<String, String> body) {
        userService.resetPassword(id, body.get("newPassword"));
        return Result.success();
    }
}
