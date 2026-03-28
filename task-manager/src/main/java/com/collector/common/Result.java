package com.collector.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Result<T> {
    private boolean success;
    private T data;
    private String message;
    private Integer code;

    public static <T> Result<T> ok(T data) {
        return new Result<>(true, data, null, 200);
    }

    public static <T> Result<T> ok() {
        return new Result<>(true, null, null, 200);
    }

    public static <T> Result<T> fail(String message) {
        return new Result<>(false, null, message, 400);
    }

    public static <T> Result<T> fail(Integer code, String message) {
        return new Result<>(false, null, message, code);
    }
}
