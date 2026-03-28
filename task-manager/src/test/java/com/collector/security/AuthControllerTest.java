package com.collector.security;

import com.collector.common.Result;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthController — login with rate limiting")
class AuthControllerTest {

    @Mock
    private JwtTokenProvider jwtTokenProvider;
    @Mock
    private HttpServletRequest request;

    private AuthController controller;
    private PasswordEncoder passwordEncoder;

    @BeforeEach
    void setUp() throws Exception {
        passwordEncoder = new BCryptPasswordEncoder();
        controller = new AuthController(jwtTokenProvider, passwordEncoder);

        String hash = passwordEncoder.encode("admin123");
        setField(controller, "adminUsername", "admin");
        setField(controller, "adminPasswordHash", hash);
    }

    private void setField(Object target, String name, Object value) throws Exception {
        Field f = target.getClass().getDeclaredField(name);
        f.setAccessible(true);
        f.set(target, value);
    }

    @Test
    @DisplayName("successful login returns token")
    void loginSuccess() {
        when(request.getRemoteAddr()).thenReturn("127.0.0.1");
        when(jwtTokenProvider.generateToken("admin", "admin")).thenReturn("jwt-token-123");

        Map<String, String> creds = Map.of("username", "admin", "password", "admin123");
        Result<Map<String, Object>> result = controller.login(creds, request);

        assertThat(result.isSuccess()).isTrue();
        assertThat(result.getData()).containsKey("token");
        assertThat(result.getData().get("token")).isEqualTo("jwt-token-123");
        assertThat(result.getData().get("role")).isEqualTo("admin");
        assertThat(result.getData().get("username")).isEqualTo("admin");
    }

    @Test
    @DisplayName("wrong password returns 401")
    void loginWrongPassword() {
        when(request.getRemoteAddr()).thenReturn("127.0.0.1");

        Map<String, String> creds = Map.of("username", "admin", "password", "wrong");
        Result<Map<String, Object>> result = controller.login(creds, request);

        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(401);
    }

    @Test
    @DisplayName("wrong username returns 401")
    void loginWrongUsername() {
        when(request.getRemoteAddr()).thenReturn("127.0.0.1");

        Map<String, String> creds = Map.of("username", "hacker", "password", "admin123");
        Result<Map<String, Object>> result = controller.login(creds, request);

        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(401);
    }

    @Test
    @DisplayName("missing username returns 400")
    void loginMissingUsername() {
        when(request.getRemoteAddr()).thenReturn("127.0.0.1");

        Map<String, String> creds = new HashMap<>();
        creds.put("password", "admin123");
        Result<Map<String, Object>> result = controller.login(creds, request);

        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(400);
    }

    @Test
    @DisplayName("missing password returns 400")
    void loginMissingPassword() {
        when(request.getRemoteAddr()).thenReturn("127.0.0.1");

        Map<String, String> creds = new HashMap<>();
        creds.put("username", "admin");
        Result<Map<String, Object>> result = controller.login(creds, request);

        assertThat(result.isSuccess()).isFalse();
        assertThat(result.getCode()).isEqualTo(400);
    }

    @Test
    @DisplayName("5 failed attempts triggers lockout (429)")
    void rateLimiting() {
        when(request.getRemoteAddr()).thenReturn("10.0.0.1");

        Map<String, String> badCreds = Map.of("username", "admin", "password", "wrong");

        // 5 failed attempts
        for (int i = 0; i < 5; i++) {
            Result<?> r = controller.login(badCreds, request);
            assertThat(r.getCode()).isEqualTo(401);
        }

        // 6th attempt should be rate limited
        Result<?> r = controller.login(badCreds, request);
        assertThat(r.getCode()).isEqualTo(429);
    }

    @Test
    @DisplayName("different IPs have separate rate limits")
    void differentIpsSeparateLimits() {
        Map<String, String> badCreds = Map.of("username", "admin", "password", "wrong");

        // 4 fails from IP1
        when(request.getRemoteAddr()).thenReturn("10.0.0.1");
        for (int i = 0; i < 4; i++) {
            controller.login(badCreds, request);
        }

        // IP2 should still be allowed
        when(request.getRemoteAddr()).thenReturn("10.0.0.2");
        Result<?> r = controller.login(badCreds, request);
        assertThat(r.getCode()).isEqualTo(401); // Failed but not locked
    }

    @Test
    @DisplayName("successful login clears lockout counter")
    void successClearsLockout() {
        when(request.getRemoteAddr()).thenReturn("10.0.0.3");
        when(jwtTokenProvider.generateToken(anyString(), anyString())).thenReturn("token");

        Map<String, String> badCreds = Map.of("username", "admin", "password", "wrong");
        Map<String, String> goodCreds = Map.of("username", "admin", "password", "admin123");

        // 3 failed attempts
        for (int i = 0; i < 3; i++) {
            controller.login(badCreds, request);
        }

        // Successful login
        Result<?> r = controller.login(goodCreds, request);
        assertThat(r.isSuccess()).isTrue();

        // Should be able to fail again without being locked
        r = controller.login(badCreds, request);
        assertThat(r.getCode()).isEqualTo(401); // Not 429
    }
}
