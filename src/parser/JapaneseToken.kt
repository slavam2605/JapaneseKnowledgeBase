package parser

import dict.WordEntry

sealed class JapaneseToken(val text: String) {
    class UnknownWordToken(text: String) : JapaneseToken(text)
    class WordToken(text: String, val possibleWords: List<WordEntry>) : JapaneseToken(text)
    class HiraganaToken(text: String) : JapaneseToken(text)
    class OtherToken(text: String) : JapaneseToken(text)
}