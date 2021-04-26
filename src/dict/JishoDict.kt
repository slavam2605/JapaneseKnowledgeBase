package dict

import readWordsFile
import utils.commonWordsFile
import utils.resolveResource
import utils.wordsFile

val jishoDataset by lazy {
    readWordsFile(resolveResource(wordsFile))
}

val jishoCommonWords by lazy {
    resolveResource(commonWordsFile).bufferedReader().useLines { lines ->
        lines.map { WordEntryImpl.readFromString(it) }.toList()
    }
}