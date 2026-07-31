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
				"BACKEND_URL":       "http://localhost:9000",
				"CONTROL_PLANE_URL": "http://localhost:8000",
			},
		},
		{
			name: "missing backend",
			env: map[string]string{
				"CONTROL_PLANE_URL": "http://localhost:8000",
			},
			wantErr: "BACKEND_URL is required",
		},
		{
			name: "invalid Control Plane scheme",
			env: map[string]string{
				"BACKEND_URL":       "http://localhost:9000",
				"CONTROL_PLANE_URL": "ftp://localhost",
			},
			wantErr: "must use http or https",
		},
		{
			name: "invalid timeout",
			env: map[string]string{
				"BACKEND_URL":        "http://localhost:9000",
				"CONTROL_PLANE_URL":  "http://localhost:8000",
				"VALIDATION_TIMEOUT": "never",
			},
			wantErr: "parsing VALIDATION_TIMEOUT",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			for _, name := range []string{
				"BACKEND_URL", "CONTROL_PLANE_URL", "CONTROL_PLANE_VALIDATE_PATH",
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
