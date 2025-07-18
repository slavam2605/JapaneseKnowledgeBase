package greek.spelling

import utils.AnkiNote

enum class SusLetter { I, O }
data class SusResult(val range: IntRange, val letter: SusLetter)

abstract class GreekSpelling {
    abstract fun getSusIota(s: String): List<SusResult>
    abstract fun getSusOmicron(s: String): List<SusResult>
    abstract fun getSusOmega(s: String): List<SusResult>
    abstract fun getSusIta(s: String, tags: List<String>): List<SusResult>
    abstract fun getSusUpsilon(s: String): List<SusResult>
    abstract fun getSusOi(s: String): List<SusResult>
    abstract fun getSusEi(s: String): List<SusResult>

    abstract fun transformTranslation(s: String): String

    abstract fun getSpellings(notes: List<AnkiNote>): Map<AnkiNote, String>
}