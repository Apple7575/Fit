package com.ssafy.companyanalysis.agent.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.Executor;

/**
 * 자소서를 받은 방을 사용자가 묻기 전에 한 바퀴 돌린다.
 *
 * <p>방을 하나씩 차례로 돈다. 한꺼번에 띄우면 턴을 이끄는 스레드가 방 수만큼 생기는데 그
 * 스레드들은 저마다 에이전트가 끝나기를 기다린다. 에이전트가 앉을 자리가 남지 않아 실행 풀이
 * 서로를 기다리며 멈춘다.
 *
 * <p>한 방이 실패해도 다음 방으로 넘어간다. 자동 검토는 사용자가 부탁한 일이 아니라 미리 해
 * 두는 일이라, 하나가 안 됐다고 나머지를 접을 이유가 없다.
 */
@Component
public class AutoReviewStarter {

    private static final Logger log = LoggerFactory.getLogger(AutoReviewStarter.class);

    private final TurnService turnService;
    private final Executor autoReviewExecutor;

    public AutoReviewStarter(TurnService turnService,
                             @Qualifier("autoReviewExecutor") Executor autoReviewExecutor) {
        this.turnService = turnService;
        this.autoReviewExecutor = autoReviewExecutor;
    }

    /** 부르는 쪽은 기다리지 않는다. 방을 깔아 준 응답이 검토가 끝날 때까지 붙들려 있으면 안 된다. */
    public void startAll(Long userId, List<Long> roomIds) {
        if (roomIds.isEmpty()) {
            return;
        }
        autoReviewExecutor.execute(() -> {
            for (Long roomId : roomIds) {
                try {
                    turnService.autoReview(userId, roomId);
                } catch (Exception e) {
                    log.warn("자동 검토를 돌리지 못했다: roomId={}, 사유={}", roomId, e.getMessage());
                }
            }
        });
    }
}
