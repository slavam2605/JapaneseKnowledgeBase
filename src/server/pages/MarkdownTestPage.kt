package server.pages

import io.ktor.application.ApplicationCall
import kotlinx.html.*

class MarkdownTestPage : PageBuilderBase("markdown") {
    override fun HEAD.buildHead() {
        link("/markdown.css", "stylesheet", "text/css")
        script(src = "/markdown.js") {}
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        div("markdown") {
            +"""
                # Main title
                So I want to **test** whether _this_ implementation works or not.  
                It should be with `code inline parts` and other cool stuff.
                It should allow under_scored words, but support just*in*the*middle*of*the*word italics.
                ## Not so main title
                Here I suppose to write some additional info
                1. Even
                2. With
                    1. Multilevel
                    2. Cool
                3. Lists!
                
                And also
                + Unordered
                * Bullet
                - Lists!
                + So wow
                
                Do you think it is enough? No!
                1. Mixed
                * Lists
                    2. With different
                    3. Levels
                    * And
                    4. Different
                    * Marker types
                                        10. Wow such jump
                            - Very
                            + List
                1110. Super base
            """.trimIndent()
        }
    }
}