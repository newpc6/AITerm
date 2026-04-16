package api

import (
	"context"
	"fmt"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

type commandOutputLine struct {
	Stream  string
	Content string
}

type commandExecutionResult struct {
	Lines    []commandOutputLine
	ExitCode int
	TimedOut bool
	Err      error
}

const commandExecutionTimeout = 60 * time.Second

func executeCommand(parent context.Context, command string) commandExecutionResult {
	trimmed := strings.TrimSpace(command)
	if trimmed == "" {
		return commandExecutionResult{
			Lines:    []commandOutputLine{{Stream: "stderr", Content: "未生成可执行命令。"}},
			ExitCode: 1,
			Err:      exec.ErrNotFound,
		}
	}

	ctx, cancel := context.WithTimeout(parent, commandExecutionTimeout)
	defer cancel()

	cmd := buildShellCommand(ctx, trimmed)
	output, err := cmd.CombinedOutput()
	lines := splitOutputLines(string(output))
	exitCode := 0
	if err != nil {
		exitCode = 1
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		}
	}
	timedOut := ctx.Err() == context.DeadlineExceeded
	if len(lines) == 0 {
		if timedOut {
			lines = []commandOutputLine{{Stream: "stderr", Content: fmt.Sprintf("命令执行超时，已在 %s 后终止。", commandExecutionTimeout.String())}}
		} else {
			lines = []commandOutputLine{{Stream: "stdout", Content: "命令未返回输出。"}}
		}
	}

	return commandExecutionResult{
		Lines:    lines,
		ExitCode: exitCode,
		TimedOut: timedOut,
		Err:      err,
	}
}

func buildShellCommand(ctx context.Context, command string) *exec.Cmd {
	if runtime.GOOS == "windows" {
		utf8Command := "$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); " + command
		return exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", utf8Command)
	}

	return exec.CommandContext(ctx, "sh", "-lc", command)
}

func splitOutputLines(output string) []commandOutputLine {
	trimmed := strings.ReplaceAll(output, "\r\n", "\n")
	trimmed = strings.TrimSpace(trimmed)
	if trimmed == "" {
		return nil
	}

	parts := strings.Split(trimmed, "\n")
	segments := make([]string, 0, len(parts))
	for _, part := range parts {
		value := strings.TrimSpace(part)
		if value == "" {
			continue
		}
		segments = append(segments, value)
	}
	if len(segments) == 0 {
		return nil
	}
	return []commandOutputLine{{
		Stream:  "stdout",
		Content: strings.Join(segments, " | "),
	}}
}
