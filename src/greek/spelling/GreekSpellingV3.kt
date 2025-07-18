package greek.spelling

/**
 * Removes suspicious letters from the translation field
 */
open class GreekSpellingV3 : GreekSpellingV2() {
    override fun transformTranslation(s: String): String {
        val susResults = s.isSus(emptyList())
        return smartReplace(s, susResults, "*")
    }
}