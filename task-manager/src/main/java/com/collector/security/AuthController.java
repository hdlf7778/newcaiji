package com.collector.security;

import com.collector.common.Result;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final JwtTokenProvider jwtTokenProvider;
    private final PasswordEncoder passwordEncoder;

    private final Map<String, List<Long>> loginAttempts = new ConcurrentHashMap<>();
    private static final int MAX_ATTEMPTS = 5;
    private static final long LOCKOUT_MS = 15 * 60 * 1000; // 15 minutes
    private static final int MAX_TRACKED_IPS = 10_000;

    @Value("${collector.admin.username:admin}")
    private String adminUsername;

    @Value("${collector.admin.password-hash}")
    private String adminPasswordHash;

    /**
     * POST /api/auth/login
     * Body: {"username": "...", "password": "..."}
     * Returns: {"token": "jwt...", "role": "admin", "username": "admin"}
     */
    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody Map<String, String> credentials, HttpServletRequest request) {
        String clientIp = request.getRemoteAddr();
        if (loginAttempts.size() > MAX_TRACKED_IPS) {
            loginAttempts.clear();
        }
        List<Long> attempts = loginAttempts.computeIfAbsent(clientIp, k -> new ArrayList<>());
        long now = System.currentTimeMillis();
        attempts.removeIf(t -> now - t > LOCKOUT_MS);
        if (attempts.size() >= MAX_ATTEMPTS) {
            log.warn("Login locked out for IP: {}", clientIp);
            return Result.fail(429, "Too many login attempts, please try again later");
        }

        String username = credentials.get("username");
        String password = credentials.get("password");

        if (username == null || password == null) {
            return Result.fail(400, "Username and password are required");
        }

        // Validate credentials (production: query from database)
        if (!adminUsername.equals(username) || !passwordEncoder.matches(password, adminPasswordHash)) {
            log.warn("Login failed for username: {}", username);
            attempts.add(now);
            return Result.fail(401, "Invalid username or password");
        }

        loginAttempts.remove(clientIp);

        String role = "admin";
        String token = jwtTokenProvider.generateToken(username, role);

        log.info("Login successful for username: {}", username);
        return Result.ok(Map.of(
                "token", token,
                "role", role,
                "username", username
        ));
    }
}
