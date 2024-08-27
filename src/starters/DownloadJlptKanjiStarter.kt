package starters

import downloadKanjiList
import utils.*

fun main() {
    downloadKanjiList(resolveResource(PathConstants.kanjiJLPTN5File), "jlpt-n5")
    downloadKanjiList(resolveResource(PathConstants.kanjiJLPTN4File), "jlpt-n4")
    downloadKanjiList(resolveResource(PathConstants.kanjiJLPTN3File), "jlpt-n3")
    downloadKanjiList(resolveResource(PathConstants.kanjiJLPTN2File), "jlpt-n2")
    downloadKanjiList(resolveResource(PathConstants.kanjiJLPTN1File), "jlpt-n1")
}