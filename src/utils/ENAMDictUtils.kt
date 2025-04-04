package utils

import java.io.File
import java.nio.charset.Charset
import kotlin.time.measureTime

class ENAMDict(file: File) {
    private val entries = hashMapOf<String, MutableList<ENAMEntry>>()

    init {
        val duration = measureTime {
            file.useLines(Charset.forName("EUC-JP")) { lines ->
                lines.drop(1).forEach { line ->
                    val entry = ENAMEntry.parse(line) ?: run {
                        System.err.println("Failed to parse ENAM entry: $line")
                        return@forEach
                    }
                    val entryList = entries.getOrPut(entry.text) { mutableListOf() }
                    entryList.add(entry)
                }
            }
        }
        println("ENAMDICT is loaded in ${duration.inWholeMilliseconds} ms")
    }

    operator fun get(text: String): List<ENAMEntry>? = entries[text]
}

enum class ENAMClassificationCode(private val letterCode: String, val description: String) {
    Surname("s", "surname"),
    PlaceName("p", "place name"),
    PersonName("u", "person name, either given or surname, as-yet unclassified"),
    GivenName("g", "given name, as-yet not classified by sex"),
    FemaleGivenName("f", "female given name"),
    MaleGivenName("m", "male given name"),
    FullPersonName("h", "full (usually family plus given) name of a particular person"),
    ProductName("pr", "product name"),
    CompanyName("c", "company name"),
    OrganizationName("o", "organization name"),
    Station("st", "stations"),
    WorkOfArt("wk", "work of literature, art, film, etc.");

    companion object {
        fun fromLetterCode(code: String): ENAMClassificationCode {
            for (value in entries) {
                if (value.letterCode == code)
                    return value
            }
            throw IllegalArgumentException("Unknown letter code: \"$code\"")
        }
    }
}

data class ENAMEntry(
    val text: String,
    val reading: String,
    val codes: List<ENAMClassificationCode>,
    val meaning: String
) {
    companion object {
        private val entryPattern = "(.*?) (\\[(.*)] )?/(\\((.*?)\\) )?(.*)/".toPattern()

        fun parse(line: String): ENAMEntry? {
            val matcher = entryPattern.matcher(line)
            if (!matcher.matches()) {
                System.err.println("Not parsed: $line")
                return null
            }

            val text = matcher.group(1)
            val reading = matcher.group(3) ?: ""
            val codes = matcher.group(5)
            val meaning = matcher.group(6)
            return ENAMEntry(
                text,
                reading,
                codes?.split(',')?.map { ENAMClassificationCode.fromLetterCode(it) } ?: emptyList(),
                meaning
            )
        }
    }
}