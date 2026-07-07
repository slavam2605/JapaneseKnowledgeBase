# JapaneseKnowledgeBase

This repository is a Kotlin/JVM Gradle project for Japanese and Greek language tooling, plus a
small Ktor web application.

## Environment

- Kotlin `2.1.20` on the JVM via Gradle.
- Source code lives directly under `src/`; there is no `src/main/kotlin` split.
- Runtime assets, downloaded datasets, and bundled frontend files live under `resources/`.
- The Git default branch in this repo is `master`.
- In this checkout, `gradlew` is not executable, so prefer `bash ./gradlew ...`.

## Build And Run

- `bash ./gradlew build` - primary validation gate; compiles the project and runs the configured
  test task.
- `bash ./gradlew test` - run tests only.
- `bash ./gradlew run` - start the Ktor app via `starters.WebServerStarterKt`.
- `bash ./gradlew tasks --all` - inspect available Gradle tasks.

Useful targeted tasks:

- `bash ./gradlew runLexer`
- `bash ./gradlew downloadCommonWords`
- `bash ./gradlew downloadGreekConjugations`
- `bash ./gradlew downloadJlptKanji`
- `bash ./gradlew downloadWords`
- `bash ./gradlew processWords`

## Repo-Specific Guidance

- Keep starter entry points in `src/starters/` thin; prefer reusable logic in the domain packages
  under `src/`.
- Avoid refreshing large downloaded resources in `resources/` unless the task explicitly requires
  it.
- Treat zipped resource archives and generated data files as high-churn artifacts; do not rewrite
  them incidentally.
- For server or UI changes, validate by running `bash ./gradlew run` and checking the affected
  route or page.
- For parser, downloader, or deck-generation changes, prefer the narrowest relevant starter task in
  addition to `bash ./gradlew build`.

## Style

- Follow official Kotlin style.
- Use PascalCase for classes, camelCase for functions and variables, and UPPER_SNAKE_CASE for
  constants.
- Do not use wildcard imports.
- Prefer extension functions for focused helpers on existing types.
- Lean on Kotlin null-safety rather than defensive Java-style patterns.
- Keep functions focused and avoid unrelated refactors while working on an issue.
