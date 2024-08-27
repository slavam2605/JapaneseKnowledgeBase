package server

import TxtWordEntry
import dict.AllWordsList
import dict.WordEntry
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationCall
import io.ktor.server.application.call
import io.ktor.server.application.log
import io.ktor.server.html.respondHtml
import io.ktor.server.response.respondFile
import io.ktor.server.routing.get
import io.ktor.server.routing.routing
import io.ktor.server.engine.embeddedServer
import io.ktor.server.netty.Netty
import kotlinx.html.*
import server.pages.PageBuilder
import utils.resolveResource
import java.io.File

class WebApplication(
    val dataset: Map<Char, List<WordEntry>>,
    val words: List<TxtWordEntry>
) {
    private val allowedFiles = mapOf(
        "style.css" to "css",
        "kanji_details.css" to "css",
        "kanji_index.css" to "css",
        "kanji_map.css" to "css",
        "random_word.css" to "css",
        "tooltip.css" to "css",
        "learn_stats.css" to "css",
        "annotated_text.css" to "css",
        "writing_test.css" to "css",
        "reading_test.css" to "css",
        "markdown.css" to "css",
        "collapsible.js" to "",
        "tree-example.js" to "",
        "markdown.js" to "",
        "Treant.css" to "treant-js-master",
        "Treant.js" to "treant-js-master",
        "vendor/raphael.js" to "treant-js-master"
    )

    fun start() {
        println("Starting server at http://localhost:12312")
        val server = embeddedServer(Netty, 12312) { initModule() }
        server.start(wait = true)
    }

    private fun Application.initModule() {
        val kanjiVG = KanjiVG(dataset.keys)
        val allWords = AllWordsList(dataset)
        with (ComponentContainerManager) {
            registerContent(dataset)
            registerContent(kanjiVG)
            registerContent(allWords)
            registerContent(words)
        }

        val pages = ComponentContainerManager.getImplementations<PageBuilder>()
        routing {
            for (page in pages) {
                get(page.path) {
                    call.respondPage(page)
                }
            }
            get("/index") {
                call.respondHtml {
                    body {
                        for (page in pages) {
                            a(href = page.path) {
                                +page.path
                            }
                            br {  }
                        }
                    }
                }
            }
            get("/{filePath...}") {
                val filePath = context.parameters.getAll("filePath")!!.joinToString(separator = "/")
                val relativeLocation = allowedFiles[filePath] ?: run {
                    this@initModule.log.warn("Asked for file '$filePath' which is not allowed")
                    return@get
                }

                val file = File(relativeLocation).resolve(filePath)
                call.respondFile(resolveResource(file.path))
            }
        }
    }

    private suspend fun ApplicationCall.respondPage(pageBuilder: PageBuilder) {
        respondHtml {
            head {
                link("/style.css", "stylesheet", "text/css")
                with(pageBuilder) { buildHead() }
            }
            body {
                with(pageBuilder) { buildPage(this@respondPage) }
            }
        }
    }
}