# ---- backend Dockerfile ----
# 多阶段构建: Maven 构建 → JRE 运行
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
# 先拉依赖(利用层缓存)
RUN mvn -B dependency:go-offline -q || true
COPY src ./src
RUN mvn -B clean package -DskipTests -q

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN groupadd -r spring && useradd -r -g spring spring \
    && mkdir -p /app/uploads && chown -R spring:spring /app
USER spring
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD ["/bin/sh", "-c", "curl -sf http://127.0.0.1:8080/api/health || exit 1"]
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75.0", "-jar", "app.jar"]
