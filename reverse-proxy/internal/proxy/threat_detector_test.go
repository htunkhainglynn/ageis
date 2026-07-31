package proxy

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestPolicyThreatDetector(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name      string
		target    string
		rules     []ThreatPolicy
		policyErr error
		wantID    int64
		wantErr   error
	}{
		{
			name:   "matches encoded traversal in request target",
			target: "http://proxy.example/files?path=%2e%2e%2fetc",
			rules:  []ThreatPolicy{{ID: 7, Name: "Traversal", Pattern: `(?i)%2e%2e`, Severity: "high"}},
			wantID: 7,
		},
		{
			name:   "allows clean target",
			target: "http://proxy.example/orders?limit=10",
			rules:  []ThreatPolicy{{ID: 7, Pattern: `(?i)%2e%2e`}},
		},
		{
			name:    "invalid distributed regex fails closed",
			target:  "http://proxy.example/",
			rules:   []ThreatPolicy{{ID: 7, Pattern: `(?=unsupported)`}},
			wantErr: ErrPolicyUnavailable,
		},
		{
			name:      "policy outage fails closed",
			target:    "http://proxy.example/",
			policyErr: ErrPolicyUnavailable,
			wantErr:   ErrPolicyUnavailable,
		},
	}
	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			provider := policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
				return &PolicySnapshot{ThreatRules: tt.rules}, tt.policyErr
			})
			detector, _ := NewPolicyThreatDetector(provider)
			request := httptest.NewRequest(http.MethodGet, tt.target, nil)
			match, err := detector.Detect(context.Background(), request)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("error = %v, want %v", err, tt.wantErr)
			}
			if tt.wantID == 0 && match != nil {
				t.Fatalf("unexpected match: %#v", match)
			}
			if tt.wantID != 0 && (match == nil || match.RuleID != tt.wantID) {
				t.Fatalf("match = %#v, want rule %d", match, tt.wantID)
			}
		})
	}
}

func TestNewPolicyThreatDetectorValidation(t *testing.T) {
	t.Parallel()
	if _, err := NewPolicyThreatDetector(nil); err == nil {
		t.Fatal("expected missing policy provider error")
	}
}
