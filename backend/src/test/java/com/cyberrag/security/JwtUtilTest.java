package com.cyberrag.security;

import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * JWT 工具测试。
 */
class JwtUtilTest {

    private final JwtUtil jwtUtil = new JwtUtil("unit-test-jwt-secret-key-32-chars-min!!", 1);

    @Test
    void generate_and_parse_token() {
        String token = jwtUtil.generateToken(42L, "alice", "ADMIN");
        Claims claims = jwtUtil.parseToken(token);
        assertNotNull(claims);
        assertEquals(42L, claims.get("uid", Long.class));
        assertEquals("alice", claims.get("username", String.class));
        assertEquals("ADMIN", claims.get("role", String.class));
    }

    @Test
    void parse_invalid_token_returns_null() {
        assertNull(jwtUtil.parseToken("not-a-jwt-token"));
        assertNull(jwtUtil.parseToken(""));
    }

    @Test
    void tampered_token_returns_null() {
        String token = jwtUtil.generateToken(1L, "bob", "USER");
        assertNull(jwtUtil.parseToken(token + "tampered"));
    }

    @org.junit.jupiter.api.Test
    void short_secret_rejected() {
        org.junit.jupiter.api.Assertions.assertThrows(IllegalStateException.class,
                () -> new JwtUtil("short", 1));
    }
}
