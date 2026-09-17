package com.ssafy.companyanalysis.auth.repository;

import com.ssafy.companyanalysis.auth.domain.User;
import com.ssafy.companyanalysis.auth.domain.UserStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    @Modifying
    @Query("DELETE FROM User u WHERE u.id IN :ids AND u.status = :status")
    int deleteByIdInAndStatus(@Param("ids") Collection<Long> ids, @Param("status") UserStatus status);
}
