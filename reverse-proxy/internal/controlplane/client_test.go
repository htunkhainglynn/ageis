package controlplane

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

func TestClientValidateKey(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		status    int
		body      string
		wantError error
	}{
		{
			name:   "active key",
			status: http.StatusOK,
			body:   `{"status":"success","data":{"id":1,"key_prefix":"ak_test","owner_id":2,"scopes":["read"],"status":"active","expires_at":null}}`,
		},
		{
			name:      "unknown key",
			status:    http.StatusNotFound,
			body:      `{"status":"error","errorCode":"API_KEY_NOT_FOUND","message":"not found"}`,
			wantError: proxycore.ErrKeyNotFound,
		},
		{
			name:      "revoked key",
			status:    http.StatusForbidden,
			body:      `{"status":"error","errorCode":"API_KEY_REVOKED","message":"revoked"}`,
			wantError: proxycore.ErrKeyRevoked,
		},
		{
			name:      "expired key",
			status:    http.StatusForbidden,
			body:      `{"status":"error","errorCode":"API_KEY_EXPIRED","message":"expired"}`,
			wantError: proxycore.ErrKeyExpired,
		},
		{
			name:      "invalid JSON",
			status:    http.StatusOK,
			body:      `{`,
			wantError: proxycore.ErrValidatorUnavailable,
		},
		{
			name:      "missing data",
			status:    http.StatusOK,
			body:      `{"status":"success","data":null}`,
			wantError: proxycore.ErrValidatorUnavailable,
		},
		{
			name:      "server error",
			status:    http.StatusInternalServerError,
			body:      `{"status":"error"}`,
			wantError: proxycore.ErrValidatorUnavailable,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()

			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodPost {
					t.Errorf("method = %s, want POST", r.Method)
				}
				if r.URL.Path != "/api/v1/api-keys/validate" {
					t.Errorf("path = %s", r.URL.Path)
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tt.status)
				_, _ = w.Write([]byte(tt.body))
			}))
			t.Cleanup(server.Close)

			baseURL, _ := url.Parse(server.URL)
			client, err := NewClient(server.Client(), baseURL, "/api/v1/api-keys/validate")
			if err != nil {
				t.Fatalf("create client: %v", err)
			}
			info, err := client.ValidateKey(context.Background(), "ak_secret")

			if tt.wantError != nil {
				if !errors.Is(err, tt.wantError) {
					t.Fatalf("error = %v, want %v", err, tt.wantError)
				}
				return
			}
			if err != nil {
				t.Fatalf("validate key: %v", err)
			}
			if info == nil || info.ID != 1 || info.Status != "active" {
				t.Fatalf("unexpected key info: %#v", info)
			}
		})
	}
}

func TestClientRejectsExpiredSuccessfulResponse(t *testing.T) {
	t.Parallel()
	expired := time.Now().Add(-time.Minute).UTC().Format(time.RFC3339Nano)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte(`{"status":"success","data":{"id":1,"status":"active","expires_at":"` + expired + `"}}`))
	}))
	t.Cleanup(server.Close)
	baseURL, _ := url.Parse(server.URL)
	client, _ := NewClient(server.Client(), baseURL, "/validate")

	_, err := client.ValidateKey(context.Background(), "ak_expired")
	if !errors.Is(err, proxycore.ErrKeyExpired) {
		t.Fatalf("error = %v, want expired", err)
	}
}

func TestClientDoesNotExposeKeyInURL(t *testing.T) {
	t.Parallel()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.String(), "ak_secret") {
			t.Fatal("raw API key leaked into URL")
		}
		_, _ = w.Write([]byte(`{"status":"success","data":{"id":1,"status":"active"}}`))
	}))
	t.Cleanup(server.Close)
	baseURL, _ := url.Parse(server.URL)
	client, _ := NewClient(server.Client(), baseURL, "/validate")

	if _, err := client.ValidateKey(context.Background(), "ak_secret"); err != nil {
		t.Fatalf("validate key: %v", err)
	}
}
