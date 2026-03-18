package starters

import downloadWords
import utils.KanjiLists
import utils.PathConstants
import utils.compressResource
import utils.resolveResource
import utils.uncompressResource

fun main() {
    // First, try to uncompress existing word list if it exists
    uncompressResource(PathConstants.wordsFile)
    
    // Download words
    downloadWords(
        resolveResource(PathConstants.wordsFile),
        *KanjiLists.jouyou.toCharArray()
    )
    
    // Compress the word list after downloading
    compressResource(PathConstants.wordsFile)
}
