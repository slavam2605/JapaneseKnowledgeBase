package server.pages

import io.ktor.server.application.ApplicationCall
import kotlinx.html.BODY
import kotlinx.html.HEAD

interface PageBuilder {
    val path: String
    fun BODY.buildPage(call: ApplicationCall)
    fun HEAD.buildHead() {}
}