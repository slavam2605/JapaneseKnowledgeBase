package greek.spelling

open class GreekSpellingV2 : GreekSpellingV1() {
    override fun getSusOmicron(s: String): List<SusResult> {
        val regex = "[οό](?!\\b)(?![ιίυύς])".toRegex()
        return regex.findAll(s).mapNotNull { result ->
            if (result.range == 0..0 &&
                (s.startsWith("οι ") || s.startsWith("ο "))
            ) {
                // "οι" or "ο" article
                return@mapNotNull null
            }
            SusResult(result.range, SusLetter.O)
        }.toList()
    }
}