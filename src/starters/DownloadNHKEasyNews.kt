package starters

import org.json.JSONArray
import org.json.JSONObject
import okhttp3.OkHttpClient
import okhttp3.Request
import org.jsoup.Jsoup
import org.jsoup.nodes.Document
import utils.PathConstants
import utils.resolveResource
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.Deflater
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

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

fun zipFolder(sourceFolder: File, outputZip: File) {
    ZipOutputStream(BufferedOutputStream(FileOutputStream(outputZip))).use { zipOut ->
        zipOut.setLevel(Deflater.BEST_COMPRESSION)
        sourceFolder.walkTopDown()
            .filter { it.isFile }
            .forEach { file ->
                val relativePath = sourceFolder.toPath().relativize(file.toPath()).toString()
                zipOut.putNextEntry(ZipEntry(relativePath))
                file.inputStream().use { input -> input.copyTo(zipOut) }
                zipOut.closeEntry()
            }
    }
}

fun unzipToFolder(zipFile: File, targetDir: File) {
    if (!targetDir.exists()) targetDir.mkdirs()

    var newCount = 0
    var replaceCount = 0
    ZipInputStream(FileInputStream(zipFile)).use { zipIn ->
        var entry = zipIn.nextEntry
        while (entry != null) {
            val outFile = File(targetDir, entry.name)
            if (entry.isDirectory) {
                outFile.mkdirs()
            } else {
                outFile.parentFile?.mkdirs()
                if (outFile.exists()) { replaceCount++ } else { newCount++ }
                FileOutputStream(outFile).use { output ->
                    zipIn.copyTo(output)
                }
            }
            zipIn.closeEntry()
            entry = zipIn.nextEntry
        }
    }

    println("Unzipped ${zipFile.name}\n" +
            "\t$newCount new files\n" +
            "\t$replaceCount replaced files")
}

fun getFileSizeString(file: File): String {
    val size = file.length().toDouble()
    val (value, unit) = when {
        size < 1024        -> size to "B"
        size < 1024 * 1024 -> size / 1024 to "KB"
        else               -> size / (1024 * 1024) to "MB"
    }
    return "%.2f %s".format(value, unit)
}

fun compressNewsArticles(folderName: String) {
    val sourceDir = resolveResource(folderName)
    val outputZip = resolveResource("$folderName.zip")
    if (!sourceDir.exists() || !sourceDir.isDirectory) {
        println("Folder not found: ${sourceDir.absolutePath}")
        return
    }

    zipFolder(sourceDir, outputZip)
    println("Packed news articles to ${outputZip.name}, resulting size: ${getFileSizeString(outputZip)}")
}

fun unzipOldArticles(folderName: String) {
    val zipFile = resolveResource("$folderName.zip")
    val targetDir = resolveResource(folderName)
    if (!zipFile.exists()) {
        println("Skipped unzipping old articles, no ${zipFile.name} is found")
        return
    }

    unzipToFolder(zipFile, targetDir)
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
    unzipOldArticles(PathConstants.nhkEasyNewsFolder)
    unzipOldArticles(PathConstants.nhkHardNewsFolder)

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

    compressNewsArticles(PathConstants.nhkEasyNewsFolder)
    compressNewsArticles(PathConstants.nhkHardNewsFolder)
}
