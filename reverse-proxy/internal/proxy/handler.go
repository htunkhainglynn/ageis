package proxy

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
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
		apiKeyHeader:      apiKeyHeader,
		validationTimeout: validationTimeout,
	}, nil
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	key := strings.TrimSpace(r.Header.Get(h.apiKeyHeader))
	if key == "" {
		writeError(w, http.StatusUnauthorized, "API_KEY_MISSING", fmt.Sprintf("%s header is required.", h.apiKeyHeader))
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), h.validationTimeout)
	defer cancel()

	_, err := h.validator.ValidateKey(ctx, key)
	if err != nil {
		switch {
		case errors.Is(err, ErrKeyNotFound):
			writeError(w, http.StatusUnauthorized, "API_KEY_INVALID", "The API key is invalid.")
		case errors.Is(err, ErrKeyRevoked):
			writeError(w, http.StatusForbidden, "API_KEY_REVOKED", "The API key has been revoked.")
		case errors.Is(err, ErrKeyExpired):
			writeError(w, http.StatusForbidden, "API_KEY_EXPIRED", "The API key has expired.")
		default:
			writeError(w, http.StatusBadGateway, "CONTROL_PLANE_UNAVAILABLE", "API key validation is temporarily unavailable.")
		}
		return
	}

	rawJWT, err := bearerToken(r.Header.Get("Authorization"))
	if err != nil {
		if errors.Is(err, ErrJWTMissing) {
			writeError(w, http.StatusUnauthorized, "JWT_MISSING", "Authorization Bearer token is required.")
		} else {
			writeError(w, http.StatusUnauthorized, "JWT_INVALID", "The JWT is invalid.")
		}
		return
	}
	if err := h.jwtValidator.ValidateJWT(ctx, rawJWT); err != nil {
		switch {
		case errors.Is(err, ErrJWTMissing):
			writeError(w, http.StatusUnauthorized, "JWT_MISSING", "Authorization Bearer token is required.")
		case errors.Is(err, ErrJWTExpired):
			writeError(w, http.StatusUnauthorized, "JWT_EXPIRED", "The JWT has expired.")
		case errors.Is(err, ErrJWTInvalid):
			writeError(w, http.StatusUnauthorized, "JWT_INVALID", "The JWT is invalid.")
		default:
			writeError(w, http.StatusBadGateway, "CONTROL_PLANE_UNAVAILABLE", "JWT validation policy is temporarily unavailable.")
		}
		return
	}

	forwardRequest := r.Clone(r.Context())
	forwardRequest.Header = r.Header.Clone()
	forwardRequest.Header.Del(h.apiKeyHeader)
	forwardRequest.Header.Del("Authorization")
	h.forwarder.ServeHTTP(w, forwardRequest)
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
