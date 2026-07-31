package config

import (
	"strings"
	"testing"
	"time"
)

func TestLoad(t *testing.T) {
	tests := []struct {
		name    string
		env     map[string]string
		wantErr string
	}{
		{
			name: "valid minimum configuration",
			env: map[string]string{
				"BACKEND_URL":        "http://localhost:9000",
				"CONTROL_PLANE_URL":  "http://localhost:8000",
				"INTERNAL_API_TOKEN": "test-internal-token",
			},
		},
		{
			name: "missing backend",
			env: map[string]string{
				"CONTROL_PLANE_URL":  "http://localhost:8000",
				"INTERNAL_API_TOKEN": "test-internal-token",
			},
			wantErr: "BACKEND_URL is required",
		},
		{
			name: "invalid Control Plane scheme",
			env: map[string]string{
				"BACKEND_URL":        "http://localhost:9000",
				"CONTROL_PLANE_URL":  "ftp://localhost",
				"INTERNAL_API_TOKEN": "test-internal-token",
			},
			wantErr: "must use http or https",
		},
		{
			name: "invalid timeout",
			env: map[string]string{
				"BACKEND_URL":        "http://localhost:9000",
				"CONTROL_PLANE_URL":  "http://localhost:8000",
				"INTERNAL_API_TOKEN": "test-internal-token",
				"VALIDATION_TIMEOUT": "never",
			},
			wantErr: "parsing VALIDATION_TIMEOUT",
		},
		{
			name: "invalid Redis database",
			env: map[string]string{
				"BACKEND_URL":        "http://localhost:9000",
				"CONTROL_PLANE_URL":  "http://localhost:8000",
				"INTERNAL_API_TOKEN": "test-internal-token",
				"REDIS_DB":           "-1",
			},
			wantErr: "REDIS_DB must be a non-negative integer",
		},
		{
			name: "missing internal token",
			env: map[string]string{
				"BACKEND_URL":       "http://localhost:9000",
				"CONTROL_PLANE_URL": "http://localhost:8000",
			},
			wantErr: "INTERNAL_API_TOKEN is required",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			for _, name := range []string{
				"BACKEND_URL", "CONTROL_PLANE_URL", "CONTROL_PLANE_VALIDATE_PATH",
				"INTERNAL_API_TOKEN",
				"CONTROL_PLANE_POLICY_PATH", "POLICY_CACHE_TTL",
				"REDIS_ADDR", "REDIS_PASSWORD", "REDIS_DB",
				"VALIDATION_TIMEOUT", "VALIDATION_CACHE_TTL",
				"VALIDATION_NEGATIVE_CACHE_TTL", "SHUTDOWN_TIMEOUT",
			} {
				t.Setenv(name, "")
			}
			for name, value := range tt.env {
				t.Setenv(name, value)
			}

			cfg, err := Load()
			if tt.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tt.wantErr) {
					t.Fatalf("error = %v, want substring %q", err, tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("load config: %v", err)
			}
			if cfg.ValidationTimeout != 2*time.Second {
				t.Errorf("validation timeout = %s", cfg.ValidationTimeout)
			}
			if cfg.APIKeyHeader != "X-API-Key" {
				t.Errorf("API key header = %q", cfg.APIKeyHeader)
			}
		})
	}
}
