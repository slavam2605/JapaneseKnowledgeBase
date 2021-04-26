package starters

import downloadKanjiList
import utils.*

fun main() {
    downloadKanjiList(resolveResource(kanjiJLPTN5File), "jlpt-n5")
    downloadKanjiList(resolveResource(kanjiJLPTN4File), "jlpt-n4")
    downloadKanjiList(resolveResource(kanjiJLPTN3File), "jlpt-n3")
    downloadKanjiList(resolveResource(kanjiJLPTN2File), "jlpt-n2")
    downloadKanjiList(resolveResource(kanjiJLPTN1File), "jlpt-n1")
}