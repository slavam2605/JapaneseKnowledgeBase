@file:Suppress("NonAsciiCharacters")

package utils

fun слово(n: Int, includeNumber: Boolean = false): String {
    return (if (includeNumber) "$n " else "") + when (n % 10) {
        1 -> "слово"
        2, 3, 4 -> "слова"
        0, 5, 6, 7, 8, 9 -> "слов"
        else -> error(n)
    }
}