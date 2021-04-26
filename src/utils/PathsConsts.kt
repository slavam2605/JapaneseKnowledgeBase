package utils

private val appData = System.getenv("APPDATA")
private val userHome = System.getProperty("user.home")

const val endTag = "</svg>"
val mediaFolder = "$appData\\Anki2\\1-й пользователь\\collection.media"
const val wordsFile = "word_list_2.txt"
const val txtWordsFile = "missing_words.txt"
val exportedFilePath = "$userHome\\Minna no Nihongo_ слова.txt"
const val commonWordsFile = "common_words.txt"
const val jmDictFile = "JMdict"
const val jmDictSimplifiedFile = "JMdict_simplified"
const val enamDictFile = "enamdict"
const val sampleTextFile = "sample_text.txt"

const val kanjiJLPTN5File = "jlpt5_kanji_list.txt"
const val kanjiJLPTN4File = "jlpt4_kanji_list.txt"
const val kanjiJLPTN3File = "jlpt3_kanji_list.txt"
const val kanjiJLPTN2File = "jlpt2_kanji_list.txt"
const val kanjiJLPTN1File = "jlpt1_kanji_list.txt"