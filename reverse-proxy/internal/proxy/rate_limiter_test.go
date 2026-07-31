package proxy

import (
	"context"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestRedisRateLimiterAlgorithms(t *testing.T) {
	tests := []struct {
		name        string
		algorithm   string
		limit       int64
		burst       *int64
		allowCount  int
		denyRequest int
	}{
		{
			name:        "fixed window",
			algorithm:   "fixed_window",
			limit:       2,
			allowCount:  2,
			denyRequest: 3,
		},
		{
			name:        "sliding window",
			algorithm:   "sliding_window",
			limit:       2,
			allowCount:  2,
			denyRequest: 3,
		},
		{
			name:        "token bucket with burst",
			algorithm:   "token_bucket",
			limit:       2,
			burst:       int64Pointer(1),
			allowCount:  3,
			denyRequest: 4,
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			redisServer := miniredis.RunT(t)
			client := redis.NewClient(&redis.Options{Addr: redisServer.Addr()})
			t.Cleanup(func() { _ = client.Close() })

			snapshot := &PolicySnapshot{
				RateLimitRules: []RateLimitPolicy{
					{
						ID:             1,
						ScopeType:      "global",
						Algorithm:      tt.algorithm,
						LimitCount:     tt.limit,
						WindowSeconds:  1,
						BurstAllowance: tt.burst,
					},
				},
			}
			limiter, err := NewRedisRateLimiter(
				client,
				policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
					return snapshot, nil
				}),
			)
			if err != nil {
				t.Fatalf("create limiter: %v", err)
			}
			limiter.now = func() time.Time {
				return time.Date(2026, time.July, 31, 0, 0, 0, 0, time.UTC)
			}

			for requestNumber := 1; requestNumber <= tt.denyRequest; requestNumber++ {
				result, err := limiter.Allow(
					context.Background(),
					&KeyInfo{ID: 9},
					"/orders",
				)
				if err != nil {
					t.Fatalf("request %d: %v", requestNumber, err)
				}
				if requestNumber <= tt.allowCount && !result.Allowed {
					t.Fatalf("request %d was denied, expected allowed", requestNumber)
				}
				if requestNumber == tt.denyRequest && result.Allowed {
					t.Fatalf("request %d was allowed, expected denied", requestNumber)
				}
			}
		})
	}
}

func TestRedisRateLimiterSharesCountersAcrossInstances(t *testing.T) {
	redisServer := miniredis.RunT(t)
	firstClient := redis.NewClient(&redis.Options{Addr: redisServer.Addr()})
	secondClient := redis.NewClient(&redis.Options{Addr: redisServer.Addr()})
	t.Cleanup(func() {
		_ = firstClient.Close()
		_ = secondClient.Close()
	})
	snapshot := &PolicySnapshot{
		RateLimitRules: []RateLimitPolicy{
			{
				ID:            1,
				ScopeType:     "api_key",
				ScopeValue:    "42",
				Algorithm:     "fixed_window",
				LimitCount:    1,
				WindowSeconds: 60,
			},
		},
	}
	provider := policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
		return snapshot, nil
	})
	first, _ := NewRedisRateLimiter(firstClient, provider)
	second, _ := NewRedisRateLimiter(secondClient, provider)

	firstResult, err := first.Allow(context.Background(), &KeyInfo{ID: 42}, "/orders")
	if err != nil || !firstResult.Allowed {
		t.Fatalf("first instance result=%#v err=%v", firstResult, err)
	}
	secondResult, err := second.Allow(context.Background(), &KeyInfo{ID: 42}, "/orders")
	if err != nil {
		t.Fatalf("second instance: %v", err)
	}
	if secondResult.Allowed {
		t.Fatal("second instance did not observe the distributed counter")
	}
}

func TestRedisRateLimiterRecoversAfterWindowOrRefill(t *testing.T) {
	tests := []string{"fixed_window", "sliding_window", "token_bucket"}
	for _, algorithm := range tests {
		algorithm := algorithm
		t.Run(algorithm, func(t *testing.T) {
			redisServer := miniredis.RunT(t)
			client := redis.NewClient(&redis.Options{Addr: redisServer.Addr()})
			t.Cleanup(func() { _ = client.Close() })
			snapshot := &PolicySnapshot{
				RateLimitRules: []RateLimitPolicy{
					{
						ID:            1,
						ScopeType:     "global",
						Algorithm:     algorithm,
						LimitCount:    1,
						WindowSeconds: 1,
					},
				},
			}
			limiter, _ := NewRedisRateLimiter(
				client,
				policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
					return snapshot, nil
				}),
			)
			now := time.Date(2026, time.July, 31, 0, 0, 0, 0, time.UTC)
			limiter.now = func() time.Time { return now }

			first, err := limiter.Allow(context.Background(), &KeyInfo{ID: 1}, "/")
			if err != nil || !first.Allowed {
				t.Fatalf("first result=%#v err=%v", first, err)
			}
			denied, err := limiter.Allow(context.Background(), &KeyInfo{ID: 1}, "/")
			if err != nil || denied.Allowed {
				t.Fatalf("denied result=%#v err=%v", denied, err)
			}

			now = now.Add(time.Second)
			redisServer.FastForward(time.Second)
			recovered, err := limiter.Allow(context.Background(), &KeyInfo{ID: 1}, "/")
			if err != nil || !recovered.Allowed {
				t.Fatalf("recovered result=%#v err=%v", recovered, err)
			}
		})
	}
}

func TestRateLimitRuleSelectionUsesMostSpecificScope(t *testing.T) {
	t.Parallel()
	rules := []RateLimitPolicy{
		{ID: 1, ScopeType: "global"},
		{ID: 2, ScopeType: "route", ScopeValue: "/orders"},
		{ID: 3, ScopeType: "api_key", ScopeValue: "42"},
	}

	if selected := selectRateLimitRule(rules, 42, "/orders"); selected == nil || selected.ID != 3 {
		t.Fatalf("selected rule = %#v, want API-key rule", selected)
	}
	if selected := selectRateLimitRule(rules, 7, "/orders"); selected == nil || selected.ID != 2 {
		t.Fatalf("selected rule = %#v, want route rule", selected)
	}
	if selected := selectRateLimitRule(rules, 7, "/other"); selected == nil || selected.ID != 1 {
		t.Fatalf("selected rule = %#v, want global rule", selected)
	}
}

func TestRedisRateLimiterAllowsWhenNoRuleMatches(t *testing.T) {
	redisServer := miniredis.RunT(t)
	client := redis.NewClient(&redis.Options{Addr: redisServer.Addr()})
	t.Cleanup(func() { _ = client.Close() })
	limiter, _ := NewRedisRateLimiter(
		client,
		policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
			return &PolicySnapshot{}, nil
		}),
	)

	result, err := limiter.Allow(context.Background(), &KeyInfo{ID: 1}, "/orders")
	if err != nil {
		t.Fatalf("allow request: %v", err)
	}
	if !result.Allowed || result.Limit != 0 {
		t.Fatalf("unexpected result: %#v", result)
	}
}

func int64Pointer(value int64) *int64 {
	return &value
}
