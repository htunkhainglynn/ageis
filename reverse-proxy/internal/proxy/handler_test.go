package proxy

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

type fakeValidator struct {
	keyInfo *KeyInfo
	err     error
	calls   atomic.Int32
}

func (f *fakeValidator) ValidateKey(_ context.Context, _ string) (*KeyInfo, error) {
	f.calls.Add(1)
	return f.keyInfo, f.err
}

func TestHandler(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name             string
		apiKey           string
		validationErr    error
		wantStatus       int
		wantErrorCode    string
		wantBackendCalls int32
	}{
		{name: "missing key", wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_MISSING"},
		{name: "unknown key", apiKey: "ak_unknown", validationErr: ErrKeyNotFound, wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_INVALID"},
		{name: "revoked key", apiKey: "ak_revoked", validationErr: ErrKeyRevoked, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_REVOKED"},
		{name: "expired key", apiKey: "ak_expired", validationErr: ErrKeyExpired, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_EXPIRED"},
		{name: "validator unavailable", apiKey: "ak_valid", validationErr: ErrValidatorUnavailable, wantStatus: http.StatusBadGateway, wantErrorCode: "CONTROL_PLANE_UNAVAILABLE"},
		{name: "valid key", apiKey: "ak_valid", wantStatus: http.StatusCreated, wantBackendCalls: 1},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			var backendCalls atomic.Int32
			backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				backendCalls.Add(1)
				if received := r.Header.Get("X-API-Key"); received != "" {
					t.Errorf("backend received API key header %q", received)
				}
				w.Header().Set("X-Upstream", "preserved")
				w.WriteHeader(http.StatusCreated)
				_, _ = w.Write([]byte("upstream response"))
			}))
			t.Cleanup(backend.Close)

			backendURL, err := url.Parse(backend.URL)
			if err != nil {
				t.Fatalf("parse backend URL: %v", err)
			}
			validator := &fakeValidator{
				keyInfo: &KeyInfo{ID: 1, Status: "active"},
				err:     tt.validationErr,
			}
			handler, err := NewHandler(
				backendURL,
				validator,
				"X-API-Key",
				time.Second,
				slog.New(slog.NewTextHandler(io.Discard, nil)),
			)
			if err != nil {
				t.Fatalf("create handler: %v", err)
			}

			req := httptest.NewRequest(http.MethodGet, "http://proxy.example/orders?limit=10", nil)
			if tt.apiKey != "" {
				req.Header.Set("X-API-Key", tt.apiKey)
			}
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, req)

			if recorder.Code != tt.wantStatus {
				t.Fatalf("status = %d, want %d; body=%s", recorder.Code, tt.wantStatus, recorder.Body.String())
			}
			if got := backendCalls.Load(); got != tt.wantBackendCalls {
				t.Fatalf("backend calls = %d, want %d", got, tt.wantBackendCalls)
			}
			if tt.wantErrorCode != "" && !strings.Contains(recorder.Body.String(), `"`+tt.wantErrorCode+`"`) {
				t.Errorf("response body %q does not contain error code %q", recorder.Body.String(), tt.wantErrorCode)
			}
			if tt.wantBackendCalls == 1 {
				if got := recorder.Header().Get("X-Upstream"); got != "preserved" {
					t.Errorf("upstream header = %q, want preserved", got)
				}
				if got := recorder.Body.String(); got != "upstream response" {
					t.Errorf("body = %q, want upstream response", got)
				}
			}
		})
	}
}

func TestHandlerRespectsValidationTimeout(t *testing.T) {
	t.Parallel()

	validator := validatorFunc(func(ctx context.Context, _ string) (*KeyInfo, error) {
		<-ctx.Done()
		return nil, ctx.Err()
	})
	backendURL, _ := url.Parse("http://backend.invalid")
	handler, err := NewHandler(
		backendURL,
		validator,
		"X-API-Key",
		10*time.Millisecond,
		slog.New(slog.NewTextHandler(io.Discard, nil)),
	)
	if err != nil {
		t.Fatalf("create handler: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "http://proxy.example/", nil)
	req.Header.Set("X-API-Key", "ak_slow")
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, req)

	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
}

type validatorFunc func(context.Context, string) (*KeyInfo, error)

func (f validatorFunc) ValidateKey(ctx context.Context, key string) (*KeyInfo, error) {
	return f(ctx, key)
}

func TestNewHandlerValidation(t *testing.T) {
	t.Parallel()
	backendURL, _ := url.Parse("http://backend.example")
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	validator := &fakeValidator{}

	tests := []struct {
		name      string
		backend   *url.URL
		validator KeyValidator
		header    string
		timeout   time.Duration
		logger    *slog.Logger
	}{
		{name: "missing backend", validator: validator, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing validator", backend: backendURL, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing header", backend: backendURL, validator: validator, timeout: time.Second, logger: logger},
		{name: "invalid timeout", backend: backendURL, validator: validator, header: "X-API-Key", logger: logger},
		{name: "missing logger", backend: backendURL, validator: validator, header: "X-API-Key", timeout: time.Second},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if _, err := NewHandler(tt.backend, tt.validator, tt.header, tt.timeout, tt.logger); err == nil {
				t.Fatal("expected error")
			}
		})
	}
}

func TestErrorsAreDistinct(t *testing.T) {
	t.Parallel()
	if errors.Is(ErrKeyNotFound, ErrKeyRevoked) {
		t.Fatal("sentinel errors must be distinct")
	}
}
