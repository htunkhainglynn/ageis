package proxy

import (
	"context"
	"crypto/ecdsa"
	"crypto/rsa"
	"errors"
	"fmt"
	"strings"

	"github.com/golang-jwt/jwt/v5"
)

type PolicyJWTValidator struct {
	policies PolicyProvider
}

func NewPolicyJWTValidator(policies PolicyProvider) (*PolicyJWTValidator, error) {
	if policies == nil {
		return nil, errors.New("policy provider is required")
	}
	return &PolicyJWTValidator{policies: policies}, nil
}

func (v *PolicyJWTValidator) ValidateJWT(ctx context.Context, rawToken string) error {
	if strings.TrimSpace(rawToken) == "" {
		return ErrJWTMissing
	}

	snapshot, err := v.policies.GetPolicy(ctx)
	if err != nil || snapshot == nil || snapshot.JWT == nil {
		return ErrPolicyUnavailable
	}
	policy := snapshot.JWT

	verificationKey, err := parseVerificationKey(policy)
	if err != nil {
		return fmt.Errorf("%w: %v", ErrPolicyUnavailable, err)
	}

	options := []jwt.ParserOption{
		jwt.WithValidMethods([]string{policy.Algorithm}),
		jwt.WithExpirationRequired(),
	}
	if policy.Issuer != "" {
		options = append(options, jwt.WithIssuer(policy.Issuer))
	}
	if policy.Audience != "" {
		options = append(options, jwt.WithAudience(policy.Audience))
	}

	token, err := jwt.Parse(
		rawToken,
		func(token *jwt.Token) (any, error) {
			if token.Method.Alg() != policy.Algorithm {
				return nil, fmt.Errorf("unexpected signing algorithm %q", token.Method.Alg())
			}
			return verificationKey, nil
		},
		options...,
	)
	if errors.Is(err, jwt.ErrTokenExpired) {
		return ErrJWTExpired
	}
	if err != nil || token == nil || !token.Valid {
		return ErrJWTInvalid
	}
	return nil
}

func parseVerificationKey(policy *JWTPolicy) (any, error) {
	switch policy.Algorithm {
	case "HS256":
		if policy.VerificationKey == "" {
			return nil, errors.New("HS256 verification key is empty")
		}
		return []byte(policy.VerificationKey), nil
	case "RS256":
		key, err := jwt.ParseRSAPublicKeyFromPEM([]byte(policy.VerificationKey))
		if err != nil {
			return nil, fmt.Errorf("parsing RS256 public key: %w", err)
		}
		return (*rsa.PublicKey)(key), nil
	case "ES256":
		key, err := jwt.ParseECPublicKeyFromPEM([]byte(policy.VerificationKey))
		if err != nil {
			return nil, fmt.Errorf("parsing ES256 public key: %w", err)
		}
		return (*ecdsa.PublicKey)(key), nil
	default:
		return nil, fmt.Errorf("unsupported JWT algorithm %q", policy.Algorithm)
	}
}
