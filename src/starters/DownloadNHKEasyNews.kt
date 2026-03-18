package starters

import org.json.JSONArray
import org.json.JSONObject
import okhttp3.OkHttpClient
import okhttp3.Request
import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import utils.PathConstants
import utils.compressResource
import utils.resolveResource
import utils.uncompressResource
import java.io.File

private class DoNotRetry : Exception()

fun downloadUrl(url: String): Result<String?> {
    val client = OkHttpClient()
    val request = Request.Builder().url(url).build()

    client.newCall(request).execute().use { response ->
        if (!response.isSuccessful) {
            println("Failed to download: ${response.code}")
            // Do not retry 404
            return Result.failure(if (response.code == 404) DoNotRetry() else Exception())
        }
        return Result.success(response.body?.string())
    }
}

fun downloadPage(url: String): Result<Document?> {
    return downloadUrl(url).map {
        Jsoup.parse(it ?: return@map null)
    }
}

fun <T> retryWithBackoff(retries: Int = 5, initialDelayMs: Long = 1000L, factor: Double = 2.0, block: () -> Result<T>): T? {
    var currentDelay = initialDelayMs
    repeat(retries - 1) {
        val result = block()
        if (result.isSuccess) return result.getOrNull()
        if (result.exceptionOrNull() is DoNotRetry) return null

        Thread.sleep(currentDelay)
        currentDelay = (currentDelay * factor).toLong()
    }
    return block().getOrNull() // Final attempt
}

fun getNewsListJson(): JSONObject {
    val resourceFile = resolveResource("nhk-news-list.json")

    // Update the news list
    val newsListUrl = "https://www3.nhk.or.jp/news/easy/news-list.json"
    val updatedJson = retryWithBackoff { downloadUrl(newsListUrl) }
    if (updatedJson != null) {
        resourceFile.writeText(updatedJson)
        println("Updated the news list from $newsListUrl")
    } else {
        System.err.println("Failed to update the news list, using the old one from resources")
    }

    return JSONArray(resourceFile.readText()).getJSONObject(0)
}


fun downloadNews(
    data: List<String>,
    targetDir: String,
    urlGetter: (data: String) -> String,
    fileNameGetter: (data: String) -> String
) {
    var successCount = 0
    var skippedCount = 0
    var errorCount = 0
    for (articleData in data) {
        val resourceFile = resolveResource("$targetDir/${fileNameGetter(articleData)}")
        if (resourceFile.exists() && resourceFile.length() > 0) {
            skippedCount++
            continue
        }

        val newsLink = urlGetter(articleData)
        val document = retryWithBackoff { downloadPage(newsLink) } ?: run {
            System.err.println("Failed to download: $newsLink")
            errorCount++
            continue
        }

        resourceFile.writeText(document.html())

        successCount++
        println("Downloaded $successCount of ${data.size}: $newsLink")
    }

    println("Processed ${data.size} news articles:\n" +
            "\tdownloaded $successCount\n" +
            "\tskipped $skippedCount\n" +
            "\tfailed to download $errorCount")
}

fun main() {
    uncompressResource(PathConstants.nhkEasyNewsFolder)
    uncompressResource(PathConstants.nhkHardNewsFolder)

    val newsListJson = getNewsListJson()
    val newsIds = newsListJson.keySet().flatMap { keyDate ->
        (newsListJson[keyDate] as JSONArray).map { (it as JSONObject)["news_id"] as String }
    }
    val originalNewsUrls = newsListJson.keySet().flatMap { keyDate ->
        (newsListJson[keyDate] as JSONArray).map {
            val rawUrl = (it as JSONObject)["news_web_url"] as String
            rawUrl.substringBeforeLast("#")
        }
    }

    // Download easy news
    downloadNews(
        data = newsIds,
        targetDir = PathConstants.nhkEasyNewsFolder,
        urlGetter = { "https://www3.nhk.or.jp/news/easy/$it/$it.html" },
        fileNameGetter = { "$it.html" }
    )

    // Download hard news
    downloadNews(
        data = originalNewsUrls,
        targetDir = PathConstants.nhkHardNewsFolder,
        urlGetter = { it },
        fileNameGetter = { it.substringAfterLast('/') }
    )

    compressResource(PathConstants.nhkEasyNewsFolder)
    compressResource(PathConstants.nhkHardNewsFolder)
}
