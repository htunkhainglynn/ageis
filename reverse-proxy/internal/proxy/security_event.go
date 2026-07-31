package proxy

type SecurityEvent struct {
	EventType  string `json:"event_type"`
	SourceIP   string `json:"source_ip"`
	APIKeyID   *int64 `json:"api_key_id"`
	RuleID     *int64 `json:"rule_id"`
	Method     string `json:"method"`
	Path       string `json:"path"`
	StatusCode int    `json:"status_code"`
}

type EventReporter interface {
	Report(event SecurityEvent)
}
