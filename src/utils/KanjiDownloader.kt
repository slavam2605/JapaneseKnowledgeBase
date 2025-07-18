package utils

import getDocumentFromUrl
import getNextDelayForDownload
import org.json.JSONArray
import org.json.JSONObject
import org.jsoup.nodes.Document
import java.io.File

fun downloadKanjiInfo(file: File, vararg kanjiToDownload: Char) {
    val fileText = if (file.exists()) file.readText() else ""
    val json = if (fileText.isNotBlank()) JSONObject(fileText) else JSONObject()

    fun saveJsonFile() {
        print("Saving json file... ")
        file.writer().use {
            json.write(it, 4, 0)
        }
        println("done, file size is ${getFileSizeString(file)}")
    }

    for (kanjiIndex in kanjiToDownload.indices) {
        val kanji = kanjiToDownload[kanjiIndex]
        val existingValue = json.opt("$kanji")
        if (existingValue != null) {
            println("Skipping kanji: $kanji")
            continue
        }

        val document = getKanjiInfoPage(kanjiToDownload.first()) ?: run {
            System.err.println("Failed to download: $kanji")
            continue
        }

        println("Downloaded kanji ${kanjiIndex + 1} / ${kanjiToDownload.size}: $kanji")
        val mainReadings = document.select(".kanji-details__main-readings")
        val kunYomi = mainReadings.select(".kun_yomi").select("a").map { it.text() }
        val onYomi = mainReadings.select(".on_yomi").select("a").map { it.text() }
        val kanjiObject = JSONObject(mapOf(
            "kun_yomi" to JSONArray(kunYomi),
            "on_yomi" to JSONArray(onYomi)
        ))
        json.put("$kanji", kanjiObject)

        if (kanjiIndex % 20 == 0) {
            saveJsonFile()
        }
    }

    saveJsonFile()
}

fun downloadKanjiList(file: File, tag: String) {
    val result = mutableListOf<Char>()
    val maxPageCount = 1000
    println("Start downloading of kanji for tag $tag")
    for (page in 1 .. maxPageCount) {
        println("Fetching page $page...")
        val kanjiList = getKanjiPage(tag, page)?.parseKanjiPage() ?: emptyList()
        if (kanjiList.isEmpty())
            break

        result.addAll(kanjiList)
        Thread.sleep(getNextDelayForDownload())
    }
    file.bufferedWriter().use {
        val allKanji = result.joinToString(separator = "") { kanji -> "$kanji" }
        it.write(allKanji)
    }
}

private fun Document.parseKanjiPage(): List<Char> {
    val blocks = select("div.kanji_light_block div.entry.kanji_light div.kanji_light_content")
    return blocks.map { block ->
        val char = block.select("div.literal_block span.character a").single()
        char.text().trim().single()
    }
}

private fun getKanjiInfoPage(kanji: Char) =
    getDocumentFromUrl("https://jisho.org/search/$kanji%20%23kanji")

private fun getKanjiPage(tag: String, page: Int) =
    getDocumentFromUrl("https://jisho.org/search/%23kanji%20%23$tag?page=$page")