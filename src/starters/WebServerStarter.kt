package starters

import TxtWordsListProcessor
import dict.jishoDataset
import server.WebApplication
import utils.exportedFilePath
import java.io.File

fun main() {
    val deckWords = TxtWordsListProcessor(File(exportedFilePath)).readExportedList()
    WebApplication(jishoDataset, deckWords).start()
}