package com.ssafy.companyanalysis.auth.service;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UsernameNotFoundException;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class CustomUserDetailsServiceTest {

    @Mock
    private UserRepository userRepository;

    @InjectMocks
    private CustomUserDetailsService customUserDetailsService;

    @Test
    @DisplayName("이메일로 회원을 찾아 이메일·권한을 담은 UserDetails 를 만든다")
    void loadsUserByEmail() {
        given(userRepository.findByEmail("user@example.com"))
                .willReturn(Optional.of(User.create("user@example.com", "hash", "민재")));

        UserDetails details = customUserDetailsService.loadUserByUsername("user@example.com");

        assertThat(details.getUsername()).isEqualTo("user@example.com");
        assertThat(details.getPassword()).isEqualTo("hash");
        assertThat(details.getAuthorities()).extracting("authority").containsExactly("ROLE_USER");
        assertThat(details.isEnabled()).isTrue();
    }

    @Test
    @DisplayName("이메일이 없으면 UsernameNotFoundException")
    void throwsWhenEmailNotFound() {
        given(userRepository.findByEmail("missing@example.com")).willReturn(Optional.empty());

        assertThatThrownBy(() -> customUserDetailsService.loadUserByUsername("missing@example.com"))
                .isInstanceOf(UsernameNotFoundException.class);
    }
}
