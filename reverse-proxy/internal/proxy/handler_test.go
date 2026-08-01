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

type fakeRateLimiter struct {
	result RateLimitResult
	err    error
	calls  atomic.Int32
}

type fakeIPBlocker struct {
	blocked bool
	err     error
	calls   atomic.Int32
}

type fakeThreatDetector struct {
	match *ThreatMatch
	err   error
	calls atomic.Int32
}

type fakeEventReporter struct {
	events []SecurityEvent
}

func (f *fakeEventReporter) Report(event SecurityEvent) {
	f.events = append(f.events, event)
}

func (f *fakeThreatDetector) Detect(
	_ context.Context,
	_ *http.Request,
) (*ThreatMatch, error) {
	f.calls.Add(1)
	return f.match, f.err
}

func (f *fakeIPBlocker) IsBlocked(_ context.Context, _ string) (bool, error) {
	f.calls.Add(1)
	return f.blocked, f.err
}

func (f *fakeRateLimiter) Allow(
	_ context.Context,
	_ *KeyInfo,
	_ string,
) (RateLimitResult, error) {
	f.calls.Add(1)
	return f.result, f.err
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
		method           string
		scopes           []string
		rateLimitResult  RateLimitResult
		rateLimitError   error
		ipBlocked        bool
		ipBlockError     error
		threatMatch      bool
		threatError      error
		wantStatus       int
		wantErrorCode    string
		wantBackendCalls int32
	}{
		{name: "blocked IP", ipBlocked: true, wantStatus: http.StatusForbidden, wantErrorCode: "IP_BLOCKED"},
		{name: "IP policy unavailable", ipBlockError: ErrPolicyUnavailable, wantStatus: http.StatusServiceUnavailable, wantErrorCode: "IP_BLOCK_POLICY_UNAVAILABLE"},
		{name: "threat detected", threatMatch: true, wantStatus: http.StatusForbidden, wantErrorCode: "THREAT_DETECTED"},
		{name: "threat policy unavailable", threatError: ErrPolicyUnavailable, wantStatus: http.StatusServiceUnavailable, wantErrorCode: "THREAT_POLICY_UNAVAILABLE"},
		{name: "missing key", wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_MISSING"},
		{name: "unknown key", apiKey: "ak_unknown", validationErr: ErrKeyNotFound, wantStatus: http.StatusUnauthorized, wantErrorCode: "API_KEY_INVALID"},
		{name: "revoked key", apiKey: "ak_revoked", validationErr: ErrKeyRevoked, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_REVOKED"},
		{name: "expired key", apiKey: "ak_expired", validationErr: ErrKeyExpired, wantStatus: http.StatusForbidden, wantErrorCode: "API_KEY_EXPIRED"},
		{name: "validator unavailable", apiKey: "ak_valid", validationErr: ErrValidatorUnavailable, wantStatus: http.StatusBadGateway, wantErrorCode: "CONTROL_PLANE_UNAVAILABLE"},
		{name: "missing JWT", apiKey: "ak_valid", wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_MISSING"},
		{name: "invalid JWT", apiKey: "ak_valid", jwtToken: "invalid", jwtError: ErrJWTInvalid, wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_INVALID"},
		{name: "expired JWT", apiKey: "ak_valid", jwtToken: "expired", jwtError: ErrJWTExpired, wantStatus: http.StatusUnauthorized, wantErrorCode: "JWT_EXPIRED"},
		{name: "policy unavailable", apiKey: "ak_valid", jwtToken: "token", jwtError: ErrPolicyUnavailable, wantStatus: http.StatusBadGateway, wantErrorCode: "CONTROL_PLANE_UNAVAILABLE"},
		{name: "write scope allowed", apiKey: "ak_valid", jwtToken: "valid", method: http.MethodPost, scopes: []string{"orders:write"}, rateLimitResult: RateLimitResult{Allowed: true, Limit: 10, Remaining: 9}, wantStatus: http.StatusCreated, wantBackendCalls: 1},
		{name: "rate limiter unavailable", apiKey: "ak_valid", jwtToken: "valid", rateLimitError: errors.New("Redis unavailable"), wantStatus: http.StatusServiceUnavailable, wantErrorCode: "RATE_LIMIT_UNAVAILABLE"},
		{name: "rate limit exceeded", apiKey: "ak_valid", jwtToken: "valid", rateLimitResult: RateLimitResult{Allowed: false, Limit: 2, RetryAfter: time.Second}, wantStatus: http.StatusTooManyRequests, wantErrorCode: "RATE_LIMIT_EXCEEDED"},
		{name: "valid credentials", apiKey: "ak_valid", jwtToken: "valid", rateLimitResult: RateLimitResult{Allowed: true, Limit: 10, Remaining: 9}, wantStatus: http.StatusCreated, wantBackendCalls: 1},
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
			scopes := tt.scopes
			if scopes == nil {
				scopes = []string{"orders:read"}
			}
			validator := &fakeValidator{
				keyInfo: &KeyInfo{ID: 1, Status: "active", Scopes: scopes},
				err:     tt.validationErr,
			}
			jwtValidator := &fakeJWTValidator{err: tt.jwtError}
			rateLimiter := &fakeRateLimiter{result: tt.rateLimitResult, err: tt.rateLimitError}
			ipBlocker := &fakeIPBlocker{blocked: tt.ipBlocked, err: tt.ipBlockError}
			threatDetector := &fakeThreatDetector{err: tt.threatError}
			eventReporter := &fakeEventReporter{}
			if tt.threatMatch {
				threatDetector.match = &ThreatMatch{RuleID: 1, Severity: "high"}
			}
			handler, err := NewHandler(
				backendURL,
				validator,
				jwtValidator,
				rateLimiter,
				ipBlocker,
				threatDetector,
				eventReporter,
				"X-API-Key",
				time.Second,
				slog.New(slog.NewTextHandler(io.Discard, nil)),
			)
			if err != nil {
				t.Fatalf("create handler: %v", err)
			}

			method := tt.method
			if method == "" {
				method = http.MethodGet
			}
			req := httptest.NewRequest(method, "http://proxy.example/orders?limit=10", nil)
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
			if len(eventReporter.events) != 1 || eventReporter.events[0].StatusCode != tt.wantStatus {
				t.Fatalf("reported events = %#v, want one HTTP %d event", eventReporter.events, tt.wantStatus)
			}
			if got := backendCalls.Load(); got != tt.wantBackendCalls {
				t.Fatalf("backend calls = %d, want %d", got, tt.wantBackendCalls)
			}
			if tt.wantErrorCode != "" && !strings.Contains(recorder.Body.String(), `"`+tt.wantErrorCode+`"`) {
				t.Errorf("response body %q does not contain error code %q", recorder.Body.String(), tt.wantErrorCode)
			}
			if tt.wantBackendCalls == 1 {
				if got := recorder.Header().Get("X-RateLimit-Remaining"); got != "9" {
					t.Errorf("rate-limit remaining = %q, want 9", got)
				}
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
		&fakeRateLimiter{result: RateLimitResult{Allowed: true}},
		&fakeIPBlocker{},
		&fakeThreatDetector{},
		&fakeEventReporter{},
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

func TestHasScopeRequiresExactScope(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		scopes   []string
		required string
		want     bool
	}{
		{name: "specific match", scopes: []string{"echo:read"}, required: "echo:read", want: true},
		{name: "resource wildcard is not implicit", scopes: []string{"echo:*"}, required: "echo:write", want: false},
		{name: "global wildcard is not implicit", scopes: []string{"*"}, required: "echo:write", want: false},
		{name: "missing write", scopes: []string{"echo:read"}, required: "echo:write", want: false},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := hasScope(tt.scopes, tt.required); got != tt.want {
				t.Fatalf("hasScope() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestHandlerEnforcesBackendRoutePermissionPolicy(t *testing.T) {
	t.Parallel()

	backendCalls := atomic.Int32{}
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		backendCalls.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(backend.Close)
	backendURL, _ := url.Parse(backend.URL)

	policy := &PolicySnapshot{RoutePermissions: []RoutePermissionPolicy{
		{ID: 1, Method: http.MethodGet, PathPattern: "/protected", RequiredScope: "orders:read"},
		{ID: 2, Method: http.MethodPost, PathPattern: "/protected", RequiredScope: "orders:write"},
	}}
	provider := policyProviderFunc(func(context.Context) (*PolicySnapshot, error) { return policy, nil })
	rateLimiter := &fakeRateLimiter{result: RateLimitResult{Allowed: true}}
	reporter := &fakeEventReporter{}
	handler, err := NewHandlerWithPolicy(
		backendURL,
		&fakeValidator{keyInfo: &KeyInfo{ID: 9, Scopes: []string{"orders:read"}}},
		&fakeJWTValidator{}, rateLimiter, &fakeIPBlocker{}, &fakeThreatDetector{}, reporter,
		provider, "X-API-Key", time.Second, slog.New(slog.NewTextHandler(io.Discard, nil)),
	)
	if err != nil {
		t.Fatalf("create handler: %v", err)
	}

	tests := []struct {
		name          string
		method        string
		path          string
		wantStatus    int
		wantEvent     string
		wantRateCalls int32
	}{
		{"matching scope allowed", http.MethodGet, "/protected", http.StatusOK, "request_forwarded", 1},
		{"missing scope denied", http.MethodPost, "/protected", http.StatusForbidden, "insufficient_scope", 0},
		{"method mismatch allowed by default", http.MethodPut, "/protected", http.StatusOK, "request_forwarded", 1},
		{"path mismatch allowed by default", http.MethodGet, "/other", http.StatusOK, "request_forwarded", 1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			reporter.events = nil
			rateLimiter.calls.Store(0)
			req := httptest.NewRequest(tt.method, "http://proxy.example"+tt.path, nil)
			req.Header.Set("X-API-Key", "ak_valid")
			req.Header.Set("Authorization", "Bearer valid")
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, req)
			if recorder.Code != tt.wantStatus {
				t.Fatalf("status = %d, want %d; body=%s", recorder.Code, tt.wantStatus, recorder.Body.String())
			}
			if !strings.Contains(recorder.Body.String(), `"INSUFFICIENT_SCOPE"`) && tt.wantEvent == "insufficient_scope" {
				t.Fatalf("body = %s, want insufficient scope error", recorder.Body.String())
			}
			if len(reporter.events) != 1 || reporter.events[0].EventType != tt.wantEvent {
				t.Fatalf("events = %#v, want %s", reporter.events, tt.wantEvent)
			}
			if got := rateLimiter.calls.Load(); got != tt.wantRateCalls {
				t.Fatalf("rate limiter calls = %d, want %d", got, tt.wantRateCalls)
			}
		})
	}
	if got := backendCalls.Load(); got != 3 {
		t.Fatalf("backend calls = %d, want 3", got)
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
	rateLimiter := &fakeRateLimiter{}
	ipBlocker := &fakeIPBlocker{}
	threatDetector := &fakeThreatDetector{}
	eventReporter := &fakeEventReporter{}

	tests := []struct {
		name      string
		backend   *url.URL
		validator KeyValidator
		jwt       JWTValidator
		limiter   RateLimiter
		blocker   IPBlocker
		detector  ThreatDetector
		reporter  EventReporter
		header    string
		timeout   time.Duration
		logger    *slog.Logger
	}{
		{name: "missing backend", validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing validator", backend: backendURL, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing JWT validator", backend: backendURL, validator: validator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing rate limiter", backend: backendURL, validator: validator, jwt: jwtValidator, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing IP blocker", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing threat detector", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, reporter: eventReporter, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing event reporter", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, header: "X-API-Key", timeout: time.Second, logger: logger},
		{name: "missing header", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, timeout: time.Second, logger: logger},
		{name: "invalid timeout", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", logger: logger},
		{name: "missing logger", backend: backendURL, validator: validator, jwt: jwtValidator, limiter: rateLimiter, blocker: ipBlocker, detector: threatDetector, reporter: eventReporter, header: "X-API-Key", timeout: time.Second},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if _, err := NewHandler(tt.backend, tt.validator, tt.jwt, tt.limiter, tt.blocker, tt.detector, tt.reporter, tt.header, tt.timeout, tt.logger); err == nil {
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
