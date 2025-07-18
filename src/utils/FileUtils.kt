package utils

import java.io.File

fun getFileSizeString(file: File): String {
    val size = file.length().toDouble()
    // 900 is an arbitrary threshold, chosen to avoid displaying sizes like 1015 KB
    val (value, unit) = when {
        size < 900         -> size to "B"
        size < 1024 * 900  -> size / 1024 to "KB"
        else               -> size / (1024 * 1024) to "MB"
    }
    return "%.2f %s".format(value, unit)
}