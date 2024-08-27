package starters

import TxtWordsListProcessor
import utils.PathConstants
import utils.resolveResource
import java.io.File

fun main() {
    val words = TxtWordsListProcessor(resolveResource(PathConstants.txtWordsFile)).readSimpleList()
    val deckWords = TxtWordsListProcessor(PathConstants.exportedFilePath.toFile()).readExportedList()
    val missingWords = words.filter { word -> deckWords.find { it.sameWord(word) } == null }

    TxtWordsListProcessor.writeSimpleList(missingWords, resolveResource(PathConstants.txtWordsFile))
}