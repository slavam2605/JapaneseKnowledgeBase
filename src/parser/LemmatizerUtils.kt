package parser

import utils.Hiragana
import utils.KanaVowel

fun String.getHiragana(index: Int): Hiragana? {
    val normalizedIndex = if (index < 0) length + index else index
    val char = getOrNull(normalizedIndex) ?: return null
    return Hiragana.fromChar(char)
}

fun Hiragana.changeVowelToChar(vowel: KanaVowel): Char {
    return changeVowel(vowel)!!.toChar()!!
}