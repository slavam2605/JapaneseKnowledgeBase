package starters

import TxtWordsListProcessor
import dict.jishoDataset
import server.WebApplication
import utils.PathConstants.exportedFilePath

fun main() {
    val deckWords = TxtWordsListProcessor(exportedFilePath.toFile()).readExportedList()
    WebApplication(jishoDataset, deckWords).start()
}