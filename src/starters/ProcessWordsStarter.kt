package starters

import TxtWordsListProcessor
import utils.exportedFilePath
import utils.resolveResource
import utils.txtWordsFile
import java.io.File

fun main() {
    val words = TxtWordsListProcessor(resolveResource(txtWordsFile)).readSimpleList()
    val deckWords = TxtWordsListProcessor(File(exportedFilePath)).readExportedList()
    val missingWords = words.filter { word -> deckWords.find { it.sameWord(word) } == null }

    TxtWordsListProcessor.writeSimpleList(missingWords, resolveResource(txtWordsFile))
}