package proxy

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type policyProviderFunc func(context.Context) (*PolicySnapshot, error)

func (f policyProviderFunc) GetPolicy(ctx context.Context) (*PolicySnapshot, error) {
	return f(ctx)
}

func TestPolicyJWTValidatorHS256(t *testing.T) {
	t.Parallel()
	now := time.Now()
	policy := &JWTPolicy{
		ID:              1,
		Algorithm:       "HS256",
		VerificationKey: "test-shared-secret-with-sufficient-length",
		Issuer:          "aegis",
		Audience:        "orders-api",
	}
	validator, _ := NewPolicyJWTValidator(
		policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
			return &PolicySnapshot{JWT: policy}, nil
		}),
	)

	validToken := signedToken(
		t,
		jwt.SigningMethodHS256,
		[]byte(policy.VerificationKey),
		jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(now.Add(time.Hour)),
			Issuer:    "aegis",
			Audience:  jwt.ClaimStrings{"orders-api"},
		},
	)
	expiredToken := signedToken(
		t,
		jwt.SigningMethodHS256,
		[]byte(policy.VerificationKey),
		jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(now.Add(-time.Minute)),
			Issuer:    "aegis",
			Audience:  jwt.ClaimStrings{"orders-api"},
		},
	)
	wrongIssuer := signedToken(
		t,
		jwt.SigningMethodHS256,
		[]byte(policy.VerificationKey),
		jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(now.Add(time.Hour)),
			Issuer:    "other",
			Audience:  jwt.ClaimStrings{"orders-api"},
		},
	)
	missingExpiration := signedToken(
		t,
		jwt.SigningMethodHS256,
		[]byte(policy.VerificationKey),
		jwt.RegisteredClaims{
			Issuer:   "aegis",
			Audience: jwt.ClaimStrings{"orders-api"},
		},
	)

	tests := []struct {
		name      string
		token     string
		wantError error
	}{
		{name: "valid token", token: validToken},
		{name: "expired token", token: expiredToken, wantError: ErrJWTExpired},
		{name: "wrong issuer", token: wrongIssuer, wantError: ErrJWTInvalid},
		{name: "missing expiration", token: missingExpiration, wantError: ErrJWTInvalid},
		{name: "malformed token", token: "not-a-jwt", wantError: ErrJWTInvalid},
		{name: "missing token", wantError: ErrJWTMissing},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			err := validator.ValidateJWT(context.Background(), tt.token)
			if !errors.Is(err, tt.wantError) {
				t.Fatalf("error = %v, want %v", err, tt.wantError)
			}
		})
	}
}

func TestPolicyJWTValidatorAsymmetricAlgorithms(t *testing.T) {
	t.Parallel()
	rsaPrivate, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generate RSA key: %v", err)
	}
	rsaPublicPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "PUBLIC KEY",
		Bytes: x509.MarshalPKCS1PublicKey(&rsaPrivate.PublicKey),
	})

	ecPrivate, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatalf("generate EC key: %v", err)
	}
	ecPublicDER, err := x509.MarshalPKIXPublicKey(&ecPrivate.PublicKey)
	if err != nil {
		t.Fatalf("marshal EC public key: %v", err)
	}
	ecPublicPEM := pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: ecPublicDER})

	tests := []struct {
		name       string
		algorithm  string
		method     jwt.SigningMethod
		signingKey any
		publicKey  string
	}{
		{
			name:       "RS256",
			algorithm:  "RS256",
			method:     jwt.SigningMethodRS256,
			signingKey: rsaPrivate,
			publicKey:  string(rsaPublicPEM),
		},
		{
			name:       "ES256",
			algorithm:  "ES256",
			method:     jwt.SigningMethodES256,
			signingKey: ecPrivate,
			publicKey:  string(ecPublicPEM),
		},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			policy := &JWTPolicy{
				ID:              1,
				Algorithm:       tt.algorithm,
				VerificationKey: tt.publicKey,
			}
			validator, _ := NewPolicyJWTValidator(
				policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
					return &PolicySnapshot{JWT: policy}, nil
				}),
			)
			token := signedToken(
				t,
				tt.method,
				tt.signingKey,
				jwt.RegisteredClaims{ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour))},
			)
			if err := validator.ValidateJWT(context.Background(), token); err != nil {
				t.Fatalf("validate token: %v", err)
			}
		})
	}
}

func TestPolicyJWTValidatorFailsClosedWithoutPolicy(t *testing.T) {
	t.Parallel()
	validator, _ := NewPolicyJWTValidator(
		policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
			return nil, ErrPolicyUnavailable
		}),
	)

	if err := validator.ValidateJWT(context.Background(), "token"); !errors.Is(err, ErrPolicyUnavailable) {
		t.Fatalf("error = %v, want policy unavailable", err)
	}
}

func TestPolicyJWTValidatorRejectsAlgorithmSubstitution(t *testing.T) {
	t.Parallel()
	rsaPrivate, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generate RSA key: %v", err)
	}
	publicDER, err := x509.MarshalPKIXPublicKey(&rsaPrivate.PublicKey)
	if err != nil {
		t.Fatalf("marshal RSA public key: %v", err)
	}
	publicPEM := pem.EncodeToMemory(&pem.Block{Type: "PUBLIC KEY", Bytes: publicDER})
	policy := &JWTPolicy{
		ID:              1,
		Algorithm:       "RS256",
		VerificationKey: string(publicPEM),
	}
	validator, _ := NewPolicyJWTValidator(
		policyProviderFunc(func(context.Context) (*PolicySnapshot, error) {
			return &PolicySnapshot{JWT: policy}, nil
		}),
	)
	forgedToken := signedToken(
		t,
		jwt.SigningMethodHS256,
		publicPEM,
		jwt.RegisteredClaims{ExpiresAt: jwt.NewNumericDate(time.Now().Add(time.Hour))},
	)

	if err := validator.ValidateJWT(context.Background(), forgedToken); !errors.Is(err, ErrJWTInvalid) {
		t.Fatalf("error = %v, want JWT invalid", err)
	}
}

func signedToken(
	t *testing.T,
	method jwt.SigningMethod,
	key any,
	claims jwt.RegisteredClaims,
) string {
	t.Helper()
	rawToken, err := jwt.NewWithClaims(method, claims).SignedString(key)
	if err != nil {
		t.Fatalf("sign token: %v", err)
	}
	return rawToken
}
