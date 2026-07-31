package controlplane

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"strings"
	"time"

	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/policypb"
	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

type GRPCPolicySubscriber struct {
	address       string
	internalToken string
	reconnect     time.Duration
	provider      *StreamingPolicyProvider
	logger        *slog.Logger
}

func NewGRPCPolicySubscriber(
	address string,
	internalToken string,
	reconnect time.Duration,
	provider *StreamingPolicyProvider,
	logger *slog.Logger,
) (*GRPCPolicySubscriber, error) {
	if strings.TrimSpace(address) == "" || strings.TrimSpace(internalToken) == "" {
		return nil, errors.New("gRPC policy address and internal token are required")
	}
	if reconnect <= 0 || provider == nil || logger == nil {
		return nil, errors.New("valid reconnect delay, provider, and logger are required")
	}
	return &GRPCPolicySubscriber{
		address: address, internalToken: internalToken, reconnect: reconnect,
		provider: provider, logger: logger,
	}, nil
}

func (s *GRPCPolicySubscriber) Run(ctx context.Context) {
	for ctx.Err() == nil {
		if err := s.subscribe(ctx); err != nil && ctx.Err() == nil {
			s.logger.Warn("gRPC policy stream disconnected; cached/REST policy retained", "error", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(s.reconnect):
		}
	}
}

func (s *GRPCPolicySubscriber) subscribe(ctx context.Context) error {
	connection, err := grpc.NewClient(
		s.address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		return err
	}
	defer connection.Close()

	streamCtx := metadata.AppendToOutgoingContext(
		ctx, "x-aegis-internal-token", s.internalToken,
	)
	stream, err := policypb.NewPolicySyncClient(connection).Subscribe(
		streamCtx, &policypb.SubscribeRequest{},
	)
	if err != nil {
		return err
	}
	for {
		message, receiveErr := stream.Recv()
		if receiveErr != nil {
			return receiveErr
		}
		var snapshot proxycore.PolicySnapshot
		if decodeErr := json.Unmarshal(message.GetJsonPayload(), &snapshot); decodeErr != nil {
			s.logger.Warn("invalid gRPC policy snapshot ignored", "error", decodeErr)
			continue
		}
		s.provider.Update(&snapshot)
	}
}
