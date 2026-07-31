package controlplane

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type countingValidator struct {
	calls atomic.Int32
	info  *proxycore.KeyInfo
	err   error
}

func (v *countingValidator) ValidateKey(_ context.Context, _ string) (*proxycore.KeyInfo, error) {
	v.calls.Add(1)
	return v.info, v.err
}

func TestCachedValidatorCachesResults(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		err  error
	}{
		{name: "valid", err: nil},
		{name: "not found", err: proxycore.ErrKeyNotFound},
		{name: "revoked", err: proxycore.ErrKeyRevoked},
		{name: "expired", err: proxycore.ErrKeyExpired},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			next := &countingValidator{info: &proxycore.KeyInfo{ID: 1, Status: "active"}, err: tt.err}
			cache, err := NewCachedValidator(next, time.Minute, time.Minute)
			if err != nil {
				t.Fatalf("create cache: %v", err)
			}
			for range 2 {
				_, gotErr := cache.ValidateKey(context.Background(), "ak_same")
				if !errors.Is(gotErr, tt.err) {
					t.Fatalf("error = %v, want %v", gotErr, tt.err)
				}
			}
			if calls := next.calls.Load(); calls != 1 {
				t.Fatalf("validator calls = %d, want 1", calls)
			}
		})
	}
}

func TestCachedValidatorDoesNotCacheUnavailable(t *testing.T) {
	t.Parallel()
	next := &countingValidator{err: proxycore.ErrValidatorUnavailable}
	cache, _ := NewCachedValidator(next, time.Minute, time.Minute)

	for range 2 {
		_, _ = cache.ValidateKey(context.Background(), "ak_same")
	}
	if calls := next.calls.Load(); calls != 2 {
		t.Fatalf("validator calls = %d, want 2", calls)
	}
}

func TestCachedValidatorConcurrentAccess(t *testing.T) {
	t.Parallel()
	next := &countingValidator{info: &proxycore.KeyInfo{ID: 1, Status: "active"}}
	cache, _ := NewCachedValidator(next, time.Minute, time.Minute)

	var group sync.WaitGroup
	for range 100 {
		group.Add(1)
		go func() {
			defer group.Done()
			info, err := cache.ValidateKey(context.Background(), "ak_shared")
			if err != nil || info == nil {
				t.Errorf("validate key: info=%v err=%v", info, err)
			}
		}()
	}
	group.Wait()
}

func TestCachedValidatorRefreshesExpiredEntry(t *testing.T) {
	t.Parallel()
	next := &countingValidator{info: &proxycore.KeyInfo{ID: 1, Status: "active"}}
	cache, _ := NewCachedValidator(next, time.Minute, time.Minute)
	now := time.Date(2026, time.July, 31, 0, 0, 0, 0, time.UTC)
	cache.now = func() time.Time { return now }

	if _, err := cache.ValidateKey(context.Background(), "ak_rotating"); err != nil {
		t.Fatalf("initial validation: %v", err)
	}
	now = now.Add(2 * time.Minute)
	if _, err := cache.ValidateKey(context.Background(), "ak_rotating"); err != nil {
		t.Fatalf("refreshed validation: %v", err)
	}
	if calls := next.calls.Load(); calls != 2 {
		t.Fatalf("validator calls = %d, want 2 after cache expiry", calls)
	}
}
