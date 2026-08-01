package proxy

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type KeyInfo struct {
	ID        int64      `json:"id"`
	KeyPrefix string     `json:"key_prefix"`
	OwnerID   int64      `json:"owner_id"`
	Scopes    []string   `json:"scopes"`
	Status    string     `json:"status"`
	ExpiresAt *time.Time `json:"expires_at"`
}

type KeyValidator interface {
	ValidateKey(ctx context.Context, key string) (*KeyInfo, error)
}

type JWTValidator interface {
	ValidateJWT(ctx context.Context, rawToken string) error
}

type Handler struct {
	forwarder         *httputil.ReverseProxy
	validator         KeyValidator
	jwtValidator      JWTValidator
	rateLimiter       RateLimiter
	ipBlocker         IPBlocker
	threatDetector    ThreatDetector
	eventReporter     EventReporter
	policyProvider    PolicyProvider
	apiKeyHeader      string
	validationTimeout time.Duration
}

type errorBody struct {
	Status    string `json:"status"`
	ErrorCode string `json:"errorCode"`
	Message   string `json:"message"`
}

func NewHandler(
	backendURL *url.URL,
	validator KeyValidator,
	jwtValidator JWTValidator,
	rateLimiter RateLimiter,
	ipBlocker IPBlocker,
	threatDetector ThreatDetector,
	eventReporter EventReporter,
	apiKeyHeader string,
	validationTimeout time.Duration,
	logger *slog.Logger,
) (*Handler, error) {
	return newHandler(backendURL, validator, jwtValidator, rateLimiter, ipBlocker, threatDetector, eventReporter, nil, apiKeyHeader, validationTimeout, logger)
}

func NewHandlerWithPolicy(
	backendURL *url.URL,
	validator KeyValidator,
	jwtValidator JWTValidator,
	rateLimiter RateLimiter,
	ipBlocker IPBlocker,
	threatDetector ThreatDetector,
	eventReporter EventReporter,
	policyProvider PolicyProvider,
	apiKeyHeader string,
	validationTimeout time.Duration,
	logger *slog.Logger,
) (*Handler, error) {
	return newHandler(backendURL, validator, jwtValidator, rateLimiter, ipBlocker, threatDetector, eventReporter, policyProvider, apiKeyHeader, validationTimeout, logger)
}

