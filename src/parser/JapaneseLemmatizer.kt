package parser

object JapaneseLemmatizer {
    fun toNormalForm(text: String): List<String> {
        return listOf(
            VerbsLemmatizer.toNormalForm(text),
            AdjectivesLemmatizer.toNormalForm(text)
        ).flatten().distinct()
    }
}