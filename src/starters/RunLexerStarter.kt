package starters

import dict.AllWordsList
import parser.JapaneseLexer
import readWordsFile
import utils.resolveResource
import utils.sampleTextFile
import utils.wordsFile

fun main() {
    val text = resolveResource(sampleTextFile).readText()
    val dataset = readWordsFile(resolveResource(wordsFile))
    val tokens = JapaneseLexer(text, AllWordsList(dataset)).getTokens()
    for (token in tokens) {
        print("[$token]")
    }
}