package starters

import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import utils.AnkiDataManager
import greek.GreekConjugations
import utils.PathConstants
import utils.resolveResource
import java.io.FileWriter
import java.io.IOException

private fun downloadWordForms(words: List<String>) {
    val existingWords = GreekConjugations.readConjugations()

    FileWriter(resolveResource(PathConstants.greekConjugations), true).use { writer ->
        for (word in words + listOf("θυμάμαι")) {
            if (existingWords.any { it.word == word || it.guessPresentForms().firstOrNull()?.contains(word) == true }) {
                println("Skipping word $word, it already exists in the database")
                continue
            }

            val url = "https://cooljugator.com/gr/$word"
            println("Processing URL: $url")

            val document = fetchDocumentTryBothB1(url)
            if (document != null) {
                try {
                    processPage(document, writer, word)
                    println("Finished processing URL: $url")
                } catch (e: Exception) {
                    println("Error while processing page from $url: ${e.message}")
                }
            } else {
                println("Failed to fetch document for URL: $url after retries.")
            }
        }
    }
}

fun fetchDocumentTryBothB1(url: String): Document? {
    val document = fetchDocumentWithRetries(url, retries = 3)
    if (document != null && document.location().endsWith("404") && url.endsWith("άω")) {
        val newUrl = url.take(url.length - 2) + "ώ"
        return fetchDocumentWithRetries(newUrl, retries = 3)
    }

    return document
}

fun fetchDocumentWithRetries(url: String, retries: Int): Document? {
    var attempt = 0
    val timeoutMillis = 10_000

    while (attempt < retries) {
        try {
            println("Attempt ${attempt + 1} to fetch URL: $url")

            val document = Jsoup.connect(url)
                .userAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36")
                .referrer("https://www.google.com/")
                .timeout(timeoutMillis)
                .followRedirects(true)
                .get()

            println("Successfully fetched document for URL: $url")
            return document
        } catch (e: IOException) {
            println("Failed to fetch document for URL: $url on attempt ${attempt + 1}. Error: ${e.message}")
        }

        attempt++
        Thread.sleep(2_000L)
    }
    return null
}

private fun Document.getContentById(id: String): String? {
    val rootElement = getElementById(id) ?: return null
    val metaForm = rootElement.getElementsByClass("meta-form").firstOrNull() ?: return null
    return metaForm.html().trim()
}

private fun processPage(document: Document, writer: FileWriter, word: String) {
    val presentIds = listOf("infinitive0") + (2..6).map { "present$it" }
    val futureIds = (1..6).map { "future$it" }
    val simplePastIds = (1..6).map { "pastperfect$it" }

    writer.write(">>>$word\n")
    writer.write("present|" + presentIds.joinToString("|") { document.getContentById(it) ?: "<null>" } + "\n")
    writer.write("aplos_melodas|" + futureIds.joinToString("|") { document.getContentById(it) ?: "<null>" } + "\n")
    writer.write("aoristos|" + simplePastIds.joinToString("|") { document.getContentById(it) ?: "<null>" } + "\n")
}

private fun fixWordString(word: String): String {
    return word.replace("<br>", "\n").trim()
}

private fun getAllAnkiVerbs(): List<String> {
    val excludeList = setOf("εδώ", "γύρω", "απέξω")
    val b1VerbsPattern = "([^,]*)άω, *\\1ώ".toRegex()
    val b1TypoPattern = "([^,]*), *\\1".toRegex()
    val egoPattern = "\\(εγώ\\) (.*)".toRegex()
    val notes = AnkiDataManager.readDeck(AnkiDataManager.PES_TO_ELLINIKA_DECK)
    return notes.filter { note ->
        val word = fixWordString(note.fields[0])
        (word.endsWith("ω") || word.endsWith("ώ") || word.endsWith("μαι")) &&
                !note.tags.map { it.trim() }.any { it == "aplos_melodas" || it == "simple_past" } &&
                !word.startsWith("θα ") &&
                word !in excludeList
    }.map {
        val word = fixWordString(it.fields[0])
        b1VerbsPattern.matchEntire(word)?.let {
            return@map it.groupValues[1] + "άω"
        }
        b1TypoPattern.matchEntire(word)?.let {
            return@map it.groupValues[1]
        }
        egoPattern.matchEntire(word)?.let {
            return@map it.groupValues[1]
        }


        word
    }.filter {
        !it.contains(" ")
    }.distinct()
}

fun main() {
    val verbs = getAllAnkiVerbs()
    downloadWordForms(verbs)
}