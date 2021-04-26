package server.pages

import dict.OutlierDict
import io.ktor.application.ApplicationCall
import kotlinx.html.*

class TreeExamplePage : PageBuilderBase("/tree") {
    override fun HEAD.buildHead() {
        link(rel = "stylesheet", href = "Treant.css", type = "text/css")
    }

    private fun OutlierDict.Entry.toNode(): String {
        val children = components.mapNotNull { (component, _) ->
            OutlierDict.entries[component]?.toNode()
        }
        return "{ text: {name: \"$kanji\"}, children: [${children.joinToString()}] }"
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        div {
            id = "tree-simple"
        }

        script(src = "vendor/raphael.js") {}
        script(src = "Treant.js") {}

        val kanji = "現"
        val entry = OutlierDict.entries[kanji] ?: return

        script {
            unsafe {
                +"""
                    const simple_chart_config = {
                        chart: {
                            container: "#tree-simple",
                            connectors: {
                                type: "straight",
                                style: {
                                    stroke: '#8080FF',
                                    'arrow-end': 'block-wide-long',
                                    'stroke-width': 1.5
                                }
                            }
                        },

                        nodeStructure:
                            ${entry.toNode()}
                    };

                    new Treant(simple_chart_config);
                """.trimIndent()
            }
        }
    }
}