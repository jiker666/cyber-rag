package com.cyberrag.security;

import lombok.AllArgsConstructor;
import lombok.Data;

/**
 * 当前登录用户上下文(ThreadLocal)。
 */
public final class AuthContext {

    @Data
    @AllArgsConstructor
    public static class CurrentUser {
        private Long userId;
        private String username;
        private String nickname;
        private Long roleId;
        private String roleCode;
    }

    private static final ThreadLocal<CurrentUser> HOLDER = new ThreadLocal<>();

    private AuthContext() {
    }

    public static void set(CurrentUser user) {
        HOLDER.set(user);
    }

    public static CurrentUser get() {
        return HOLDER.get();
    }

    public static Long getUserId() {
        CurrentUser u = HOLDER.get();
        return u == null ? null : u.getUserId();
    }

    public static boolean isAdmin() {
        CurrentUser u = HOLDER.get();
        return u != null && "ADMIN".equals(u.getRoleCode());
    }

    public static void clear() {
        HOLDER.remove();
    }
}
