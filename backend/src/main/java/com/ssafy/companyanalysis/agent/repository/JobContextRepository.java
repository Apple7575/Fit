package com.ssafy.companyanalysis.agent.repository;

import com.ssafy.companyanalysis.agent.domain.JobContext;
import org.springframework.data.jpa.repository.JpaRepository;

public interface JobContextRepository extends JpaRepository<JobContext, String> {
}
