package proxy

import (
	"context"
	"time"
)

type JWTPolicy struct {
	ID              int64  `json:"id"`
	Algorithm       string `json:"algorithm"`
	VerificationKey string `json:"verification_key"`
	Issuer          string `json:"issuer"`
	Audience        string `json:"audience"`
}

type RateLimitPolicy struct {
	ID             int64  `json:"id"`
	ScopeType      string `json:"scope_type"`
	ScopeValue     string `json:"scope_value"`
	Algorithm      string `json:"algorithm"`
	LimitCount     int64  `json:"limit_count"`
	WindowSeconds  int64  `json:"window_seconds"`
	BurstAllowance *int64 `json:"burst_allowance"`
}

type PolicySnapshot struct {
	GeneratedAt    time.Time         `json:"generated_at"`
	JWT            *JWTPolicy        `json:"jwt"`
	RateLimitRules []RateLimitPolicy `json:"rate_limit_rules"`
}

type PolicyProvider interface {
	GetPolicy(ctx context.Context) (*PolicySnapshot, error)
}
