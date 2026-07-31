package controlplane

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

const maxResponseBytes = 1 << 20

type Client struct {
	httpClient *http.Client
	endpoint   *url.URL
}

type validationRequest struct {
	APIKey string `json:"api_key"`
}

type apiResponse struct {
	Status  string             `json:"status"`
	Message string             `json:"message"`
	Data    *proxycore.KeyInfo `json:"data"`
}

type apiErrorResponse struct {
	ErrorCode string `json:"errorCode"`
	Message   string `json:"message"`
}

func NewClient(httpClient *http.Client, baseURL *url.URL, validationPath string) (*Client, error) {
	if httpClient == nil {
		return nil, errors.New("HTTP client is required")
	}
	if baseURL == nil {
		return nil, errors.New("Control Plane URL is required")
	}
	if !strings.HasPrefix(validationPath, "/") {
		return nil, errors.New("validation path must start with /")
	}

	endpoint := baseURL.ResolveReference(&url.URL{Path: validationPath})
	return &Client{httpClient: httpClient, endpoint: endpoint}, nil
}

func (c *Client) ValidateKey(ctx context.Context, key string) (*proxycore.KeyInfo, error) {
	payload, err := json.Marshal(validationRequest{APIKey: key})
	if err != nil {
		return nil, fmt.Errorf("encoding key validation request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.endpoint.String(), bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("creating key validation request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: calling Control Plane: %w", proxycore.ErrValidatorUnavailable, err)
	}
	if resp == nil {
		return nil, fmt.Errorf("%w: Control Plane returned a nil response", proxycore.ErrValidatorUnavailable)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		return nil, fmt.Errorf("%w: reading Control Plane response: %w", proxycore.ErrValidatorUnavailable, err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, classifyError(resp.StatusCode, body)
	}

	var envelope apiResponse
	if err := json.Unmarshal(body, &envelope); err != nil {
		return nil, fmt.Errorf("%w: decoding Control Plane response: %w", proxycore.ErrValidatorUnavailable, err)
	}
	if envelope.Data == nil {
		return nil, fmt.Errorf("%w: Control Plane response omitted data", proxycore.ErrValidatorUnavailable)
	}

	switch strings.ToLower(envelope.Data.Status) {
	case "active":
		if envelope.Data.ExpiresAt != nil && !envelope.Data.ExpiresAt.After(time.Now()) {
			return nil, proxycore.ErrKeyExpired
		}
		return envelope.Data, nil
	case "revoked":
		return nil, proxycore.ErrKeyRevoked
	default:
		return nil, fmt.Errorf("%w: unsupported key status %q", proxycore.ErrValidatorUnavailable, envelope.Data.Status)
	}
}

func classifyError(status int, body []byte) error {
	var response apiErrorResponse
	_ = json.Unmarshal(body, &response)

	switch {
	case status == http.StatusNotFound || status == http.StatusUnauthorized:
		return proxycore.ErrKeyNotFound
	case status == http.StatusForbidden && response.ErrorCode == "API_KEY_EXPIRED":
		return proxycore.ErrKeyExpired
	case status == http.StatusForbidden:
		return proxycore.ErrKeyRevoked
	default:
		return fmt.Errorf("%w: Control Plane returned HTTP %d", proxycore.ErrValidatorUnavailable, status)
	}
}
