package controlplane

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

func TestPolicyClientGetPolicy(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		status    int
		body      string
		wantError bool
	}{
		{
			name:   "active policy",
			status: http.StatusOK,
			body: `{"status":"success","data":{
				"generated_at":"2026-07-31T00:00:00Z",
				"jwt":{"id":1,"algorithm":"HS256","verification_key":"secret","issuer":"aegis","audience":"api"},
				"rate_limit_rules":[{"id":2,"scope_type":"global","scope_value":null,"algorithm":"fixed_window","limit_count":10,"window_seconds":60,"burst_allowance":null}],
				"blocked_ip_addresses":["203.0.113.8"],
				"threat_rules":[{"id":3,"name":"Traversal","pattern":"%2e%2e","severity":"high"}]
			}}`,
		},
		{
			name:      "internal authentication rejected",
			status:    http.StatusUnauthorized,
			body:      `{"status":"error","errorCode":"INTERNAL_API_UNAUTHORIZED"}`,
			wantError: true,
		},
		{
			name:      "invalid JSON",
			status:    http.StatusOK,
			body:      `{`,
			wantError: true,
		},
		{
			name:      "missing data",
			status:    http.StatusOK,
			body:      `{"status":"success","data":null}`,
			wantError: true,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodGet {
					t.Errorf("method = %s, want GET", r.Method)
				}
				if r.URL.Path != "/api/v1/internal/proxy-config" {
					t.Errorf("path = %s", r.URL.Path)
				}
				if r.Header.Get("X-Aegis-Internal-Token") != "test-internal-token" {
					t.Error("internal API token header was not set")
				}
				w.WriteHeader(tt.status)
				_, _ = w.Write([]byte(tt.body))
			}))
			t.Cleanup(server.Close)

			baseURL, _ := url.Parse(server.URL)
			client, err := NewPolicyClient(
				server.Client(),
				baseURL,
				"/api/v1/internal/proxy-config",
				"test-internal-token",
			)
			if err != nil {
				t.Fatalf("create client: %v", err)
			}
			snapshot, err := client.GetPolicy(context.Background())
			if tt.wantError {
				if !errors.Is(err, proxycore.ErrPolicyUnavailable) {
					t.Fatalf("error = %v, want policy unavailable", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("get policy: %v", err)
			}
			if snapshot.JWT == nil || snapshot.JWT.Algorithm != "HS256" {
				t.Fatalf("unexpected JWT policy: %#v", snapshot.JWT)
			}
			if len(snapshot.RateLimitRules) != 1 {
				t.Fatalf("rate limit rules = %d, want 1", len(snapshot.RateLimitRules))
			}
			if len(snapshot.BlockedIPAddresses) != 1 || snapshot.BlockedIPAddresses[0] != "203.0.113.8" {
				t.Fatalf("blocked IP addresses = %#v", snapshot.BlockedIPAddresses)
			}
			if len(snapshot.ThreatRules) != 1 || snapshot.ThreatRules[0].ID != 3 {
				t.Fatalf("threat rules = %#v", snapshot.ThreatRules)
			}
		})
	}
}
