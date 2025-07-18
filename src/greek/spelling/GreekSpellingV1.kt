package greek.spelling

import utils.AnkiNote

open class GreekSpellingV1 : GreekSpelling() {
    override fun getSusIota(s: String): List<SusResult> {
        val regex = "(?:^|[^οα])([ιί])(?!\\b)".toRegex()
        return regex.findAll(s).map { result ->
            SusResult(result.groups[1]!!.range, SusLetter.I)
        }.toList()
    }

    override fun getSusOmicron(s: String): List<SusResult> {
        val regex = "[οό](?!\\b)(?![ιίυύ])".toRegex()
        return regex.findAll(s).mapNotNull { result ->
            if (result.range == 0..0 &&
                (s.startsWith("οι ") || s.startsWith("ο "))
            ) {
                // "οι" or "ο" article
                return@mapNotNull null
            }
            SusResult(result.range, SusLetter.O)
        }.toList()
    }

    override fun getSusOmega(s: String): List<SusResult> {
        val regex = "[ωώ](?!\\b)".toRegex()
        return regex.findAll(s).map { result ->
            SusResult(result.range, SusLetter.O)
        }.toList()
    }

    override fun getSusIta(s: String, tags: List<String>): List<SusResult> {
        val regex = "[ηή](?!\\b)".toRegex()
        return regex.findAll(s).mapNotNull { result ->
            SusResult(result.range, SusLetter.I)
        }.toList()
    }

    override fun getSusUpsilon(s: String): List<SusResult> {
        val regex = "(?:^|[^αοε])([υύ])".toRegex()
        return regex.findAll(s).map { result ->
            SusResult(result.groups[1]!!.range, SusLetter.I)
        }.toList()
    }

    override fun getSusOi(s: String): List<SusResult> {
        val regex = "ο[ιί]".toRegex()
        return regex.findAll(s).mapNotNull { result ->
            if (result.range == 0..1 && s.startsWith("οι ")) {
                // "οι" article
                return@mapNotNull null
            }
            SusResult(result.range, SusLetter.I)
        }.toList()
    }

    override fun getSusEi(s: String): List<SusResult> {
        val regex = "ε[ιί]".toRegex()
        return regex.findAll(s).mapNotNull { result ->
            if (result.range == s.length - 3..s.length - 2 && s.endsWith("εις")) {
                return@mapNotNull null
            }
            SusResult(result.range, SusLetter.I)
        }.toList()
    }

    protected fun String.isSus(tags: List<String>): List<SusResult> {
        return getSusIota(this) + getSusOmicron(this) +
                getSusOmega(this) + getSusIta(this, tags) +
                getSusUpsilon(this) + getSusOi(this) +
                getSusEi(this)
    }

    private val ignoredWords = listOf(
        "της", "του", "των", "Τους", "Τον", "Τις", "Την", "Μου", "Σου", "Του", "Της", "θα"
    ).map { "\\b$it\\b".toRegex() }

    private fun String.isIgnored(): Boolean {
        return when {
            ignoredWords.any { it.find(this) != null } -> true
            split(' ').size > 2 -> {
                if ("ο .*\\bη ".toRegex().find(this) != null) {
                    return false
                }
                true
            }

            else -> false
        }
    }

    protected fun smartReplace(word: String, susResults: List<SusResult>, customReplacement: String? = null): String {
        val array = IntArray(word.length)
        for (i in word.indices) {
            array[i] = word[i].code
        }
        for (i in susResults.indices) {
            for (j in susResults[i].range) {
                array[j] = -i
            }
        }
        val maxLength = 300
        val charResult = CharArray(maxLength)
        var curIndex = 0
        for (i in word.indices) {
            if (array[i] > 0) {
                charResult[curIndex] = array[i].toChar()
                curIndex++
                continue
            }
            if (i == 0 || array[i - 1] != array[i]) {
                val susIndex = -array[i]
                val sub = customReplacement ?: "{{c1::${word.substring(susResults[susIndex].range)}:: }}"
                sub.forEach { char ->
                    charResult[curIndex] = char
                    curIndex++
                }
                continue
            }
        }

        val replWord = String(charResult, 0, curIndex)
        return replWord
    }

    private fun transformWord(word: String): String {
        var word = word

        // Replace double articles
        word = word.replace("[οo], η".toRegex(), "ο")

        // Remove all brackets
        word = word.replace("\\(.*\\)".toRegex(), "")

        // Remove all <span> tags
        word = "<span .*>(.*)</span>".toRegex().replace(word) { it.groups[1]!!.value }

        // Replace all HTML line breaks
        word = word.replace("(<br>)+".toRegex(), ", ")

        // Join all lines
        word = word.replace("\n", " ")

        // Normalize commas
        word = " *,( *)".toRegex().replace(word) {
            val endSpaces = it.groups[1]?.value
            "," + if (endSpaces == null || endSpaces.isEmpty()) "" else " "
        }

        // Keep one of multiple gender forms
        val adjRegexes = listOf(
            "(.+)[οό]ς.*\\1ι?[ηήαά](.*\\1[οό])?".toRegex(),
            "(.+)[οό]ς.*\\1[οό]ς\\$".toRegex(),
            "(.+)[ηή]ς.*\\1[ηή]ς.*\\1[εέ]ς".toRegex(),
            "(.+)[υύ]ς.*\\1ι[αά].*\\1[υύ]".toRegex()
        )
        val excludedRoots = setOf(
            "κ", "δικ", "τ", "στ", "λ", "ρ",
            "ν", "ρκ", "φ", "ικ", "τ"
        )
        adjRegexes.forEach { regex ->
            regex.find(word)?.let {
                val range = it.groups[1]!!.range
                if (word.substring(range) in excludedRoots) return@let
                // Good short words:
                // όλος, όλη, όλο -> όλος
                // όσος, όση, όσο -> όσος
                // ωμός, ωμή, ωμό -> ωμός
                // if (range.count() == 5) {
                //     println("$word -> ${word.substring(range.first..range.last + 2)}")
                // }
                word = word.substring(range.first..range.last + 2)
            }
        }

        val goodWords = listOf(
            "Οκτώβριος", "ευρώ", "κορώνα"
        )
        goodWords.forEach { goodWord ->
            if (word.contains(goodWord)) {
                word = goodWord
            }
        }

        return word
    }

    override fun transformTranslation(s: String): String {
        return s
    }

    override fun getSpellings(notes: List<AnkiNote>): Map<AnkiNote, String> {
        var count = 0
        val countCount = mutableMapOf<Int, Int>()
        val visited = hashSetOf<String>()
        val result = mutableMapOf<AnkiNote, String>()
        for (note in notes) {
            if (note.fields.size < 5) continue
            val (preWord, _, translation, _, image) = note.fields
            val word = transformWord(preWord).trim()
            if (!visited.add(word)) {
                continue
            }

            val susResults = word.isSus(note.tags)
            if (word.isIgnored() || susResults.isEmpty()) {
                if (word.isIgnored()) {
//                println(word)
                }
                continue
            }

            countCount.compute(susResults.size) { _, o -> (o ?: 0) + 1 }
            val replWord = smartReplace(word, susResults)
//        println("$word -> $replWord")
            result[note] = "${replWord.replace("\n", "<br>")}<br><br>${transformTranslation(translation)}<br><br>$image"
            count++
        }

//    println()
//    println("Total: $count words")
        countCount.keys.sorted().forEach { k ->
//        println("\tWords with $k hidden parts: ${countCount[k]}")
        }
        return result
    }
}