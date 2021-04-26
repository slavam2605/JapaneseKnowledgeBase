import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import java.io.IOException
import java.util.*

fun getDocumentFromUrl(url: String): Document? {
    return try {
        Jsoup.connect(url).get()
    } catch (e: IOException) {
        System.err.println("Failed to get url: $url")
        null
    }
}

private val delayRandom = Random()
fun getNextDelayForDownload(): Long {
    return (300 + delayRandom.nextInt(200)).toLong()
}