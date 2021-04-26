import org.jsoup.nodes.Document
import java.io.File

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

private fun getKanjiPage(tag: String, page: Int) =
    getDocumentFromUrl("https://jisho.org/search/%23kanji%20%23$tag?page=$page")