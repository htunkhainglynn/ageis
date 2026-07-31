package controlplane

import (
	"context"
	"crypto/sha256"
	"errors"
	"sync"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type Validator interface {
	ValidateKey(ctx context.Context, key string) (*proxycore.KeyInfo, error)
}

type cacheEntry struct {
	keyInfo   *proxycore.KeyInfo
	err       error
	expiresAt time.Time
}

type CachedValidator struct {
	next        Validator
	positiveTTL time.Duration
	negativeTTL time.Duration
	now         func() time.Time
	mu          sync.RWMutex
	entries     map[[sha256.Size]byte]cacheEntry
}

func NewCachedValidator(next Validator, positiveTTL, negativeTTL time.Duration) (*CachedValidator, error) {
	if next == nil {
		return nil, errors.New("validator is required")
	}
	if positiveTTL <= 0 || negativeTTL <= 0 {
		return nil, errors.New("cache TTL values must be greater than zero")
	}
	return &CachedValidator{
		next:        next,
		positiveTTL: positiveTTL,
		negativeTTL: negativeTTL,
		now:         time.Now,
		entries:     make(map[[sha256.Size]byte]cacheEntry),
	}, nil
}

func (c *CachedValidator) ValidateKey(ctx context.Context, key string) (*proxycore.KeyInfo, error) {
	cacheKey := sha256.Sum256([]byte(key))
	now := c.now()

	c.mu.RLock()
	entry, found := c.entries[cacheKey]
	c.mu.RUnlock()
	if found && now.Before(entry.expiresAt) {
		return cloneKeyInfo(entry.keyInfo), entry.err
	}

	keyInfo, err := c.next.ValidateKey(ctx, key)
	if err != nil && !isCacheableError(err) {
		return nil, err
	}

	ttl := c.positiveTTL
	if err != nil {
		ttl = c.negativeTTL
	}
	c.mu.Lock()
	c.entries[cacheKey] = cacheEntry{
		keyInfo:   cloneKeyInfo(keyInfo),
		err:       err,
		expiresAt: now.Add(ttl),
	}
	c.mu.Unlock()

	return cloneKeyInfo(keyInfo), err
}

func isCacheableError(err error) bool {
	return errors.Is(err, proxycore.ErrKeyNotFound) ||
		errors.Is(err, proxycore.ErrKeyRevoked) ||
		errors.Is(err, proxycore.ErrKeyExpired)
}

func cloneKeyInfo(value *proxycore.KeyInfo) *proxycore.KeyInfo {
	if value == nil {
		return nil
	}
	copyValue := *value
	copyValue.Scopes = append([]string(nil), value.Scopes...)
	return &copyValue
}
