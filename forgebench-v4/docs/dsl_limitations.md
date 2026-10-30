# Ограничения проверки Gradle/Kotlin DSL (v4) — честный статус

## Что осталось ограничением (наследовано от v3, ограничение #4)

Groovy (.gradle) и Kotlin (.gradle.kts) DSL-эталоны (задачи BUILD_*, часть PRJ_*)
проверяются **token-level**: среда не содержит парсера Groovy/Kotlin, а установка
`groovy`/`kotlinc` не покрывает семантику Gradle API. Полная проверка возможна только
реальной Gradle-сборкой (см. BLOCKED L3: требуется >=8 ГБ, Docker).

## Что v4 сделал сверх v3

1. **API-evidence на класс-уровень распространён и на DSL-эталоны**: имена
   `net.minecraftforge.*`/`net.neoforged.*`/`net.minecraft.*`, встречающиеся в
   build-скриптах (dependencies, versionCatalogs, конфигурации), прошли тот же
   class-level гейт в api_evidence.csv. Отсутствующих символов нет.
2. **Версии платформ в DSL-эталонах сверены** с pinned-артефактами:
   ForgeGradle 6 / Forge 47.3.0 / Gradle 8.1.1 / Java 17;
   ModDevGradle / NeoForge 21.1.77 / Gradle 8.9 / Java 21 (maven.neoforged.net).
3. Токен-левел проверки (сбалансированность скобок/кавычек, синтаксическая
   целостность нотации зависимостей) остаются в ast_eval (правила H-серии).

## Не сделано (честно)

- Полный парс DSL: NOT_RUN (нет парсера).
- Семантическая проверка плагинов/зависимостей внутри скриптов: NOT_RUN
  (требует Gradle-резолвер; блокирован средой).
- Из этого следует: DSL-эталоны НЕ имеют права помечаться compile_verified —
  их verification_status = syntax_verified (как у всех задач v4).
