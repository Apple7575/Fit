package com.ssafy.companyanalysis.agent.policy;

public record PolicyDecision(
        PolicyAction action,
        String reason,
        String reply,
        String policyVersion
) {
    public boolean allowsExecution() {
        return action == PolicyAction.ALLOW;
    }
}
