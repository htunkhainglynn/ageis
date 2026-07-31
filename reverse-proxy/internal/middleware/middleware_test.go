package middleware

import (
	"bytes"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestChainLogsRequestStatus(t *testing.T) {
	t.Parallel()
	var logs bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&logs, nil))
	handler := Chain(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusAccepted)
		}),
		RequestLogger(logger),
	)

	handler.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodPost, "/orders", nil))

	output := logs.String()
	for _, expected := range []string{`"method":"POST"`, `"path":"/orders"`, `"status":202`} {
		if !strings.Contains(output, expected) {
			t.Errorf("log %q does not contain %q", output, expected)
		}
	}
}

func TestRecoverReturnsStructuredError(t *testing.T) {
	t.Parallel()
	logger := slog.New(slog.NewTextHandler(&bytes.Buffer{}, nil))
	handler := Chain(
		http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
			panic("boom")
		}),
		Recover(logger),
	)
	recorder := httptest.NewRecorder()

	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/", nil))

	if recorder.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d, want 500", recorder.Code)
	}
	if !strings.Contains(recorder.Body.String(), `"INTERNAL_ERROR"`) {
		t.Fatalf("body = %q", recorder.Body.String())
	}
}

func TestStatusRecorderUnwrapsResponseWriter(t *testing.T) {
	t.Parallel()
	recorder := httptest.NewRecorder()
	wrapped := &statusRecorder{ResponseWriter: recorder}
	if wrapped.Unwrap() != recorder {
		t.Fatal("Unwrap did not return the underlying response writer")
	}
}
