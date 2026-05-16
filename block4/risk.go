// Package main: pure-Go rule-based credit-risk scoring.
//
// Logic mirrors the policy docs in block2/corpus.jsonl:
//   - policy-001: new-buyer cohort baseline delinquency ~5.5% vs 4.5%
//   - policy-003: travel-segment +1.0pp baseline premium
//   - policy-004: gaming-segment caps (5k new / 15k returning per order)
//   - playbook-004: JCIC-fallback path caps initial at TWD 15,000
//
// Kept deliberately rule-based (no ML) — mirrors the "rule-based intervention
// took unpaid rate from 4.5% to 3.5%" claim in playbook-002.
package main

import (
	"errors"
	"fmt"
)

type RiskInput struct {
	MerchantSegment string  `json:"merchant_segment"`
	IsNewBuyer      bool    `json:"is_new_buyer"`
	OrderValueTWD   float64 `json:"order_value_twd"`
	HasJCIC         bool    `json:"has_jcic"`
}

type RiskOutput struct {
	Score         float64  `json:"score"`
	Band          string   `json:"band"`
	Decision      string   `json:"decision"`
	Contributions []string `json:"contributions"`
}

var allowedSegments = map[string]bool{
	"travel": true, "gaming": true, "retail": true,
}

// orderValueCap returns the policy-defined per-order cap (TWD) for a segment +
// new/returning combination. ok=false means no cap defined (retail = no cap).
func orderValueCap(segment string, isNew bool) (cap float64, ok bool) {
	switch segment {
	case "gaming":
		if isNew {
			return 5000, true
		}
		return 15000, true
	case "travel":
		if isNew {
			return 30000, true
		}
	}
	return 0, false
}

func ScoreRisk(in RiskInput) (RiskOutput, error) {
	if !allowedSegments[in.MerchantSegment] {
		return RiskOutput{}, fmt.Errorf(
			"invalid merchant_segment %q (allowed: travel, gaming, retail)",
			in.MerchantSegment)
	}
	if in.OrderValueTWD < 0 {
		return RiskOutput{}, errors.New("order_value_twd must be >= 0")
	}

	score := 0.10
	contribs := []string{"base 0.10 (portfolio baseline)"}

	if in.IsNewBuyer {
		score += 0.10
		contribs = append(contribs, "new buyer +0.10 (policy-001)")
	}
	if in.MerchantSegment == "travel" {
		score += 0.05
		contribs = append(contribs, "travel segment +0.05 (policy-003)")
	}
	if !in.HasJCIC {
		score += 0.08
		contribs = append(contribs, "no JCIC record +0.08 (playbook-004)")
	}
	if cap, ok := orderValueCap(in.MerchantSegment, in.IsNewBuyer); ok &&
		in.OrderValueTWD > cap {
		score += 0.05
		contribs = append(contribs, fmt.Sprintf(
			"order_value %.0f exceeds %s cap %.0f +0.05",
			in.OrderValueTWD, in.MerchantSegment, cap))
	}

	band, decision := bandAndDecision(score)
	return RiskOutput{
		Score: score, Band: band, Decision: decision,
		Contributions: contribs,
	}, nil
}

func bandAndDecision(score float64) (band, decision string) {
	switch {
	case score < 0.20:
		return "low", "approve"
	case score < 0.35:
		return "medium", "review"
	default:
		return "high", "decline"
	}
}