func newHandler(
	backendURL *url.URL,
	validator KeyValidator,
	jwtValidator JWTValidator,
	rateLimiter RateLimiter,
	ipBlocker IPBlocker,
	threatDetector ThreatDetector,
	eventReporter EventReporter,
	policyProvider PolicyProvider,
	apiKeyHeader string,
	validationTimeout time.Duration,
	logger *slog.Logger,
) (*Handler, error) {
	if backendURL == nil {
		return nil, errors.New("backend URL is required")
	}
	if validator == nil {
		return nil, errors.New("key validator is required")
	}
	if jwtValidator == nil {
		return nil, errors.New("JWT validator is required")
	}
	if rateLimiter == nil {
		return nil, errors.New("rate limiter is required")
	}
	if ipBlocker == nil {
		return nil, errors.New("IP blocker is required")
	}
	if threatDetector == nil {
		return nil, errors.New("threat detector is required")
	}
	if eventReporter == nil {
		return nil, errors.New("event reporter is required")
	}
	if strings.TrimSpace(apiKeyHeader) == "" {
		return nil, errors.New("API key header is required")
	}
	if validationTimeout <= 0 {
		return nil, errors.New("validation timeout must be greater than zero")
	}
	if logger == nil {
		return nil, errors.New("logger is required")
	}

	forwarder := httputil.NewSingleHostReverseProxy(backendURL)
	forwarder.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		logger.ErrorContext(r.Context(), "backend forwarding failed", "error", err)
		writeError(w, http.StatusBadGateway, "BACKEND_UNAVAILABLE", "The upstream service is unavailable.")
	}

	return &Handler{
		forwarder:         forwarder,
		validator:         validator,
		jwtValidator:      jwtValidator,
		rateLimiter:       rateLimiter,
		ipBlocker:         ipBlocker,
		threatDetector:    threatDetector,
		eventReporter:     eventReporter,
		policyProvider:    policyProvider,
		apiKeyHeader:      apiKeyHeader,
		validationTimeout: validationTimeout,
	}, nil
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	event := SecurityEvent{
		EventType: "proxy_error", SourceIP: sourceIP(r.RemoteAddr),
		Method: r.Method, Path: r.URL.Path, StatusCode: http.StatusInternalServerError,
	}
	defer func() { h.eventReporter.Report(event) }()

	ctx, cancel := context.WithTimeout(r.Context(), h.validationTimeout)
	defer cancel()

	blocked, err := h.ipBlocker.IsBlocked(ctx, r.RemoteAddr)
	if err != nil {
		if errors.Is(err, ErrClientIPInvalid) {
			event.EventType, event.StatusCode = "client_ip_invalid", http.StatusBadRequest
			writeError(w, http.StatusBadRequest, "CLIENT_IP_INVALID", "The client network address is invalid.")
		} else {
			event.EventType, event.StatusCode = "policy_unavailable", http.StatusServiceUnavailable
			writeError(w, http.StatusServiceUnavailable, "IP_BLOCK_POLICY_UNAVAILABLE", "IP block policy is temporarily unavailable.")
		}
		return
	}
	if blocked {
		event.EventType, event.StatusCode = "ip_blocked", http.StatusForbidden
		writeError(w, http.StatusForbidden, "IP_BLOCKED", "Requests from this IP address are blocked.")
		return
	}

	threat, err := h.threatDetector.Detect(ctx, r)
	if err != nil {
		event.EventType, event.StatusCode = "policy_unavailable", http.StatusServiceUnavailable
		writeError(w, http.StatusServiceUnavailable, "THREAT_POLICY_UNAVAILABLE", "Threat policy is temporarily unavailable.")
		return
	}
	if threat != nil {
		event.EventType, event.StatusCode = "threat_detected", http.StatusForbidden
		event.RuleID = &threat.RuleID
		writeError(w, http.StatusForbidden, "THREAT_DETECTED", "The request matched a security rule.")
		return
	}

	key := strings.TrimSpace(r.Header.Get(h.apiKeyHeader))
	if key == "" {
		event.EventType, event.StatusCode = "api_key_missing", http.StatusUnauthorized
		writeError(w, http.StatusUnauthorized, "API_KEY_MISSING", fmt.Sprintf("%s header is required.", h.apiKeyHeader))
		return
	}

	keyInfo, err := h.validator.ValidateKey(ctx, key)
	if err != nil {
		switch {
		case errors.Is(err, ErrKeyNotFound):
			event.EventType, event.StatusCode = "api_key_invalid", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "API_KEY_INVALID", "The API key is invalid.")
		case errors.Is(err, ErrKeyRevoked):
			event.EventType, event.StatusCode = "api_key_revoked", http.StatusForbidden
			writeError(w, http.StatusForbidden, "API_KEY_REVOKED", "The API key has been revoked.")
		case errors.Is(err, ErrKeyExpired):
			event.EventType, event.StatusCode = "api_key_expired", http.StatusForbidden
			writeError(w, http.StatusForbidden, "API_KEY_EXPIRED", "The API key has expired.")
		default:
			event.EventType, event.StatusCode = "validation_unavailable", http.StatusBadGateway
			writeError(w, http.StatusBadGateway, "CONTROL_PLANE_UNAVAILABLE", "API key validation is temporarily unavailable.")
		}
		return
	}
	event.APIKeyID = &keyInfo.ID

	rawJWT, err := bearerToken(r.Header.Get("Authorization"))
	if err != nil {
		if errors.Is(err, ErrJWTMissing) {
			event.EventType, event.StatusCode = "jwt_missing", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "JWT_MISSING", "Authorization Bearer token is required.")
		} else {
			event.EventType, event.StatusCode = "jwt_invalid", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "JWT_INVALID", "The JWT is invalid.")
		}
		return
	}
	if err := h.jwtValidator.ValidateJWT(ctx, rawJWT); err != nil {
		switch {
		case errors.Is(err, ErrJWTMissing):
			event.EventType, event.StatusCode = "jwt_missing", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "JWT_MISSING", "Authorization Bearer token is required.")
		case errors.Is(err, ErrJWTExpired):
			event.EventType, event.StatusCode = "jwt_expired", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "JWT_EXPIRED", "The JWT has expired.")
		case errors.Is(err, ErrJWTInvalid):
			event.EventType, event.StatusCode = "jwt_invalid", http.StatusUnauthorized
			writeError(w, http.StatusUnauthorized, "JWT_INVALID", "The JWT is invalid.")
		default:
			event.EventType, event.StatusCode = "policy_unavailable", http.StatusBadGateway
			writeError(w, http.StatusBadGateway, "CONTROL_PLANE_UNAVAILABLE", "JWT validation policy is temporarily unavailable.")
		}
		return
	}

	if err := h.authorizeRoute(ctx, r, keyInfo, &event, w); err != nil {
		return
	}

	rateLimitResult, err := h.rateLimiter.Allow(ctx, keyInfo, r.URL.Path)
	if err != nil {
		event.EventType, event.StatusCode = "rate_limit_unavailable", http.StatusServiceUnavailable
		writeError(w, http.StatusServiceUnavailable, "RATE_LIMIT_UNAVAILABLE", "Rate limiting is temporarily unavailable.")
		return
	}
	if rateLimitResult.Limit > 0 {
		w.Header().Set("X-RateLimit-Limit", strconv.FormatInt(rateLimitResult.Limit, 10))
		w.Header().Set("X-RateLimit-Remaining", strconv.FormatInt(rateLimitResult.Remaining, 10))
	}
	if !rateLimitResult.Allowed {
		event.EventType, event.StatusCode = "rate_limited", http.StatusTooManyRequests
		retrySeconds := int64(math.Ceil(rateLimitResult.RetryAfter.Seconds()))
		if retrySeconds < 1 {
			retrySeconds = 1
		}
		w.Header().Set("Retry-After", strconv.FormatInt(retrySeconds, 10))
		writeError(w, http.StatusTooManyRequests, "RATE_LIMIT_EXCEEDED", "Rate limit exceeded.")
		return
	}

	forwardRequest := r.Clone(r.Context())
	forwardRequest.Header = r.Header.Clone()
	forwardRequest.Header.Del(h.apiKeyHeader)
	forwardRequest.Header.Del("Authorization")
	capture := &proxyStatusRecorder{ResponseWriter: w, status: http.StatusOK}
	h.forwarder.ServeHTTP(capture, forwardRequest)
	event.StatusCode = capture.status
	if capture.status >= 500 {
		event.EventType = "upstream_error"
	} else {
		event.EventType = "request_forwarded"
	}
}

