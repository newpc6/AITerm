package app

import (
	"fmt"
	"log"
	"net/http"

	"aiterm-server/internal/api"
	"aiterm-server/internal/config"
)

func Run() error {
	cfg := config.Load()
	handler, err := api.NewRouter(cfg)
	if err != nil {
		return err
	}

	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", cfg.Port),
		Handler: handler,
	}

	log.Printf(
		"AITerm server listening on http://127.0.0.1:%d (db=%s, sqlite=%s)",
		cfg.Port,
		cfg.Database.Driver,
		cfg.Database.SQLitePath,
	)

	return server.ListenAndServe()
}
