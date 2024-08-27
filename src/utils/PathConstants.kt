package utils

import kotlin.io.path.Path
import kotlin.io.path.div

enum class SystemInfo {
    Windows, MacOS, Linux;

    companion object {
        val info = System.getProperty("os.name").lowercase().let { osName ->
            when {
                osName.contains("win") -> Windows
                osName.contains("mac") -> MacOS
                else -> Linux
            }
        }
    }
}

object PathConstants {
    /* System info */
    private val appData = System.getenv("APPDATA")?.let { Path(it) }
    private val userHome = Path(System.getProperty("user.home"))

    /* Anki info */
    private const val ANKI_USER = "User 1"
    val ankiCollectionPath = when (SystemInfo.info) {
        SystemInfo.Windows -> appData!! / "Anki2" / ANKI_USER / "collection.anki2"
        SystemInfo.MacOS -> userHome / "Library" / "Application Support" / "Anki2" / ANKI_USER / "collection.anki2"
        SystemInfo.Linux -> TODO()
    }
    private const val WORDS_DECK = "日本語__Words__Words MNN1-2.txt"
    private const val KANJI_WORDS_DECK = "日本語__Kanji__Kanji words.txt"

    val exportedFilePath = userHome / WORDS_DECK
    val exportedKanjiWordsPath = userHome / KANJI_WORDS_DECK
    const val wordsFile = "word_list_2.txt"
    const val txtWordsFile = "missing_words.txt"
    const val commonWordsFile = "common_words.txt"
    const val jmDictFile = "JMdict"
    const val enamDictFile = "enamdict"
    const val sampleTextFile = "sample_text.txt"

    const val kanjiJLPTN5File = "jlpt5_kanji_list.txt"
    const val kanjiJLPTN4File = "jlpt4_kanji_list.txt"
    const val kanjiJLPTN3File = "jlpt3_kanji_list.txt"
    const val kanjiJLPTN2File = "jlpt2_kanji_list.txt"
    const val kanjiJLPTN1File = "jlpt1_kanji_list.txt"
}