func sourceIP(remoteAddr string) string {
	address, err := parseClientIP(remoteAddr)
	if err != nil {
		return "unknown"
	}
	return address.String()
}

func hasScope(scopes []string, required string) bool {
	for _, scope := range scopes {
		if strings.TrimSpace(scope) == required {
			return true
		}
	}
	return false
}

func (h *Handler) authorizeRoute(
	ctx context.Context,
	r *http.Request,
	keyInfo *KeyInfo,
	event *SecurityEvent,
	w http.ResponseWriter,
) error {
	if h.policyProvider == nil {
		return nil
	}
	snapshot, err := h.policyProvider.GetPolicy(ctx)
	if err != nil || snapshot == nil {
		event.EventType, event.StatusCode = "policy_unavailable", http.StatusServiceUnavailable
		writeError(w, http.StatusServiceUnavailable, "ROUTE_PERMISSION_POLICY_UNAVAILABLE", "Route permission policy is temporarily unavailable.")
		return err
	}
	for _, permission := range snapshot.RoutePermissions {
		if permission.Method != r.Method || permission.PathPattern != r.URL.Path {
			continue
		}
		if hasScope(keyInfo.Scopes, permission.RequiredScope) {
			return nil
		}
		event.EventType, event.StatusCode = "insufficient_scope", http.StatusForbidden
		writeError(w, http.StatusForbidden, "INSUFFICIENT_SCOPE", "This API key does not have permission to access this route.")
		return ErrKeyScopeForbidden
	}
	return nil
}

type proxyStatusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *proxyStatusRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func (r *proxyStatusRecorder) Unwrap() http.ResponseWriter {
	return r.ResponseWriter
}

func bearerToken(value string) (string, error) {
	parts := strings.Fields(value)
	if len(parts) == 0 {
		return "", ErrJWTMissing
	}
	if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") || parts[1] == "" {
		return "", ErrJWTInvalid
	}
	return parts[1], nil
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(errorBody{
		Status:    "error",
		ErrorCode: code,
		Message:   message,
	}); err != nil {
		return
	}
}
