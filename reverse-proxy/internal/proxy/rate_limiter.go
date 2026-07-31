package proxy

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"strconv"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

var fixedWindowScript = redis.NewScript(`
local current = redis.call("INCR", KEYS[1])
if current == 1 then
  redis.call("PEXPIRE", KEYS[1], ARGV[2])
end
local ttl = redis.call("PTTL", KEYS[1])
local allowed = 0
if current <= tonumber(ARGV[1]) then
  allowed = 1
end
local remaining = math.max(0, tonumber(ARGV[1]) - current)
return {allowed, remaining, math.max(0, ttl)}
`)

var slidingWindowScript = redis.NewScript(`
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call("ZREMRANGEBYSCORE", KEYS[1], "-inf", now - window)
local current = redis.call("ZCARD", KEYS[1])
if current >= limit then
  local oldest = redis.call("ZRANGE", KEYS[1], 0, 0, "WITHSCORES")
  local retry = window
  if #oldest == 2 then
    retry = math.max(0, window - (now - tonumber(oldest[2])))
  end
  return {0, 0, retry}
end
redis.call("ZADD", KEYS[1], now, ARGV[4])
redis.call("PEXPIRE", KEYS[1], window)
return {1, limit - current - 1, 0}
`)

var tokenBucketScript = redis.NewScript(`
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_per_ms = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local tokens = tonumber(redis.call("HGET", KEYS[1], "tokens"))
local last = tonumber(redis.call("HGET", KEYS[1], "last"))
if tokens == nil or last == nil then
  tokens = capacity
  last = now
end
tokens = math.min(capacity, tokens + math.max(0, now - last) * refill_per_ms)
local allowed = 0
local retry = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
else
  retry = math.ceil((1 - tokens) / refill_per_ms)
end
redis.call("HSET", KEYS[1], "tokens", tokens, "last", now)
redis.call("PEXPIRE", KEYS[1], ttl)
return {allowed, math.floor(tokens), retry}
`)

type RateLimitResult struct {
	Allowed    bool
	Limit      int64
	Remaining  int64
	RetryAfter time.Duration
}

type RateLimiter interface {
	Allow(
		ctx context.Context,
		keyInfo *KeyInfo,
		path string,
	) (RateLimitResult, error)
}

type RedisRateLimiter struct {
	client   redis.UniversalClient
	policies PolicyProvider
	now      func() time.Time
	sequence atomic.Uint64
}

func NewRedisRateLimiter(
	client redis.UniversalClient,
	policies PolicyProvider,
) (*RedisRateLimiter, error) {
	if client == nil {
		return nil, errors.New("Redis client is required")
	}
	if policies == nil {
		return nil, errors.New("policy provider is required")
	}
	return &RedisRateLimiter{
		client:   client,
		policies: policies,
		now:      time.Now,
	}, nil
}

func (r *RedisRateLimiter) Allow(
	ctx context.Context,
	keyInfo *KeyInfo,
	path string,
) (RateLimitResult, error) {
	if keyInfo == nil {
		return RateLimitResult{}, errors.New("API key metadata is required")
	}
	snapshot, err := r.policies.GetPolicy(ctx)
	if err != nil || snapshot == nil {
		return RateLimitResult{}, ErrPolicyUnavailable
	}

	rule := selectRateLimitRule(snapshot.RateLimitRules, keyInfo.ID, path)
	if rule == nil {
		return RateLimitResult{Allowed: true}, nil
	}
	if rule.LimitCount <= 0 || rule.WindowSeconds <= 0 {
		return RateLimitResult{}, fmt.Errorf(
			"%w: rate-limit rule %d has invalid limits",
			ErrPolicyUnavailable,
			rule.ID,
		)
	}

	bucket := rateLimitBucket(*rule, keyInfo.ID, path)
	digest := sha256.Sum256([]byte(bucket))
	redisKey := fmt.Sprintf(
		"aegis:rate:%s:%d:%s",
		rule.Algorithm,
		rule.ID,
		hex.EncodeToString(digest[:]),
	)
	now := r.now()

	var values []any
	switch rule.Algorithm {
	case "fixed_window":
		values, err = fixedWindowScript.Run(
			ctx,
			r.client,
			[]string{redisKey},
			rule.LimitCount,
			rule.WindowSeconds*1000,
		).Slice()
	case "sliding_window":
		member := strconv.FormatInt(now.UnixNano(), 10) + "-" +
			strconv.FormatUint(r.sequence.Add(1), 10)
		values, err = slidingWindowScript.Run(
			ctx,
			r.client,
			[]string{redisKey},
			now.UnixMilli(),
			rule.WindowSeconds*1000,
			rule.LimitCount,
			member,
		).Slice()
	case "token_bucket":
		capacity := rule.LimitCount
		if rule.BurstAllowance != nil {
			capacity += *rule.BurstAllowance
		}
		refillPerMillisecond := float64(rule.LimitCount) /
			float64(rule.WindowSeconds*1000)
		values, err = tokenBucketScript.Run(
			ctx,
			r.client,
			[]string{redisKey},
			now.UnixMilli(),
			capacity,
			refillPerMillisecond,
			rule.WindowSeconds*2000,
		).Slice()
	default:
		return RateLimitResult{}, fmt.Errorf(
			"%w: unsupported rate-limit algorithm %q",
			ErrPolicyUnavailable,
			rule.Algorithm,
		)
	}
	if err != nil {
		return RateLimitResult{}, fmt.Errorf("running Redis rate limiter: %w", err)
	}
	if len(values) != 3 {
		return RateLimitResult{}, errors.New("Redis rate limiter returned an invalid result")
	}

	allowed, err := redisInteger(values[0])
	if err != nil {
		return RateLimitResult{}, err
	}
	remaining, err := redisInteger(values[1])
	if err != nil {
		return RateLimitResult{}, err
	}
	retryMilliseconds, err := redisInteger(values[2])
	if err != nil {
		return RateLimitResult{}, err
	}
	return RateLimitResult{
		Allowed:    allowed == 1,
		Limit:      rule.LimitCount,
		Remaining:  remaining,
		RetryAfter: time.Duration(retryMilliseconds) * time.Millisecond,
	}, nil
}

func selectRateLimitRule(
	rules []RateLimitPolicy,
	apiKeyID int64,
	path string,
) *RateLimitPolicy {
	var routeRule *RateLimitPolicy
	var globalRule *RateLimitPolicy
	apiKeyValue := strconv.FormatInt(apiKeyID, 10)

	for index := range rules {
		rule := &rules[index]
		switch {
		case rule.ScopeType == "api_key" && rule.ScopeValue == apiKeyValue:
			return rule
		case rule.ScopeType == "route" && rule.ScopeValue == path:
			routeRule = rule
		case rule.ScopeType == "global":
			globalRule = rule
		}
	}
	if routeRule != nil {
		return routeRule
	}
	return globalRule
}

func rateLimitBucket(rule RateLimitPolicy, apiKeyID int64, path string) string {
	switch rule.ScopeType {
	case "api_key":
		return "api_key:" + strconv.FormatInt(apiKeyID, 10)
	case "route":
		return "route:" + path
	default:
		return "global"
	}
}

func redisInteger(value any) (int64, error) {
	switch typed := value.(type) {
	case int64:
		return typed, nil
	case string:
		parsed, err := strconv.ParseInt(typed, 10, 64)
		if err != nil {
			return 0, fmt.Errorf("parsing Redis integer: %w", err)
		}
		return parsed, nil
	case float64:
		return int64(math.Round(typed)), nil
	default:
		return 0, fmt.Errorf("unexpected Redis integer type %T", value)
	}
}
