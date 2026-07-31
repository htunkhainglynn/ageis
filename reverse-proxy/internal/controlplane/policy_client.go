package controlplane

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type PolicyClient struct {
	httpClient    *http.Client
	endpoint      *url.URL
	internalToken string
}

type policyAPIResponse struct {
	Status  string                    `json:"status"`
	Message string                    `json:"message"`
	Data    *proxycore.PolicySnapshot `json:"data"`
}

func NewPolicyClient(
	httpClient *http.Client,
	baseURL *url.URL,
	policyPath string,
	internalToken string,
) (*PolicyClient, error) {
	if httpClient == nil {
		return nil, errors.New("HTTP client is required")
	}
	if baseURL == nil {
		return nil, errors.New("Control Plane URL is required")
	}
	if !strings.HasPrefix(policyPath, "/") {
		return nil, errors.New("policy path must start with /")
	}
	if strings.TrimSpace(internalToken) == "" {
		return nil, errors.New("internal API token is required")
	}

	return &PolicyClient{
		httpClient:    httpClient,
		endpoint:      baseURL.ResolveReference(&url.URL{Path: policyPath}),
		internalToken: internalToken,
	}, nil
}

func (c *PolicyClient) GetPolicy(ctx context.Context) (*proxycore.PolicySnapshot, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.endpoint.String(), nil)
	if err != nil {
		return nil, fmt.Errorf("creating policy request: %w", err)
	}
	req.Header.Set("X-Aegis-Internal-Token", c.internalToken)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: calling Control Plane: %w", proxycore.ErrPolicyUnavailable, err)
	}
	if resp == nil {
		return nil, fmt.Errorf("%w: Control Plane returned a nil response", proxycore.ErrPolicyUnavailable)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		return nil, fmt.Errorf("%w: reading Control Plane response: %w", proxycore.ErrPolicyUnavailable, err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%w: Control Plane returned HTTP %d", proxycore.ErrPolicyUnavailable, resp.StatusCode)
	}

	var envelope policyAPIResponse
	if err := json.Unmarshal(body, &envelope); err != nil {
		return nil, fmt.Errorf("%w: decoding Control Plane response: %w", proxycore.ErrPolicyUnavailable, err)
	}
	if envelope.Data == nil {
		return nil, fmt.Errorf("%w: Control Plane response omitted data", proxycore.ErrPolicyUnavailable)
	}
	return envelope.Data, nil
}
