package utils

import java.lang.StringBuilder

fun String.splitAnkiHtml(): List<String> {
    var nestedLevel = 0
    var index = 0
    val result = mutableListOf<String>()
    val builder = StringBuilder()

    fun onDiv() = startsWith("<div>", index)
    fun onCDiv() = startsWith("</div>", index)
    fun skipDiv() { index += "<div>".length }
    fun skipCDiv() { index += "</div>".length }
    fun resetBuilder() {
        if (builder.isNotBlank()) {
            result.add(builder.toString())
        }
        builder.clear()
    }

    while (index < length) {
        when {
            onDiv() -> {
                resetBuilder()
                nestedLevel++
                skipDiv()
            }
            onCDiv() -> {
                nestedLevel--
                skipCDiv()
            }
            else -> {
                builder.append(this[index])
                index++
            }
        }
    }
    resetBuilder()
    check(nestedLevel == 0)
    return result
}