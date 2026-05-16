// MCP stdio server exposing the risk_score tool.
//
// Built with github.com/mark3labs/mcp-go (the de-facto Go MCP SDK).
// The agent (Python, Block 3) can spawn this binary as a subprocess and
// talk JSON-RPC over stdio — see block4/demo_client.py for the integration.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

func main() {
	s := server.NewMCPServer(
		"fintech-risk-tool",
		"0.1.0",
		server.WithToolCapabilities(false),
	)

	tool := mcp.NewTool("risk_score",
		mcp.WithDescription(
			"Compute rule-based credit-risk score (0.0-1.0) for a "+
				"hypothetical order. Returns score, band, decision, and "+
				"the contributing factors. Rules derived from internal "+
				"credit policies (see block2/corpus.jsonl).",
		),
		mcp.WithString("merchant_segment",
			mcp.Required(),
			mcp.Description("travel | gaming | retail"),
			mcp.Enum("travel", "gaming", "retail"),
		),
		mcp.WithBoolean("is_new_buyer",
			mcp.Required(),
			mcp.Description("True if first-time buyer"),
		),
		mcp.WithNumber("order_value_twd",
			mcp.Required(),
			mcp.Description("Order amount in TWD (>= 0)"),
		),
		mcp.WithBoolean("has_jcic",
			mcp.Required(),
			mcp.Description("True if JCIC returned a credit record"),
		),
	)

	s.AddTool(tool, handleRiskScore)

	if err := server.ServeStdio(s); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

func handleRiskScore(
	_ context.Context, req mcp.CallToolRequest,
) (*mcp.CallToolResult, error) {
	in := RiskInput{
		MerchantSegment: req.GetString("merchant_segment", ""),
		IsNewBuyer:      req.GetBool("is_new_buyer", false),
		OrderValueTWD:   req.GetFloat("order_value_twd", 0),
		HasJCIC:         req.GetBool("has_jcic", false),
	}
	out, err := ScoreRisk(in)
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}
	js, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("marshal: %w", err)
	}
	return mcp.NewToolResultText(string(js)), nil
}
