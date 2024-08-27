package dict

import readWordsFile
import utils.PathConstants
import utils.resolveResource

val jishoDataset by lazy {
    readWordsFile(resolveResource(PathConstants.wordsFile))
}

val jishoCommonWords by lazy {
    resolveResource(PathConstants.commonWordsFile).bufferedReader().useLines { lines ->
        lines.map { WordEntryImpl.readFromString(it) }.toList()
    }
}