package api

import (
	"encoding/json"
	"net/http"
	"time"
)

type terminalExecuteRequest struct {
	Command string `json:"command"`
	NodeID  string `json:"node_id"`
}

type terminalExecuteResponse struct {
	Command   string `json:"command"`
	Output    string `json:"output"`
	ExitCode  int    `json:"exit_code"`
	TimedOut  bool   `json:"timed_out"`
	NodeID    string `json:"node_id"`
	NodeName  string `json:"node_name"`
	Timestamp string `json:"timestamp"`
}

func handleTerminalExecute(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeMethodNotAllowed(w)
		return
	}

	var req terminalExecuteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1000,
			Message: "invalid request",
		})
		return
	}

	if req.Command == "" {
		writeJSON(w, http.StatusBadRequest, response{
			Code:    1001,
			Message: "command is required",
		})
		return
	}

	nodeID := req.NodeID
	if nodeID == "" {
		nodeID = "1"
	}

	nodeName := "local"
	if node, ok := defaultStore.getNode(nodeID); ok {
		nodeName = node.Name
	}

	result := executeCommand(r.Context(), req.Command)

	output := ""
	for _, line := range result.Lines {
		output += line.Content + "\n"
	}

	writeJSON(w, http.StatusOK, response{
		Code:    0,
		Message: "ok",
		Data: terminalExecuteResponse{
			Command:   req.Command,
			Output:    output,
			ExitCode:  result.ExitCode,
			TimedOut:  result.TimedOut,
			NodeID:    nodeID,
			NodeName:  nodeName,
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		},
	})
}
