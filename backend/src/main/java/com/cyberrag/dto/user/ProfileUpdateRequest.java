package com.cyberrag.dto.user;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class ProfileUpdateRequest {
    @NotBlank(message = "昵称不能为空")
    @Size(max = 50, message = "昵称最长 50 字符")
    private String nickname;

    @Email(message = "邮箱格式不正确")
    private String email;

    private String avatar;
}
