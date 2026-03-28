package com.collector.security;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Field;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("JwtTokenProvider — JWT token generation and validation")
class JwtTokenProviderTest {

    private JwtTokenProvider provider;

    @BeforeEach
    void setUp() throws Exception {
        provider = new JwtTokenProvider();
        // Inject @Value fields via reflection (no Spring context)
        setField(provider, "secret", "test-secret-key-at-least-64-chars-long-for-hs512-algorithm-to-work-properly");
        setField(provider, "expiration", 86400000L);
    }

    private void setField(Object target, String fieldName, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(target, value);
    }

    @Test
    @DisplayName("generate and validate token")
    void generateAndValidate() {
        String token = provider.generateToken("admin", "admin");
        assertThat(token).isNotBlank();
        assertThat(provider.validateToken(token)).isTrue();
    }

    @Test
    @DisplayName("extract username from token")
    void extractUsername() {
        String token = provider.generateToken("testuser", "admin");
        assertThat(provider.getUsernameFromToken(token)).isEqualTo("testuser");
    }

    @Test
    @DisplayName("extract role from token")
    void extractRole() {
        String token = provider.generateToken("admin", "admin");
        assertThat(provider.getRoleFromToken(token)).isEqualTo("admin");
    }

    @Test
    @DisplayName("different users get different tokens")
    void differentUsersGetDifferentTokens() {
        String token1 = provider.generateToken("user1", "admin");
        String token2 = provider.generateToken("user2", "viewer");
        assertThat(token1).isNotEqualTo(token2);
    }

    @Test
    @DisplayName("invalid token returns false")
    void invalidToken() {
        assertThat(provider.validateToken("invalid.token.here")).isFalse();
    }

    @Test
    @DisplayName("empty token returns false")
    void emptyToken() {
        assertThat(provider.validateToken("")).isFalse();
    }

    @Test
    @DisplayName("null token returns false")
    void nullToken() {
        assertThat(provider.validateToken(null)).isFalse();
    }

    @Test
    @DisplayName("expired token returns false")
    void expiredToken() throws Exception {
        // Set expiration to -1ms (already expired)
        setField(provider, "expiration", -1L);
        String token = provider.generateToken("admin", "admin");
        assertThat(provider.validateToken(token)).isFalse();
    }

    @Test
    @DisplayName("tampered token rejected — either returns false or throws")
    void tamperedToken() {
        String token = provider.generateToken("admin", "admin");
        String tampered = token.substring(0, token.length() - 5) + "XXXXX";
        try {
            boolean result = provider.validateToken(tampered);
            // If validateToken doesn't throw, it should return false
            assertThat(result).isFalse();
        } catch (Exception e) {
            // Some JJWT versions throw SignatureException not caught by SecurityException
            assertThat(e.getClass().getSimpleName()).containsIgnoringCase("signature");
        }
    }
}
