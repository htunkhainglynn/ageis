package controlplane

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type fakePolicySource struct {
	calls    atomic.Int32
	snapshot *proxycore.PolicySnapshot
	err      error
}

func (f *fakePolicySource) GetPolicy(context.Context) (*proxycore.PolicySnapshot, error) {
	f.calls.Add(1)
	return f.snapshot, f.err
}

func TestCachedPolicyProviderCachesAndClones(t *testing.T) {
	t.Parallel()
	source := &fakePolicySource{
		snapshot: &proxycore.PolicySnapshot{
			JWT: &proxycore.JWTPolicy{ID: 1, Algorithm: "HS256"},
			RateLimitRules: []proxycore.RateLimitPolicy{
				{ID: 2, ScopeType: "global"},
			},
			BlockedIPAddresses: []string{"203.0.113.8"},
			ThreatRules:        []proxycore.ThreatPolicy{{ID: 3, Pattern: "attack"}},
		},
	}
	cache, err := NewCachedPolicyProvider(source, time.Minute)
	if err != nil {
		t.Fatalf("create policy cache: %v", err)
	}

	first, err := cache.GetPolicy(context.Background())
	if err != nil {
		t.Fatalf("first policy: %v", err)
	}
	first.JWT.Algorithm = "changed"
	first.RateLimitRules[0].ScopeType = "changed"
	first.BlockedIPAddresses[0] = "198.51.100.9"
	first.ThreatRules[0].Pattern = "changed"

	second, err := cache.GetPolicy(context.Background())
	if err != nil {
		t.Fatalf("second policy: %v", err)
	}
	if second.JWT.Algorithm != "HS256" || second.RateLimitRules[0].ScopeType != "global" {
		t.Fatal("callers mutated cached policy")
	}
	if second.BlockedIPAddresses[0] != "203.0.113.8" {
		t.Fatal("callers mutated cached blocked IP addresses")
	}
	if second.ThreatRules[0].Pattern != "attack" {
		t.Fatal("callers mutated cached threat rules")
	}
	if source.calls.Load() != 1 {
		t.Fatalf("source calls = %d, want 1", source.calls.Load())
	}
}

func TestCachedPolicyProviderUsesStalePolicyDuringOutage(t *testing.T) {
	t.Parallel()
	source := &fakePolicySource{
		snapshot: &proxycore.PolicySnapshot{
			JWT: &proxycore.JWTPolicy{ID: 1, Algorithm: "HS256"},
		},
	}
	cache, _ := NewCachedPolicyProvider(source, time.Minute)
	now := time.Date(2026, time.July, 31, 0, 0, 0, 0, time.UTC)
	cache.now = func() time.Time { return now }

	if _, err := cache.GetPolicy(context.Background()); err != nil {
		t.Fatalf("prime cache: %v", err)
	}
	now = now.Add(2 * time.Minute)
	source.err = proxycore.ErrPolicyUnavailable
	source.snapshot = nil

	stale, err := cache.GetPolicy(context.Background())
	if err != nil {
		t.Fatalf("stale policy: %v", err)
	}
	if stale.JWT == nil || stale.JWT.ID != 1 {
		t.Fatalf("unexpected stale policy: %#v", stale)
	}
}

func TestCachedPolicyProviderFailsWithoutInitialPolicy(t *testing.T) {
	t.Parallel()
	source := &fakePolicySource{err: proxycore.ErrPolicyUnavailable}
	cache, _ := NewCachedPolicyProvider(source, time.Minute)

	_, err := cache.GetPolicy(context.Background())
	if !errors.Is(err, proxycore.ErrPolicyUnavailable) {
		t.Fatalf("error = %v, want policy unavailable", err)
	}
}
