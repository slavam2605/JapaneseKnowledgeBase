package starters

import dict.AllWordsList
import parser.JapaneseLexer
import readWordsFile
import utils.PathConstants
import utils.resolveResource

fun main() {
    val text = resolveResource(PathConstants.sampleTextFile).readText()
    val dataset = readWordsFile(resolveResource(PathConstants.wordsFile))
    val tokens = JapaneseLexer(text, AllWordsList(dataset)).getTokens()
    for (token in tokens) {
        print("[$token]")
    }
}