package com.cyberrag.config;

import com.cyberrag.common.exception.BusinessException;
import com.cyberrag.entity.User;
import com.cyberrag.mapper.UserMapper;
import com.cyberrag.security.AuthContext;
import com.cyberrag.security.JwtUtil;
import com.cyberrag.security.RequireAdmin;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.NonNull;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * JWT 认证与权限拦截器。
 * - /api/auth/** 与文档资源放行
 * - 其余 /api/** 要求合法 Bearer Token
 * - 标注 @RequireAdmin 的接口要求 ADMIN 角色
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;
    private final UserMapper userMapper;

    @Override
    public boolean preHandle(@NonNull HttpServletRequest request,
                             @NonNull HttpServletResponse response,
                             @NonNull Object handler) throws Exception {
        if (!(handler instanceof HandlerMethod method)) {
            return true;
        }
        String auth = request.getHeader("Authorization");
        if (auth == null || !auth.startsWith("Bearer ")) {
            response.setStatus(401);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"message\":\"未登录或 Token 缺失\",\"data\":null}");
            return false;
        }
        Claims claims = jwtUtil.parseToken(auth.substring(7));
        if (claims == null) {
            response.setStatus(401);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"message\":\"Token 无效或已过期\",\"data\":null}");
            return false;
        }
        Long userId = claims.get("uid", Long.class);
        User user = userMapper.selectById(userId);
        if (user == null || user.getStatus() != 1) {
            response.setStatus(401);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":401,\"message\":\"用户不存在或已被禁用\",\"data\":null}");
            return false;
        }
        AuthContext.set(new AuthContext.CurrentUser(
                user.getId(), user.getUsername(), user.getNickname(),
                user.getRoleId(), claims.get("role", String.class)));

        // 管理员权限校验(方法或类上标注均可)
        boolean requireAdmin = method.hasMethodAnnotation(RequireAdmin.class)
                || method.getBeanType().isAnnotationPresent(RequireAdmin.class);
        if (requireAdmin && !AuthContext.isAdmin()) {
            response.setStatus(403);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":403,\"message\":\"需要管理员权限\",\"data\":null}");
            AuthContext.clear();
            return false;
        }
        return true;
    }

    @Override
    public void afterCompletion(@NonNull HttpServletRequest request,
                                @NonNull HttpServletResponse response,
                                @NonNull Object handler, Exception ex) {
        AuthContext.clear();
    }
}
