package controlplane

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net"
	"testing"
	"time"

	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/policypb"
	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

type fallbackPolicyFunc func(context.Context) (*proxycore.PolicySnapshot, error)

func (f fallbackPolicyFunc) GetPolicy(ctx context.Context) (*proxycore.PolicySnapshot, error) {
	return f(ctx)
}

type testPolicyStreamServer struct {
	policypb.UnimplementedPolicySyncServer
	tokenReceived chan string
}

func (s *testPolicyStreamServer) Subscribe(
	_ *policypb.SubscribeRequest,
	stream grpc.ServerStreamingServer[policypb.PolicySnapshot],
) error {
	metadataValues, _ := metadata.FromIncomingContext(stream.Context())
	s.tokenReceived <- first(metadataValues.Get("x-aegis-internal-token"))
	payload, _ := json.Marshal(&proxycore.PolicySnapshot{
		BlockedIPAddresses: []string{"203.0.113.99"},
	})
	if err := stream.Send(&policypb.PolicySnapshot{JsonPayload: payload}); err != nil {
		return err
	}
	<-stream.Context().Done()
	return stream.Context().Err()
}

func first(values []string) string {
	if len(values) == 0 {
		return ""
	}
	return values[0]
}

func TestGRPCPolicySubscriberUpdatesStreamingProvider(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	grpcServer := grpc.NewServer()
	streamServer := &testPolicyStreamServer{tokenReceived: make(chan string, 1)}
	policypb.RegisterPolicySyncServer(grpcServer, streamServer)
	go func() { _ = grpcServer.Serve(listener) }()
	t.Cleanup(func() {
		grpcServer.Stop()
		_ = listener.Close()
	})

	fallback := fallbackPolicyFunc(func(context.Context) (*proxycore.PolicySnapshot, error) {
		return &proxycore.PolicySnapshot{BlockedIPAddresses: []string{"198.51.100.1"}}, nil
	})
	provider := NewStreamingPolicyProvider(fallback)
	subscriber, err := NewGRPCPolicySubscriber(
		listener.Addr().String(), "stream-token", 10*time.Millisecond, provider,
		slog.New(slog.NewTextHandler(io.Discard, nil)),
	)
	if err != nil {
		t.Fatalf("create subscriber: %v", err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		subscriber.Run(ctx)
		close(done)
	}()

	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		snapshot, getErr := provider.GetPolicy(context.Background())
		if getErr == nil && len(snapshot.BlockedIPAddresses) == 1 &&
			snapshot.BlockedIPAddresses[0] == "203.0.113.99" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	snapshot, _ := provider.GetPolicy(context.Background())
	if snapshot.BlockedIPAddresses[0] != "203.0.113.99" {
		t.Fatalf("streaming snapshot was not applied: %#v", snapshot)
	}
	if token := <-streamServer.tokenReceived; token != "stream-token" {
		t.Fatalf("metadata token = %q", token)
	}
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("subscriber did not stop with context")
	}
}

func TestStreamingPolicyProviderFallsBackBeforeFirstStreamUpdate(t *testing.T) {
	fallback := fallbackPolicyFunc(func(context.Context) (*proxycore.PolicySnapshot, error) {
		return &proxycore.PolicySnapshot{BlockedIPAddresses: []string{"198.51.100.1"}}, nil
	})
	provider := NewStreamingPolicyProvider(fallback)
	snapshot, err := provider.GetPolicy(context.Background())
	if err != nil || snapshot.BlockedIPAddresses[0] != "198.51.100.1" {
		t.Fatalf("fallback snapshot = %#v, error=%v", snapshot, err)
	}
}
