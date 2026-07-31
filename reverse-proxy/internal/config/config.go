package config

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultListenAddr      = ":8080"
	defaultValidationPath  = "/api/v1/api-keys/validate"
	defaultPolicyPath      = "/api/v1/internal/proxy-config"
	defaultAPIKeyHeader    = "X-API-Key"
	defaultValidationTTL   = 30 * time.Second
	defaultNegativeTTL     = 5 * time.Second
	defaultPolicyTTL       = 30 * time.Second
	defaultValidationTime  = 2 * time.Second
	defaultShutdownTimeout = 10 * time.Second
	defaultRedisAddr       = "localhost:6379"
)

type Config struct {
	ListenAddr               string
	BackendURL               *url.URL
	ControlPlaneURL          *url.URL
	ControlPlaneValidatePath string
	ControlPlanePolicyPath   string
	InternalAPIToken         string
	APIKeyHeader             string
	ValidationTimeout        time.Duration
	ValidationCacheTTL       time.Duration
	ValidationNegativeTTL    time.Duration
	PolicyCacheTTL           time.Duration
	ShutdownTimeout          time.Duration
	RedisAddr                string
	RedisPassword            string
	RedisDB                  int
}

func Load() (Config, error) {
	backendURL, err := requiredURL("BACKEND_URL")
	if err != nil {
		return Config{}, err
	}
	controlPlaneURL, err := requiredURL("CONTROL_PLANE_URL")
	if err != nil {
		return Config{}, err
	}
	internalAPIToken, err := requiredString("INTERNAL_API_TOKEN")
	if err != nil {
		return Config{}, err
	}

	validationTimeout, err := durationFromEnv("VALIDATION_TIMEOUT", defaultValidationTime)
	if err != nil {
		return Config{}, err
	}
	cacheTTL, err := durationFromEnv("VALIDATION_CACHE_TTL", defaultValidationTTL)
	if err != nil {
		return Config{}, err
	}
	negativeTTL, err := durationFromEnv("VALIDATION_NEGATIVE_CACHE_TTL", defaultNegativeTTL)
	if err != nil {
		return Config{}, err
	}
	policyCacheTTL, err := durationFromEnv("POLICY_CACHE_TTL", defaultPolicyTTL)
	if err != nil {
		return Config{}, err
	}
	shutdownTimeout, err := durationFromEnv("SHUTDOWN_TIMEOUT", defaultShutdownTimeout)
	if err != nil {
		return Config{}, err
	}
	redisDB, err := integerFromEnv("REDIS_DB", 0)
	if err != nil {
		return Config{}, err
	}

	validationPath := envOrDefault("CONTROL_PLANE_VALIDATE_PATH", defaultValidationPath)
	if !strings.HasPrefix(validationPath, "/") {
		return Config{}, errors.New("CONTROL_PLANE_VALIDATE_PATH must start with /")
	}
	policyPath := envOrDefault("CONTROL_PLANE_POLICY_PATH", defaultPolicyPath)
	if !strings.HasPrefix(policyPath, "/") {
		return Config{}, errors.New("CONTROL_PLANE_POLICY_PATH must start with /")
	}

	return Config{
		ListenAddr:               envOrDefault("LISTEN_ADDR", defaultListenAddr),
		BackendURL:               backendURL,
		ControlPlaneURL:          controlPlaneURL,
		ControlPlaneValidatePath: validationPath,
		ControlPlanePolicyPath:   policyPath,
		InternalAPIToken:         internalAPIToken,
		APIKeyHeader:             envOrDefault("API_KEY_HEADER", defaultAPIKeyHeader),
		ValidationTimeout:        validationTimeout,
		ValidationCacheTTL:       cacheTTL,
		ValidationNegativeTTL:    negativeTTL,
		PolicyCacheTTL:           policyCacheTTL,
		ShutdownTimeout:          shutdownTimeout,
		RedisAddr:                envOrDefault("REDIS_ADDR", defaultRedisAddr),
		RedisPassword:            os.Getenv("REDIS_PASSWORD"),
		RedisDB:                  redisDB,
	}, nil
}

func requiredString(name string) (string, error) {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return "", fmt.Errorf("%s is required", name)
	}
	return value, nil
}

func requiredURL(name string) (*url.URL, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return nil, fmt.Errorf("%s is required", name)
	}
	parsed, err := url.Parse(raw)
	if err != nil {
		return nil, fmt.Errorf("parsing %s: %w", name, err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return nil, fmt.Errorf("%s must use http or https", name)
	}
	if parsed.Host == "" {
		return nil, fmt.Errorf("%s must include a host", name)
	}
	return parsed, nil
}

func durationFromEnv(name string, fallback time.Duration) (time.Duration, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("parsing %s: %w", name, err)
	}
	if value <= 0 {
		return 0, fmt.Errorf("%s must be greater than zero", name)
	}
	return value, nil
}

func integerFromEnv(name string, fallback int) (int, error) {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < 0 {
		return 0, fmt.Errorf("%s must be a non-negative integer", name)
	}
	return value, nil
}

func envOrDefault(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}
