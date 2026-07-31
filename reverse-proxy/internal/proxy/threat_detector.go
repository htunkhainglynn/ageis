package proxy

import (
	"context"
	"fmt"
	"net/http"
	"regexp"
)

type ThreatMatch struct {
	RuleID   int64
	RuleName string
	Severity string
}

type ThreatDetector interface {
	Detect(ctx context.Context, request *http.Request) (*ThreatMatch, error)
}

type PolicyThreatDetector struct {
	policyProvider PolicyProvider
}

func NewPolicyThreatDetector(provider PolicyProvider) (*PolicyThreatDetector, error) {
	if provider == nil {
		return nil, fmt.Errorf("policy provider is required")
	}
	return &PolicyThreatDetector{policyProvider: provider}, nil
}

func (d *PolicyThreatDetector) Detect(
	ctx context.Context,
	request *http.Request,
) (*ThreatMatch, error) {
	snapshot, err := d.policyProvider.GetPolicy(ctx)
	if err != nil || snapshot == nil {
		return nil, fmt.Errorf("%w: loading threat policy", ErrPolicyUnavailable)
	}
	target := request.Method + " " + request.URL.RequestURI()
	for _, rule := range snapshot.ThreatRules {
		pattern, compileErr := regexp.Compile(rule.Pattern)
		if compileErr != nil {
			return nil, fmt.Errorf("%w: invalid threat pattern", ErrPolicyUnavailable)
		}
		if pattern.MatchString(target) {
			return &ThreatMatch{
				RuleID: rule.ID, RuleName: rule.Name, Severity: rule.Severity,
			}, nil
		}
	}
	return nil, nil
}
