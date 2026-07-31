package proxy

import "errors"

var (
	ErrKeyNotFound          = errors.New("API key not found")
	ErrKeyRevoked           = errors.New("API key revoked")
	ErrKeyExpired           = errors.New("API key expired")
	ErrValidatorUnavailable = errors.New("key validator unavailable")
	ErrPolicyUnavailable    = errors.New("proxy policy unavailable")
	ErrJWTMissing           = errors.New("JWT missing")
	ErrJWTInvalid           = errors.New("JWT invalid")
	ErrJWTExpired           = errors.New("JWT expired")
	ErrClientIPInvalid      = errors.New("client IP address invalid")
)
