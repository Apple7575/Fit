package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.domain.UserStatus;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.Collection;
import java.util.List;

/** 인증 주체. username 은 이메일이며 회원 식별자·닉네임·상태를 함께 실어 응답·인증 판단에 쓴다. */
public class UserPrincipal implements UserDetails {

    private final Long id;
    private final String email;
    private final String nickname;
    private final String passwordHash;
    private final UserStatus status;
    private final Collection<? extends GrantedAuthority> authorities;

    public UserPrincipal(User user) {
        this.id = user.getId();
        this.email = user.getEmail();
        this.nickname = user.getNickname();
        this.passwordHash = user.getPasswordHash();
        this.status = user.getStatus();
        this.authorities = List.of(new SimpleGrantedAuthority(user.getRole().name()));
    }

    public Long getId() {
        return id;
    }

    public String getNickname() {
        return nickname;
    }

    public UserStatus getStatus() {
        return status;
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return authorities;
    }

    @Override
    public String getPassword() {
        return passwordHash;
    }

    @Override
    public String getUsername() {
        return email;
    }

    @Override
    public boolean isAccountNonExpired() {
        return true;
    }

    @Override
    public boolean isAccountNonLocked() {
        return true;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    @Override
    public boolean isEnabled() {
        // PENDING 은 인증 자체는 통과시키고(비밀번호 확인 후) 로그인 컨트롤러에서 막는다.
        return status != UserStatus.SUSPENDED && status != UserStatus.WITHDRAWN;
    }
}
