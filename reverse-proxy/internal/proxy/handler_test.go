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

type fakeJWTValidator struct {
	err   error
	calls atomic.Int32
}

func (f *fakeJWTValidator) ValidateJWT(_ context.Context, _ string) error {
	f.calls.Add(1)
	return f.err
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
		jwtToken         string
		jwtError         error
		wantStatus       int
		wantErrorCode    string
		wantBackendCalls int32
	}{
		{name: "missing key", wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_MISSING"},
		{name: "unknown key", apiKey: "ak_unknown", validationErr: ErrKeyNotFound, wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_INVALID"},
		{name: "revoked key", apiKey: "ak_revoked", validationErr: ErrKeyRevoked, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_REVOKED"},
		{name: "expired key", apiKey: "ak_expired", validationErr: ErrKeyExpired, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_EXPIRED"},
		{name: "validator unavailable", apiKey: "ak_valid", validationErr: ErrValidatorUnavailable, wantStatus: http.StatusBadGateway, wantErrorCode: "CONTROL_PLANE_UNAVAILABLE"},
		{name: "missing JWT", apiKey: "ak_valid", wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_MISSING"},
		{name: "invalid JWT", apiKey: "ak_valid", jwtToken: "invalid", jwtError: ErrJWTInvalid, wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_INVALID"},
		{name: "expired JWT", apiKey: "ak_valid", jwtToken: "expired", jwtError: ErrJWTExpired, wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_EXPIRED"},
		{name: "policy unavailable", apiKey: "ak_valid", jwtToken: "token", jwtError: ErrPolicyUnavailable, wantStatus: http.StatusBadGateway, wantErrorCode: "CONTROL_PLANE_UNAVAILABLE"},
		{name: "valid credentials", apiKey: "ak_valid", jwtToken: "valid", wantStatus: http.StatusCreated, wantBackendCalls: 1},
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
				if received := r.Header.Get("Authorization"); received != "" {
					t.Errorf("backend received Authorization header %q", received)
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
			jwtValidator := &fakeJWTValidator{err: tt.jwtError}
			handler, err := NewHandler(
				backendURL,
				validator,
				jwtValidator,
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
			if tt.jwtToken != "" {
				req.Header.Set("Authorization", "Bearer "+tt.jwtToken)
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
		&fakeJWTValidator{},
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
	jwtValidator := &fakeJWTValidator{}

	tests := []struct {
		name      string
		backend   *url.URL
		validator KeyValidator
		jwt       JWTValidator
		header    string
		timeout   time.Duration
		logger    *slog.Logger
	}{
		{name: "missing backend", validator: validator, jwt: jwtValidator, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing validator", backend: backendURL, jwt: jwtValidator, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing JWT validator", backend: backendURL, validator: validator, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing header", backend: backendURL, validator: validator, jwt: jwtValidator, timeout: time.Second, logger: logger},
		{name: "invalid timeout", backend: backendURL, validator: validator, jwt: jwtValidator, header: "X-API-Key", logger: logger},
		{name: "missing logger", backend: backendURL, validator: validator, jwt: jwtValidator, header: "X-API-Key", timeout: time.Second},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if _, err := NewHandler(tt.backend, tt.validator, tt.jwt, tt.header, tt.timeout, tt.logger); err == nil {
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
