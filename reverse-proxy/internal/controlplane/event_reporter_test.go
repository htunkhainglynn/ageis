package controlplane

import (
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
	"time"

	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

func TestAsyncEventReporterDeliversSanitizedEventAndFlushes(t *testing.T) {
	t.Parallel()
	received := make(chan proxycore.SecurityEvent, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/internal/security-events" {
			t.Errorf("path = %s", r.URL.Path)
		}
		if r.Header.Get("X-Aegis-Internal-Token") != "internal-token" {
			t.Error("internal token missing")
		}
		var event proxycore.SecurityEvent
		if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
			t.Errorf("decode event: %v", err)
		}
		received <- event
		w.WriteHeader(http.StatusCreated)
	}))
	t.Cleanup(server.Close)
	baseURL, _ := url.Parse(server.URL)
	reporter, err := NewAsyncEventReporter(
		server.Client(), baseURL, "/api/v1/internal/security-events",
		"internal-token", time.Second, 10,
		slog.New(slog.NewTextHandler(io.Discard, nil)),
	)
	if err != nil {
		t.Fatalf("create reporter: %v", err)
	}
	reporter.Report(proxycore.SecurityEvent{
		EventType: "request_forwarded", SourceIP: "203.0.113.8",
		Method: "GET", Path: "/orders", StatusCode: 200,
	})
	reporter.Close()

	select {
	case event := <-received:
		if event.EventType != "request_forwarded" || event.Path != "/orders" {
			t.Fatalf("unexpected event: %#v", event)
		}
	default:
		t.Fatal("event was not delivered before close")
	}
}

func TestNewAsyncEventReporterValidation(t *testing.T) {
	t.Parallel()
	logger := slog.New(slog.NewTextHandler(io.Discard, nil))
	baseURL, _ := url.Parse("http://control-plane.example")
	if _, err := NewAsyncEventReporter(
		nil, baseURL, "/events", "token", time.Second, 1, logger,
	); err == nil {
		t.Fatal("expected missing HTTP client error")
	}
}
