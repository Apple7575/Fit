package com.ssafy.companyanalysis.auth.dto;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.service.UserPrincipal;

public record MeResponse(Long id, String email, String nickname) {

    public static MeResponse from(User user) {
        return new MeResponse(user.getId(), user.getEmail(), user.getNickname());
    }

    public static MeResponse from(UserPrincipal principal) {
        return new MeResponse(principal.getId(), principal.getUsername(), principal.getNickname());
    }
}
