# syntax=docker/dockerfile:1
FROM gradle:9.7.1-jdk21 AS build
USER root
WORKDIR /app
ENV GRADLE_USER_HOME=/gradle-home
COPY settings.gradle build.gradle ./
COPY src ./src
RUN --mount=type=cache,target=/gradle-home gradle bootJar --no-daemon

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=70", "-jar", "app.jar"]
