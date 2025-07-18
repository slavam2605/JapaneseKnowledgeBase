package server.pages

import dict.AllWordsList
import dict.WordEntry
import io.ktor.server.application.ApplicationCall
import kotlinx.html.BODY
import kotlinx.html.div
import kotlinx.html.h3
import kotlinx.html.rt
import kotlinx.html.ruby
import org.jsoup.Jsoup
import parser.JapaneseLexer
import parser.JapaneseToken
import utils.PathConstants
import utils.ReadingInfo
import utils.getReadingInfoForKanji
import utils.isKanji
import utils.resolveResource
import java.io.File
import kotlin.math.roundToInt

class NHKNewsKanjiStatsPage(
    val dataset: Map<Char, List<WordEntry>>,
    val allWords: AllWordsList
) : PageBuilderBase("/nhk_news_kanji_stats") {
    companion object {
        private val ExplicitNull = ArrayList<ReadingPair>()
    }
    private val splitCache = mutableMapOf<ReadingPair, List<ReadingPair>>()
    private val missedKanjiReadingsSet = mutableSetOf<Char>()

    private fun processHardNewsArticle(file: File, readings: MutableList<ReadingPair>) {
        val document = Jsoup.parse(file)
        val articleText = document.select(".body-text").text()
        val lexer = JapaneseLexer(articleText, allWords)
        val tokens = lexer.getTokens()
        tokens.filterIsInstance<JapaneseToken.WordToken>().forEach { token ->
            val singleWord = token.possibleWords.singleOrNull()
            if (singleWord != null) {
                readings.add(ReadingPair(singleWord.text, singleWord.getReading(), isUncertain = false))
            } else {
                // TODO [MULTIPLE_READINGS] 見直し: みなおし, みなおす
                //      [MULTIPLE_READINGS] 伝えて: つたえる, つたう
                //      [MULTIPLE_READINGS] 改めて: あらためて, あらためる, あらたむ
                // System.err.println("[MULTIPLE_READINGS] ${token.text}: ${token.possibleWords.joinToString { it.getReading() }}")
                token.possibleWords.forEach {
                    readings.add(ReadingPair(it.text, it.getReading(), isUncertain = true))
                }
            }
        }
    }

    private fun processNewsArticle(file: File, readings: MutableList<ReadingPair>) {
        val document = Jsoup.parse(file)
        val ruby = document.select(".article-body").select("ruby")
        ruby.forEach { rubyElement ->
            val spanFreeRuby = "<span.*?>(.*?)</span>".toRegex().replace(rubyElement.html()) { it.groupValues[1] }
            "([^>]*)<rt>(.*?)</rt>".toRegex().findAll(spanFreeRuby).forEach { match ->
                val kanji = match.groupValues[1]
                val reading = match.groupValues[2]
                readings.add(ReadingPair(kanji, reading, isUncertain = false))
            }
        }
    }

    private fun guessReadingSplit(readingPair: ReadingPair): List<ReadingPair>? {
        splitCache[readingPair]?.let {
            return if (it === ExplicitNull) null else it
        }
        return guessReadingSplit0(readingPair).also {
            splitCache[readingPair] = it ?: ExplicitNull
        }
    }

    class ReadingVariation(val reading: String, val originalReading: String) {
        constructor(reading: String) : this(reading, reading)
    }

    private fun guessReadingSplit0(readingPair: ReadingPair): List<ReadingPair>? {
        val (kanjiWord, reading, isUncertain) = readingPair
        var rightIndex = 0
        val result = mutableListOf<ReadingPair>()
        outer@ for (leftIndex in kanjiWord.indices) {
            if (rightIndex >= reading.length) {
                System.err.println("Failed to match kanji reading for $kanjiWord in $reading: extra kanji suffix ${kanjiWord.substring(leftIndex)}")
                return null
            }

            val leftChar = kanjiWord[leftIndex]
            if (!leftChar.isKanji) {
                // Should match the same symbol in the reading
                val rightChar = reading[rightIndex]
                if (leftChar != rightChar) {
                    return null
                }
                result.add(ReadingPair(leftChar.toString(), rightChar.toString(), false))
                rightIndex++
                continue
            }

            // Try to match the kanji reading
            val kanjiReadings = getReadingInfoForKanji(leftChar, dataset)
            // TODO download kanji readings info and if it contains both, for example, fu and bu, do not mark it as a variation
            val allReadings = kanjiReadings.commonReadings.flatMap {
                when (it) {
                    is ReadingInfo.SingleReading -> listOf(ReadingVariation(it.reading))
                    is ReadingInfo.ReadingCollection -> listOf(ReadingVariation(it.mainReading.reading)) +
                            it.variations.map { v -> ReadingVariation(v.reading, it.mainReading.reading) }
                }
            }.sortedByDescending { it.reading.length }
            for (singleReading in allReadings) {
                if (reading.startsWith(singleReading.reading, rightIndex)) {
                    rightIndex += singleReading.reading.length
                    result.add(ReadingPair(leftChar.toString(), singleReading.originalReading, isUncertain))
                    continue@outer
                }
            }

            if (allReadings.isEmpty() && leftChar !in dataset) {
                System.err.println("No readings found for '$leftChar'")
                missedKanjiReadingsSet.add(leftChar)
            } else {
                System.err.println("Failed to match kanji reading for $kanjiWord in $reading: $leftChar")
            }
            return null
        }

        if (rightIndex != reading.length) {
            System.err.println("Failed to match kanji reading for $kanjiWord in $reading: unmatched suffix ${reading.substring(rightIndex)}")
            return null
        }
        return result
    }

    private data class ReadingPair(val kanji: String, val reading: String, val isUncertain: Boolean)

    private fun collectStats(): List<KanjiStats> {
        val readings = mutableListOf<ReadingPair>()
        resolveResource(PathConstants.nhkEasyNewsFolder).listFiles().forEach {
            processNewsArticle(it, readings)
        }
        resolveResource(PathConstants.nhkHardNewsFolder).listFiles().forEach {
            processHardNewsArticle(it, readings)
        }
        val splitReadings = readings.mapNotNull {
            guessReadingSplit(it)
        }
        if (missedKanjiReadingsSet.isNotEmpty()) {
            println("Set of missed readings: ${missedKanjiReadingsSet.joinToString { "'$it'" }}")
        }

        val usageMap = mutableMapOf<String, MutableMap<String, Pair<Int, Int>>>()
        splitReadings.flatMap { it }.forEach { (kanji, reading, isUncertain) ->
            if (kanji.length != 1 || !kanji.first().isKanji) return@forEach
            val kanjiUsageMap = usageMap.getOrPut(kanji) { mutableMapOf() }
            kanjiUsageMap.compute(reading) { _, pair ->
                val pair = pair ?: (0 to 0)
                if (isUncertain) pair.copy(second = pair.second + 1) else pair.copy(first = pair.first + 1)
            }
        }

        return usageMap.map { entry ->
            // TODO sum is more than 100%
            val totalSize = entry.value.values.sumOf { it.first + it.second }
            KanjiStats(
                entry.key,
                entry.value.map { (reading, count) ->
                    reading to (count.first.toDouble() / totalSize to (count.first + count.second).toDouble() / totalSize)
                }
            )
        }
    }

    override fun BODY.buildPage(call: ApplicationCall) {
        val stats = collectStats()
        h3 { +"NHK Easy News Kanji Stats" }
        stats.forEach { stat ->
           div {
               +"${stat.kanji}: "
               stat.readings.forEach {
                   ruby {
                       +"${it.first}, "
                       rt {
                           val from = (it.second.first * 100).roundToInt()
                           val to = (it.second.second * 100).roundToInt()
                           if (from == to) {
                               +"$from%"
                           } else {
                               +"[$from% - $to%]"
                           }
                       }
                   }
               }
           }
        }
    }

    private data class KanjiStats(
        val kanji: String,
        val readings: List<Pair<String, Pair<Double, Double>>>
    )
}