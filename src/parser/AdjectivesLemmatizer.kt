package parser

object AdjectivesLemmatizer {
    fun toNormalForm(text: String): List<String> {
        // ignore な-adjectives, should be parsed as Noun
        return toPlainForm(text).flatMap { toBaseAdjective(it) }
    }

    /**
     * Transform all variations of dictionary form (like
     * negative forms) to a base adjective
     */
    private fun toBaseAdjective(text: String): List<String> {
        return listOf(
            listOf(text),
            fromNegativeFrom(text)
        ).flatten()
    }

    /**
     * Transform from terminal (non-adjective) forms (-く, -かった and so on)
     * to a plain form of an adjective (but maybe bot base, like negative form)
     */
    private fun toPlainForm(text: String): List<String> {
        return listOf(
            listOf(text),
            fromAdverbialForm(text),
            fromPastForm(text),
            fromNounForm(text)
        ).flatten()
    }

    private fun fromNounForm(text: String): List<String> {
        return if (text.endsWith("さ"))
            listOf(text.dropLast(1) + "い")
        else
            emptyList()
    }

    fun fromPastForm(text: String): List<String> {
        return if (text.endsWith("かった"))
            listOf(text.dropLast(3) + "い")
        else
            emptyList()
    }

    private fun fromNegativeFrom(text: String): List<String> {
        return if (text.endsWith("くない"))
            listOf(text.dropLast(3) + "い")
        else
            emptyList()
    }

    private fun fromAdverbialForm(text: String): List<String> {
        return if (text.endsWith("く"))
            listOf(text.dropLast(1) + "い")
        else
            emptyList()
    }
}