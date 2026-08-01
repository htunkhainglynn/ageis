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

type ThreatPolicy struct {
	ID       int64  `json:"id"`
	Name     string `json:"name"`
	Pattern  string `json:"pattern"`
	Severity string `json:"severity"`
}

type RoutePermissionPolicy struct {
	ID            int64  `json:"id"`
	Method        string `json:"method"`
	PathPattern   string `json:"path_pattern"`
	RequiredScope string `json:"required_scope"`
}

type PolicySnapshot struct {
	GeneratedAt        time.Time               `json:"generated_at"`
	JWT                *JWTPolicy              `json:"jwt"`
	RateLimitRules     []RateLimitPolicy       `json:"rate_limit_rules"`
	BlockedIPAddresses []string                `json:"blocked_ip_addresses"`
	ThreatRules        []ThreatPolicy          `json:"threat_rules"`
	RoutePermissions   []RoutePermissionPolicy `json:"route_permissions"`
}

type PolicyProvider interface {
	GetPolicy(ctx context.Context) (*PolicySnapshot, error)
}
