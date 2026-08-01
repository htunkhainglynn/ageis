package controlplane

import (
	"context"
	"errors"
	"sync"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type PolicySource interface {
	GetPolicy(ctx context.Context) (*proxycore.PolicySnapshot, error)
}

type CachedPolicyProvider struct {
	source    PolicySource
	ttl       time.Duration
	now       func() time.Time
	mu        sync.Mutex
	snapshot  *proxycore.PolicySnapshot
	expiresAt time.Time
}

func NewCachedPolicyProvider(source PolicySource, ttl time.Duration) (*CachedPolicyProvider, error) {
	if source == nil {
		return nil, errors.New("policy source is required")
	}
	if ttl <= 0 {
		return nil, errors.New("policy cache TTL must be greater than zero")
	}
	return &CachedPolicyProvider{
		source: source,
		ttl:    ttl,
		now:    time.Now,
	}, nil
}

func (c *CachedPolicyProvider) GetPolicy(ctx context.Context) (*proxycore.PolicySnapshot, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := c.now()
	if c.snapshot != nil && now.Before(c.expiresAt) {
		return clonePolicySnapshot(c.snapshot), nil
	}

	snapshot, err := c.source.GetPolicy(ctx)
	if err != nil {
		if c.snapshot != nil {
			return clonePolicySnapshot(c.snapshot), nil
		}
		return nil, err
	}
	if snapshot == nil {
		if c.snapshot != nil {
			return clonePolicySnapshot(c.snapshot), nil
		}
		return nil, proxycore.ErrPolicyUnavailable
	}

	c.snapshot = clonePolicySnapshot(snapshot)
	c.expiresAt = now.Add(c.ttl)
	return clonePolicySnapshot(c.snapshot), nil
}

func clonePolicySnapshot(value *proxycore.PolicySnapshot) *proxycore.PolicySnapshot {
	if value == nil {
		return nil
	}
	copyValue := *value
	if value.JWT != nil {
		jwtCopy := *value.JWT
		copyValue.JWT = &jwtCopy
	}
	copyValue.RateLimitRules = append([]proxycore.RateLimitPolicy(nil), value.RateLimitRules...)
	copyValue.BlockedIPAddresses = append([]string(nil), value.BlockedIPAddresses...)
	copyValue.ThreatRules = append([]proxycore.ThreatPolicy(nil), value.ThreatRules...)
	copyValue.RoutePermissions = append([]proxycore.RoutePermissionPolicy(nil), value.RoutePermissions...)
	for index := range copyValue.RateLimitRules {
		if value.RateLimitRules[index].BurstAllowance != nil {
			burst := *value.RateLimitRules[index].BurstAllowance
			copyValue.RateLimitRules[index].BurstAllowance = &burst
		}
	}
	return &copyValue
}
