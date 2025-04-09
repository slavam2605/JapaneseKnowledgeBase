import org.jetbrains.kotlin.gradle.tasks.KotlinCompile

val ktorVersion: String by project
val kotlinVersion: String by project
val logbackVersion: String by project

plugins {
    kotlin("jvm") version "2.1.20"
    application
}

group = "com.moklev.japanese.base"
version = "0.0.1"

sourceSets {
    main {
        kotlin.srcDirs("src")
        java.srcDirs("src")
    }
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jsoup:jsoup:1.15.3")
    implementation("org.jetbrains.kotlin:kotlin-stdlib-jdk8:$kotlinVersion")
    implementation("io.ktor:ktor-server-core:$ktorVersion")
    implementation("io.ktor:ktor-server-netty:$ktorVersion")
    implementation("io.ktor:ktor-server-html-builder:$ktorVersion")
    implementation("ch.qos.logback:logback-classic:$logbackVersion")
    implementation("org.jetbrains.kotlin-wrappers:kotlin-css-jvm:1.0.0-pre.798")
    implementation("io.ktor:ktor-client-core:$ktorVersion")
    implementation("io.ktor:ktor-client-core-jvm:$ktorVersion")
    implementation("io.ktor:ktor-client-apache:$ktorVersion")
    implementation("org.xerial:sqlite-jdbc:3.41.2.2")
    testImplementation("io.ktor:ktor-server-tests:$ktorVersion")
}

application {
    mainClass.set("starters.WebServerStarterKt")
}

// Customize tasks parameters
tasks {
    // Opt-in APIs
    withType<KotlinCompile> {
        compilerOptions {
            freeCompilerArgs.addAll(
                "-opt-in=kotlin.time.ExperimentalTime",
                "-opt-in=kotlin.ExperimentalStdlibApi"
            )
        }
    }

    // Remove the XML expansion limit for parsing JMDict
    withType<JavaExec> {
        jvmArgs = listOf("-Djdk.xml.entityExpansionLimit=0")
    }
}

// Custom tasks for different run configurations
tasks {
    register<JavaExec>("downloadCommonWords") {
        group = "data"
        description = "Downloads common Japanese words"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.DownloadCommonWordsStarterKt")
    }

    register<JavaExec>("downloadGreekConjugations") {
        group = "data"
        description = "Downloads Greek verb conjugations"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.DownloadGreekConjugationsKt")
    }

    register<JavaExec>("downloadJlptKanji") {
        group = "data"
        description = "Downloads JLPT kanji lists"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.DownloadJlptKanjiStarterKt")
    }

    register<JavaExec>("processWords") {
        group = "data"
        description = "Processes word lists and identifies missing words"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.ProcessWordsStarterKt")
    }

    register<JavaExec>("runLexer") {
        group = "tools"
        description = "Tests the Japanese lexer on sample text"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.RunLexerStarterKt")
    }

    register<JavaExec>("downloadWords") {
        group = "data"
        description = "Downloads kanji/words data"
        classpath = sourceSets.main.get().runtimeClasspath
        mainClass.set("starters.WordsDownloaderStarterKt")
    }
}