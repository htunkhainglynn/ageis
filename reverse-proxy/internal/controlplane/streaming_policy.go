package controlplane

import (
	"context"
	"sync"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type StreamingPolicyProvider struct {
	fallback proxycore.PolicyProvider
	mu       sync.RWMutex
	snapshot *proxycore.PolicySnapshot
}

func NewStreamingPolicyProvider(fallback proxycore.PolicyProvider) *StreamingPolicyProvider {
	return &StreamingPolicyProvider{fallback: fallback}
}

func (p *StreamingPolicyProvider) Update(snapshot *proxycore.PolicySnapshot) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.snapshot = clonePolicySnapshot(snapshot)
}

func (p *StreamingPolicyProvider) GetPolicy(
	ctx context.Context,
) (*proxycore.PolicySnapshot, error) {
	p.mu.RLock()
	snapshot := clonePolicySnapshot(p.snapshot)
	p.mu.RUnlock()
	if snapshot != nil {
		return snapshot, nil
	}
	return p.fallback.GetPolicy(ctx)
}
