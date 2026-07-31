package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/config"
	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/controlplane"
	"github.com/htunkhainglynn/aegis/reverse-proxy/internal/middleware"
	proxycore "github.com/htunkhainglynn/aegis/reverse-proxy/internal/proxy"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	cfg, err := config.Load()
	if err != nil {
		logger.Error("loading configuration failed", "error", err)
		os.Exit(1)
	}

	httpClient := &http.Client{
		Transport: &http.Transport{
			MaxIdleConns:          100,
			MaxIdleConnsPerHost:   20,
			MaxConnsPerHost:       100,
			IdleConnTimeout:       90 * time.Second,
			TLSHandshakeTimeout:   10 * time.Second,
			ExpectContinueTimeout: time.Second,
		},
	}
	controlPlaneClient, err := controlplane.NewClient(
		httpClient,
		cfg.ControlPlaneURL,
		cfg.ControlPlaneValidatePath,
		cfg.InternalAPIToken,
	)
	if err != nil {
		logger.Error("creating Control Plane client failed", "error", err)
		os.Exit(1)
	}
	validator, err := controlplane.NewCachedValidator(
		controlPlaneClient,
		cfg.ValidationCacheTTL,
		cfg.ValidationNegativeTTL,
	)
	if err != nil {
		logger.Error("creating key validation cache failed", "error", err)
		os.Exit(1)
	}
	proxyHandler, err := proxycore.NewHandler(
		cfg.BackendURL,
		validator,
		cfg.APIKeyHeader,
		cfg.ValidationTimeout,
		logger,
	)
	if err != nil {
		logger.Error("creating proxy handler failed", "error", err)
		os.Exit(1)
	}

	server := &http.Server{
		Addr:              cfg.ListenAddr,
		Handler:           middleware.Chain(proxyHandler, middleware.Recover(logger), middleware.RequestLogger(logger)),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	serverErrors := make(chan error, 1)
	go func() {
		logger.Info("reverse proxy starting", "listen_addr", cfg.ListenAddr, "backend_url", cfg.BackendURL.String())
		serverErrors <- server.ListenAndServe()
	}()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	defer signal.Stop(signals)

	select {
	case received := <-signals:
		logger.Info("shutdown signal received", "signal", received.String())
	case serveErr := <-serverErrors:
		if !errors.Is(serveErr, http.ErrServerClosed) {
			logger.Error("HTTP server stopped unexpectedly", "error", serveErr)
		}
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
		return
	}
	logger.Info("reverse proxy stopped")
}
