package controlplane

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

type AsyncEventReporter struct {
	httpClient    *http.Client
	endpoint      *url.URL
	internalToken string
	timeout       time.Duration
	logger        *slog.Logger
	queue         chan proxycore.SecurityEvent
	done          chan struct{}
	closeOnce     sync.Once
}

func NewAsyncEventReporter(
	httpClient *http.Client,
	baseURL *url.URL,
	eventPath string,
	internalToken string,
	timeout time.Duration,
	queueSize int,
	logger *slog.Logger,
) (*AsyncEventReporter, error) {
	if httpClient == nil || baseURL == nil || logger == nil {
		return nil, fmt.Errorf("HTTP client, Control Plane URL, and logger are required")
	}
	if !strings.HasPrefix(eventPath, "/") || strings.TrimSpace(internalToken) == "" {
		return nil, fmt.Errorf("valid event path and internal token are required")
	}
	if timeout <= 0 || queueSize <= 0 {
		return nil, fmt.Errorf("event timeout and queue size must be positive")
	}
	reporter := &AsyncEventReporter{
		httpClient: httpClient, endpoint: baseURL.ResolveReference(&url.URL{Path: eventPath}),
		internalToken: internalToken, timeout: timeout, logger: logger,
		queue: make(chan proxycore.SecurityEvent, queueSize), done: make(chan struct{}),
	}
	go reporter.run()
	return reporter, nil
}

func (r *AsyncEventReporter) Report(event proxycore.SecurityEvent) {
	select {
	case r.queue <- event:
	default:
		r.logger.Warn("security event queue full; event dropped", "event_type", event.EventType)
	}
}

func (r *AsyncEventReporter) Close() {
	r.closeOnce.Do(func() {
		close(r.queue)
		<-r.done
	})
}

func (r *AsyncEventReporter) run() {
	defer close(r.done)
	for event := range r.queue {
		if err := r.send(event); err != nil {
			r.logger.Warn("security event delivery failed", "event_type", event.EventType, "error", err)
		}
	}
}

func (r *AsyncEventReporter) send(event proxycore.SecurityEvent) error {
	body, err := json.Marshal(event)
	if err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(context.Background(), r.timeout)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, r.endpoint.String(), bytes.NewReader(body))
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Aegis-Internal-Token", r.internalToken)
	response, err := r.httpClient.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, response.Body)
	if response.StatusCode != http.StatusCreated {
		return fmt.Errorf("Control Plane returned HTTP %d", response.StatusCode)
	}
	return nil
}
