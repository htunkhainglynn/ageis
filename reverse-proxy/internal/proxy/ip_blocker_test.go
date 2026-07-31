package proxy

import (
	"context"
	"errors"
	"testing"
)

func TestPolicyIPBlocker(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name       string
		remoteAddr string
		blockedIPs []string
		policyErr  error
		want       bool
		wantErr    error
	}{
		{
			name:       "blocks IPv4 direct peer",
			remoteAddr: "203.0.113.8:4567",
			blockedIPs: []string{"203.0.113.8"},
			want:       true,
		},
		{
			name:       "blocks canonical IPv6 direct peer",
			remoteAddr: "[2001:db8::8]:4567",
			blockedIPs: []string{"2001:db8::8"},
			want:       true,
		},
		{
			name:       "ignores forwarded header semantics and allows other peer",
			remoteAddr: "198.51.100.4:4567",
			blockedIPs: []string{"203.0.113.8"},
		},
		{
			name:       "rejects malformed direct peer",
			remoteAddr: "not-an-address",
			wantErr:    ErrClientIPInvalid,
		},
		{
			name:       "fails closed when policy unavailable",
			remoteAddr: "198.51.100.4:4567",
			policyErr:  ErrPolicyUnavailable,
			wantErr:    ErrPolicyUnavailable,
		},
		{
			name:       "fails closed on invalid trusted policy",
			remoteAddr: "198.51.100.4:4567",
			blockedIPs: []string{"invalid"},
			wantErr:    ErrPolicyUnavailable,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			provider := policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
				if tt.policyErr != nil {
					return nil, tt.policyErr
				}
				return &PolicySnapshot{BlockedIPAddresses: tt.blockedIPs}, nil
			})
			blocker, err := NewPolicyIPBlocker(provider)
			if err != nil {
				t.Fatalf("create blocker: %v", err)
			}

			got, err := blocker.IsBlocked(context.Background(), tt.remoteAddr)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("error = %v, want %v", err, tt.wantErr)
			}
			if got != tt.want {
				t.Fatalf("blocked = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNewPolicyIPBlockerValidation(t *testing.T) {
	t.Parallel()
	if _, err := NewPolicyIPBlocker(nil); err == nil {
		t.Fatal("expected missing policy provider error")
	}
}
