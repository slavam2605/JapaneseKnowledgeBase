import java.io.File
import java.nio.charset.Charset

enum class ENAMClassificationCode(private val letterCode: String) {
    Surname("s"), PlaceName("p"), PersonName("u"), GivenName("g"),
    FemaleGivenName("f"), MaleGivenName("m"), FullPersonName("h"),
    ProductName("pr"), CompanyName("c"), OrganizationName("o"),
    Station("st"), WorkOfArt("wk");

    companion object {
        fun fromLetterCode(code: String): ENAMClassificationCode {
            for (value in values()) {
                if (value.letterCode == code)
                    return value
            }
            throw IllegalArgumentException("Unknown letter code: \"$code\"")
        }
    }
}

class ENAMEntry(
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

fun parseENAMDict(file: File): List<ENAMEntry> {
    return file.useLines(Charset.forName("EUC-JP")) { lines ->
        lines.drop(1).mapNotNull { line ->
            ENAMEntry.parse(line)
        }.toList()
    }
}