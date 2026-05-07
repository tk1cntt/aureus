//+------------------------------------------------------------------+
//|                                                  ErrorHandler.mqh |
//|                                      Copyright 2024, OpenAlgo.in |
//|                                          https://www.openalgo.in |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, OpenAlgo.in"
#property link      "https://www.openalgo.in"
#property version   "1.00"

#ifndef ERROR_HANDLER_MQH
#define ERROR_HANDLER_MQH

#include "WinINet.mqh"

//+------------------------------------------------------------------+
//| Error Handling Constants                                          |
//+------------------------------------------------------------------+
// Timeout configuration (D-09, D-10)
#define ERROR_TIMEOUT_SEND_MS       30000   // 30 seconds
#define ERROR_TIMEOUT_RECEIVE_MS    30000   // 30 seconds

// Retry configuration (D-01)
#define ERROR_MAX_RETRIES           3
#define ERROR_RETRY_DELAY_1_MS      1000    // 1 second
#define ERROR_RETRY_DELAY_2_MS      2000    // 2 seconds
#define ERROR_RETRY_DELAY_3_MS      4000    // 4 seconds

//+------------------------------------------------------------------+
//| Error Classification (D-02, D-03)                                |
//+------------------------------------------------------------------+
// Returns true if status code is transient error (should retry)
bool IsTransientError(int status) {
    // Network errors (WebReq returns -1)
    if (status == -1) return true;
    // Timeout
    if (status == 408) return true;
    // Rate limited
    if (status == 429) return true;
    // Server errors (5xx)
    if (status >= 500 && status < 600) return true;
    return false;
}

//+------------------------------------------------------------------+
//| Retry Wrapper (D-01)                                              |
//+------------------------------------------------------------------+
// Retry wrapper for WebReq
// Returns: true if success, false if all retries exhausted
// Logs: attempt number, delays, final error
bool WebReqWithRetry(WininetRequest &req, WininetResponse &res, string context = "") {
    int delays[3] = {ERROR_RETRY_DELAY_1_MS, ERROR_RETRY_DELAY_2_MS, ERROR_RETRY_DELAY_3_MS};

    for (int attempt = 0; attempt <= ERROR_MAX_RETRIES; attempt++) {
        if (attempt > 0) {
            int delayMs = delays[attempt - 1];
            PrintFormat("[OpenAlgo] %s: Retry %d/%d after %d ms", context, attempt, ERROR_MAX_RETRIES, delayMs);
            Sleep(delayMs);
        }

        if (WebReq(req, res)) {
            if (res.status >= 200 && res.status < 300) {
                return true;  // Success
            }
            if (!IsTransientError(res.status)) {
                PrintFormat("[OpenAlgo] %s: Client error %d, not retrying", context, res.status);
                return false;  // 4xx - don't retry
            }
            PrintFormat("[OpenAlgo] %s: Transient error %d, retrying...", context, res.status);
        } else {
            if (!IsTransientError(-1)) {
                PrintFormat("[OpenAlgo] %s: Non-retryable network error", context);
                return false;
            }
            PrintFormat("[OpenAlgo] %s: Network error, retrying...", context);
        }
    }

    PrintFormat("[OpenAlgo] %s: All %d retries exhausted", context, ERROR_MAX_RETRIES);
    return false;
}

//+------------------------------------------------------------------+
//| Logging Functions (D-04 to D-08)                                  |
//+------------------------------------------------------------------+
// Log HTTP request details (D-04, D-08)
void LogRequest(string funcName, WininetRequest &req) {
    string url = (req.port == 443 ? "https://" : "http://") + req.host + req.path;
    PrintFormat("[OpenAlgo] %s: %s %s", funcName, req.method, url);
    if (StringLen(req.data_str) > 0) {
        PrintFormat("[OpenAlgo] %s: Request body: %s", funcName, req.data_str);
    }
}

// Log HTTP response (D-05, D-08)
void LogResponse(string funcName, WininetResponse &res) {
    PrintFormat("[OpenAlgo] %s: Response status: %d", funcName, res.status);
    string body = res.GetDataStr();
    if (StringLen(body) > 0) {
        PrintFormat("[OpenAlgo] %s: Response body: %s", funcName, body);
    } else {
        PrintFormat("[OpenAlgo] %s: Response body: (empty)", funcName);
    }
}

// Log network error (D-06, D-14)
void LogNetworkError(string funcName, string context) {
    uint err = GetLastError();
    PrintFormat("[OpenAlgo] %s: Network error #%d (%s)", funcName, err, context);
}

//+------------------------------------------------------------------+
//| Error Message Extraction (D-12, D-13)                             |
//+------------------------------------------------------------------+
// Try to extract error message from JSON response
string ExtractErrorMessage(string jsonResponse) {
    // Simple JSON parsing for {"error":"..."} or {"message":"..."}
    // Look for "error" key
    int errorPos = StringFind(jsonResponse, "\"error\"");
    if (errorPos >= 0) {
        int colonPos = StringFind(jsonResponse, ":", errorPos);
        int quoteStart = StringFind(jsonResponse, "\"", colonPos + 1);
        int quoteEnd = StringFind(jsonResponse, "\"", quoteStart + 1);
        if (quoteStart >= 0 && quoteEnd > quoteStart) {
            return StringSubstr(jsonResponse, quoteStart + 1, quoteEnd - quoteStart - 1);
        }
    }
    // Look for "message" key
    int msgPos = StringFind(jsonResponse, "\"message\"");
    if (msgPos >= 0) {
        int colonPos = StringFind(jsonResponse, ":", msgPos);
        int quoteStart = StringFind(jsonResponse, "\"", colonPos + 1);
        int quoteEnd = StringFind(jsonResponse, "\"", quoteStart + 1);
        if (quoteStart >= 0 && quoteEnd > quoteStart) {
            return StringSubstr(jsonResponse, quoteStart + 1, quoteEnd - quoteStart - 1);
        }
    }
    return "";
}

// Log API error with extracted message (D-13, D-14)
void LogApiError(string funcName, int status, string responseBody) {
    string errorMsg = ExtractErrorMessage(responseBody);
    if (StringLen(errorMsg) > 0) {
        PrintFormat("[OpenAlgo] %s: API error %d: %s", funcName, status, errorMsg);
    } else {
        PrintFormat("[OpenAlgo] %s: API error %d: %s", funcName, status, responseBody);
    }
}

//+------------------------------------------------------------------+
#endif
//+------------------------------------------------------------------+
