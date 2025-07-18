# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Run Commands
- `./gradlew build` - Build the project
- `./gradlew run` - Run the web application
- `./gradlew test` - Run all tests
- `./gradlew test --tests "ClassName.testMethodName"` - Run a specific test

## Code Style Guidelines
- Use official Kotlin style guide (`kotlin.code.style=official`)
- Naming: Classes - PascalCase, Functions/Variables - camelCase, Constants - UPPER_SNAKE_CASE
- Imports: No wildcards, grouped by package, alphabetically ordered
- Prefer extension functions for utility operations on existing types
- Use data classes for value objects and sealed classes for type hierarchies
- Leverage Kotlin's null safety features with proper nullability annotations
- Follow existing error handling patterns using Elvis operators and safe calls
- Keep functions focused on single responsibility
- Use companion objects for factory methods and static-like functionality
- Document public APIs with KDoc format comments
- Utilize type inference where it improves readability