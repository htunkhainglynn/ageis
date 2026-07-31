package proxy_test

import (
	"context"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/controlplane"
	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

func TestAPIKeyValidationAndForwardingIntegration(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name             string
		apiKey           string
		controlStatus    int
		controlBody      string
		requestCount     int
		wantStatus       int
		wantControlCalls int32
		wantBackendCalls int32
	}{
		{
			name:             "valid key is cached and forwarded",
			apiKey:           "ak_valid",
			controlStatus:    http.StatusOK,
			controlBody:      `{"status":"success","data":{"id":1,"key_prefix":"ak_valid","owner_id":1,"scopes":["read"],"status":"active","expires_at":null}}`,
			requestCount:     2,
			wantStatus:       http.StatusOK,
			wantControlCalls: 1,
			wantBackendCalls: 2,
		},
		{
			name:             "revoked key is negatively cached",
			apiKey:           "ak_revoked",
			controlStatus:    http.StatusForbidden,
			controlBody:      `{"status":"error","errorCode":"API_KEY_REVOKED","message":"revoked"}`,
			requestCount:     2,
			wantStatus:       http.StatusForbidden,
			wantControlCalls: 1,
		},
		{
			name:             "Control Plane failures are not cached",
			apiKey:           "ak_unknown",
			controlStatus:    http.StatusServiceUnavailable,
			controlBody:      `{"status":"error","errorCode":"SERVICE_UNAVAILABLE"}`,
			requestCount:     2,
			wantStatus:       http.StatusBadGateway,
			wantControlCalls: 2,
		},
		{
			name:         "missing key is rejected locally",
			requestCount: 1,
			wantStatus:   http.StatusUnauthorized,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			var controlCalls atomic.Int32
			controlPlane := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				controlCalls.Add(1)
				if r.Method != http.MethodPost {
					t.Errorf("Control Plane method = %s, want POST", r.Method)
				}
				if r.URL.Path != "/api/v1/api-keys/validate" {
					t.Errorf("Control Plane path = %s", r.URL.Path)
				}
				if r.Header.Get("X-Aegis-Internal-Token") != "test-internal-token" {
					t.Error("Control Plane internal token header was not set")
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tt.controlStatus)
				_, _ = w.Write([]byte(tt.controlBody))
			}))
			t.Cleanup(controlPlane.Close)

			var backendCalls atomic.Int32
			backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				backendCalls.Add(1)
				if value := r.Header.Get("X-API-Key"); value != "" {
					t.Errorf("backend received raw API key %q", value)
				}
				if r.URL.Path != "/orders/42" || r.URL.RawQuery != "expand=items" {
					t.Errorf("forwarded URL = %s?%s", r.URL.Path, r.URL.RawQuery)
				}
				w.Header().Set("X-Backend", "orders")
				_, _ = w.Write([]byte("order response"))
			}))
			t.Cleanup(backend.Close)

			controlURL, _ := url.Parse(controlPlane.URL)
			controlClient, err := controlplane.NewClient(
				controlPlane.Client(),
				controlURL,
				"/api/v1/api-keys/validate",
				"test-internal-token",
			)
			if err != nil {
				t.Fatalf("create Control Plane client: %v", err)
			}
			validator, err := controlplane.NewCachedValidator(controlClient, time.Minute, time.Minute)
			if err != nil {
				t.Fatalf("create cached validator: %v", err)
			}
			backendURL, _ := url.Parse(backend.URL)
			handler, err := proxycore.NewHandler(
				backendURL,
				validator,
				jwtValidatorFunc(func(context.Context, string) error { return nil }),
				rateLimiterFunc(func(context.Context, *proxycore.KeyInfo, string) (proxycore.RateLimitResult, error) {
					return proxycore.RateLimitResult{Allowed: true}, nil
				}),
				ipBlockerFunc(func(context.Context, string) (bool, error) {
					return false, nil
				}),
				"X-API-Key",
				time.Second,
				slog.New(slog.NewTextHandler(io.Discard, nil)),
			)
			if err != nil {
				t.Fatalf("create proxy handler: %v", err)
			}

			for index := 0; index < tt.requestCount; index++ {
				request := httptest.NewRequest(http.MethodGet, "http://proxy.example/orders/42?expand=items", nil)
				if tt.apiKey != "" {
					request.Header.Set("X-API-Key", tt.apiKey)
					request.Header.Set("Authorization", "Bearer test-token")
				}
				recorder := httptest.NewRecorder()
				handler.ServeHTTP(recorder, request)

				if recorder.Code != tt.wantStatus {
					t.Fatalf("request %d status = %d, want %d; body=%s", index+1, recorder.Code, tt.wantStatus, recorder.Body.String())
				}
				if tt.wantBackendCalls > 0 {
					if recorder.Header().Get("X-Backend") != "orders" {
						t.Error("backend response header was not preserved")
					}
					if strings.TrimSpace(recorder.Body.String()) != "order response" {
						t.Errorf("backend body = %q", recorder.Body.String())
					}
				}
			}

			if calls := controlCalls.Load(); calls != tt.wantControlCalls {
				t.Errorf("Control Plane calls = %d, want %d", calls, tt.wantControlCalls)
			}
			if calls := backendCalls.Load(); calls != tt.wantBackendCalls {
				t.Errorf("backend calls = %d, want %d", calls, tt.wantBackendCalls)
			}
		})
	}
}

type jwtValidatorFunc func(context.Context, string) error

func (f jwtValidatorFunc) ValidateJWT(ctx context.Context, rawToken string) error {
	return f(ctx, rawToken)
}

type rateLimiterFunc func(
	context.Context,
	*proxycore.KeyInfo,
	string,
) (proxycore.RateLimitResult, error)

func (f rateLimiterFunc) Allow(
	ctx context.Context,
	keyInfo *proxycore.KeyInfo,
	path string,
) (proxycore.RateLimitResult, error) {
	return f(ctx, keyInfo, path)
}

type ipBlockerFunc func(context.Context, string) (bool, error)

func (f ipBlockerFunc) IsBlocked(ctx context.Context, remoteAddr string) (bool, error) {
	return f(ctx, remoteAddr)
}
