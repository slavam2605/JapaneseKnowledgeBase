package parser

import dict.AllWordsList
import utils.isKana
import utils.isKanji
import utils.iteratePartitions

class JapaneseLexer(val text: String, val words: AllWordsList) {
    private var index = 0

    private fun isWordExists(word: String) =
        words.getWords(word).isNotEmpty()

    private fun tryExtend(chunk: String): Int {
        var localIndex = index
        var maxGoodIndex = if (isWordExists(chunk)) localIndex else -1
        while (localIndex < text.length && localIndex - index < MAX_WORD_LENGTH) {
            val candidate = chunk + text.substring(index .. localIndex)
            val allCandidates = JapaneseLemmatizer.toNormalForm(candidate)
            localIndex++
            if (allCandidates.any { isWordExists(it) }) {
                maxGoodIndex = localIndex
            }
        }
        return maxGoodIndex
    }

    private fun trySplitWord(chunk: String): List<JapaneseToken>? {
        val results = mutableListOf<Pair<List<String>, Int>>()
        for (wordCount in 1..chunk.length) {
            iteratePartitions(wordCount - 1, chunk.length - 1) { partition ->
                var currentIndex = 0
                val words = mutableListOf<String>()
                for (len in partition) {
                    words.add(chunk.substring(currentIndex until currentIndex + len))
                    currentIndex += len
                }
                val lastChunk = chunk.substring(currentIndex)
                for (word in words) {
                    if (!isWordExists(word))
                        return@iteratePartitions
                }

                val nextIndex = tryExtend(lastChunk)
                if (nextIndex < 0)
                    return@iteratePartitions

                val chunkStart = index - chunk.length
                val lastWord = text.substring(chunkStart + currentIndex, nextIndex)
                words.add(lastWord)
                results.add(words to nextIndex)
            }

            if (results.isNotEmpty())
                break
        }
        return if (results.size == 1) {
            val (words, nextIndex) = results.single()
            index = nextIndex
            words.mapIndexed { index, w ->
                if (index < words.size - 1) {
                    JapaneseToken.WordToken(w, this.words.getWords(w))
                } else {
                    val lemmas = JapaneseLemmatizer.toNormalForm(w)
                    val entries = lemmas.filter { isWordExists(it) }.flatMap { this.words.getWords(it) }
                    JapaneseToken.WordToken(w, entries)
                }
            }
        } else {
            System.err.println("Variants for the word $chunk: ${results.joinToString()}")
            null
        }
    }

    private fun finishKanjiSequence(chunk: String): List<JapaneseToken> {
        return trySplitWord(chunk) ?: listOf(JapaneseToken.UnknownWordToken(chunk))
    }

    private fun getSequence(): List<JapaneseToken> {
        val first = text[index++]
        val builder = StringBuilder().append(first)
        return when {
            first.isKanji -> {
                while (index < text.length && text[index].isKanji) {
                    builder.append(text[index++])
                }
                finishKanjiSequence(builder.toString())
            }
            first.isKana -> {
                while (index < text.length && text[index].isKana) {
                    builder.append(text[index++])
                }
                listOf(JapaneseToken.HiraganaToken(builder.toString()))
            }
            first == '\r' -> emptyList()
            else -> listOf(JapaneseToken.OtherToken(builder.toString()))
        }
    }

    fun getTokens(): List<JapaneseToken> {
        val start = System.currentTimeMillis()
        val result = mutableListOf<JapaneseToken>()
        while (index < text.length) {
            val nextChunk = getSequence()
            result.addAll(nextChunk)
        }
        println("Lexer took: ${System.currentTimeMillis() - start} ms")
        return result
    }

    companion object {
        const val MAX_WORD_LENGTH = 10
    }
}