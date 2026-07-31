package proxy

import (
	"context"
	"fmt"
	"net"
	"net/netip"
	"strings"
)

type IPBlocker interface {
	IsBlocked(ctx context.Context, remoteAddr string) (bool, error)
}

type PolicyIPBlocker struct {
	policyProvider PolicyProvider
}

func NewPolicyIPBlocker(policyProvider PolicyProvider) (*PolicyIPBlocker, error) {
	if policyProvider == nil {
		return nil, fmt.Errorf("policy provider is required")
	}
	return &PolicyIPBlocker{policyProvider: policyProvider}, nil
}

func (b *PolicyIPBlocker) IsBlocked(ctx context.Context, remoteAddr string) (bool, error) {
	clientIP, err := parseClientIP(remoteAddr)
	if err != nil {
		return false, err
	}

	snapshot, err := b.policyProvider.GetPolicy(ctx)
	if err != nil {
		return false, fmt.Errorf("%w: loading IP block policy: %v", ErrPolicyUnavailable, err)
	}
	if snapshot == nil {
		return false, ErrPolicyUnavailable
	}

	for _, rawBlockedIP := range snapshot.BlockedIPAddresses {
		blockedIP, parseErr := netip.ParseAddr(strings.TrimSpace(rawBlockedIP))
		if parseErr != nil {
			return false, fmt.Errorf(
				"%w: invalid blocked IP address in policy",
				ErrPolicyUnavailable,
			)
		}
		if clientIP == blockedIP.Unmap().WithZone("") {
			return true, nil
		}
	}
	return false, nil
}

func parseClientIP(remoteAddr string) (netip.Addr, error) {
	value := strings.TrimSpace(remoteAddr)
	if host, _, err := net.SplitHostPort(value); err == nil {
		value = host
	}
	value = strings.Trim(value, "[]")
	address, err := netip.ParseAddr(value)
	if err != nil {
		return netip.Addr{}, ErrClientIPInvalid
	}
	return address.Unmap().WithZone(""), nil
}
