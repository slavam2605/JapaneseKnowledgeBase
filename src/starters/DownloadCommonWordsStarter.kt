package starters

import downloadCommonWords
import utils.PathConstants
import utils.resolveResource

private const val skipDangerousRun = true

fun main() {
    if (skipDangerousRun) {
        println("Skipping download common words: this run can corrupt an existing words database")
        return
    }

    downloadCommonWords(resolveResource(PathConstants.commonWordsFile))
}