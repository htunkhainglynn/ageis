package proxy

import "errors"

var (
	ErrKeyNotFound          = errors.New("API key not found")
	ErrKeyRevoked           = errors.New("API key revoked")
	ErrKeyExpired           = errors.New("API key expired")
	ErrValidatorUnavailable = errors.New("key validator unavailable")
)
