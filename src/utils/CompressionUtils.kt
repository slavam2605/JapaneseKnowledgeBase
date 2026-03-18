package utils

import java.io.BufferedOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.Deflater
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

fun zipFile(sourceFile: File, outputZip: File) {
    ZipOutputStream(BufferedOutputStream(FileOutputStream(outputZip))).use { zipOut ->
        zipOut.setLevel(Deflater.BEST_COMPRESSION)
        val entryName = sourceFile.name
        zipOut.putNextEntry(ZipEntry(entryName))
        sourceFile.inputStream().use { input -> input.copyTo(zipOut) }
        zipOut.closeEntry()
    }
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

fun unzipToFolder(zipFile: File, targetDir: File): UnzipResult {
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

    return UnzipResult(newCount, replaceCount)
}

fun unzipSingleFile(zipFile: File, targetFile: File): Boolean {
    ZipInputStream(FileInputStream(zipFile)).use { zipIn ->
        val entry = zipIn.nextEntry
        return if (entry != null && !entry.isDirectory) {
            targetFile.parentFile?.mkdirs()
            FileOutputStream(targetFile).use { output ->
                zipIn.copyTo(output)
            }
            true
        } else {
            false
        }
    }
}

fun compressResource(fileName: String, deleteOriginal: Boolean = false) {
    val sourceFile = resolveResource(fileName)
    val outputZip = resolveResource("$fileName.zip")
    if (!sourceFile.exists()) {
        println("File not found: ${sourceFile.absolutePath}")
        return
    }

    if (sourceFile.isDirectory) {
        zipFolder(sourceFile, outputZip)
        println("Packed folder ${sourceFile.name} to ${outputZip.name}, resulting size: ${getFileSizeString(outputZip)}")
    } else {
        zipFile(sourceFile, outputZip)
        println("Packed file ${sourceFile.name} to ${outputZip.name}, resulting size: ${getFileSizeString(outputZip)}")
    }

    if (deleteOriginal && sourceFile.exists()) {
        if (sourceFile.isDirectory) {
            sourceFile.deleteRecursively()
        } else {
            sourceFile.delete()
        }
        println("Deleted original: ${sourceFile.name}")
    }
}

fun uncompressResource(fileName: String, verbose: Boolean = true): Boolean {
    val zipFile = resolveResource("$fileName.zip")
    val targetFile = resolveResource(fileName)
    
    if (!zipFile.exists()) {
        if (verbose) println("Skipped uncompressing $fileName, no ${zipFile.name} found")
        return false
    }

    // Try to determine if it's a single file or folder from the zip contents
    val isFolder = ZipInputStream(FileInputStream(zipFile)).use { zipIn ->
        var entryCount = 0
        var entry = zipIn.nextEntry
        while (entry != null) {
            entryCount++
            if (entryCount > 1 || entry.isDirectory) return@use true
            entry = zipIn.nextEntry
        }
        false
    }

    return if (isFolder) {
        val result = unzipToFolder(zipFile, targetFile)
        if (verbose) {
            println("Unzipped ${zipFile.name}")
            println("\t${result.newCount} new files")
            println("\t${result.replaceCount} replaced files")
        }
        true
    } else {
        val success = unzipSingleFile(zipFile, targetFile)
        if (verbose && success) {
            println("Unzipped ${zipFile.name} to ${targetFile.name}")
        }
        success
    }
}

data class UnzipResult(val newCount: Int, val replaceCount: Int)
