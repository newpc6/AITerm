package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"time"

	"aiterm-server/internal/config"
)

type logLevel string

const (
	logLevelDebug logLevel = "DEBUG"
	logLevelInfo  logLevel = "INFO"
	logLevelWarn  logLevel = "WARN"
	logLevelError logLevel = "ERROR"
)

type responseWriter struct {
	http.ResponseWriter
	statusCode int
	body       bytes.Buffer
}

func (rw *responseWriter) Flush() {
	if flusher, ok := rw.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) Write(b []byte) (int, error) {
	if rw.statusCode == 0 {
		rw.statusCode = http.StatusOK
	}
	rw.body.Write(b)
	return rw.ResponseWriter.Write(b)
}

func (rw *responseWriter) getStatus() int {
	if rw.statusCode == 0 {
		return http.StatusOK
	}
	return rw.statusCode
}

func shouldLogBody(path string) bool {
	if strings.HasPrefix(path, "/api/conversations/stream") {
		return false
	}
	if strings.HasPrefix(path, "/api/tasks/") && strings.HasSuffix(path, "/events") {
		return false
	}
	return true
}

func shouldLogRequest(path string) bool {
	excludePaths := []string{
		"/health",
		"/api/settings/llm/public",
	}
	for _, p := range excludePaths {
		if path == p {
			return false
		}
	}
	return true
}

func truncateString(s string, maxLen int) string {
	if maxLen <= 0 {
		return s
	}
	runes := []rune(s)
	if len(runes) <= maxLen {
		return s
	}
	return string(runes[:maxLen]) + "..."
}

func truncateValue(v interface{}, maxLen int) interface{} {
	switch val := v.(type) {
	case string:
		return truncateString(val, maxLen)
	case map[string]interface{}:
		return truncateMap(val, maxLen)
	case []interface{}:
		if len(val) > 10 {
			truncated := make([]interface{}, 11)
			copy(truncated, val[:10])
			truncated[10] = fmt.Sprintf("...(%d more)", len(val)-10)
			return truncated
		}
		result := make([]interface{}, len(val))
		for i, item := range val {
			result[i] = truncateValue(item, maxLen)
		}
		return result
	default:
		return v
	}
}

func truncateMap(m map[string]interface{}, maxLen int) map[string]interface{} {
	result := make(map[string]interface{})
	for k, v := range m {
		result[k] = truncateValue(v, maxLen)
	}
	return result
}

func truncateJSON(data []byte, maxLen int) interface{} {
	if len(data) == 0 {
		return nil
	}
	var result interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return truncateString(string(data), maxLen)
	}
	return truncateValue(result, maxLen)
}

func getClientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		ips := strings.Split(xff, ",")
		if len(ips) > 0 {
			return strings.TrimSpace(ips[0])
		}
	}
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}
	return strings.Split(r.RemoteAddr, ":")[0]
}

func formatJSON(v interface{}) string {
	if v == nil {
		return ""
	}
	data, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprintf("%v", v)
	}
	return string(data)
}

func loggingMiddleware(cfg config.LogConfig) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if !cfg.Enabled {
				next.ServeHTTP(w, r)
				return
			}

			start := time.Now()

			var reqBody []byte
			if r.Body != nil && shouldLogBody(r.URL.Path) {
				reqBody, _ = io.ReadAll(r.Body)
				r.Body = io.NopCloser(bytes.NewBuffer(reqBody))
			}

			rw := &responseWriter{ResponseWriter: w}
			next.ServeHTTP(rw, r)

			duration := time.Since(start).Milliseconds()

			level := logLevelInfo
			if rw.getStatus() >= 400 {
				level = logLevelWarn
			}
			if rw.getStatus() >= 500 {
				level = logLevelError
			}

			var userPart string
			if user, ok := currentUserFromContext(r.Context()); ok {
				userPart = fmt.Sprintf(" user=%s(%s)", user.Username, user.ID)
			}

			var queryPart string
			if r.URL.RawQuery != "" {
				queryPart = fmt.Sprintf(" query=%s", r.URL.RawQuery)
			}

			log.Printf("[%s] %s %s | ip=%s | status=%d | duration=%dms | size=%d%s%s",
				level,
				r.Method,
				r.URL.Path,
				getClientIP(r),
				rw.getStatus(),
				duration,
				rw.body.Len(),
				queryPart,
				userPart,
			)

			if shouldLogRequest(r.URL.Path) && shouldLogBody(r.URL.Path) {
				if len(reqBody) > 0 {
					truncated := truncateJSON(reqBody, cfg.RequestBody)
					log.Printf("  Request: %s", formatJSON(truncated))
				}
			}
		})
	}
}
