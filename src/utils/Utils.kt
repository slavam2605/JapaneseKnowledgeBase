package utils

import java.io.File

fun resolveResource(fileName: String): File {
    return File("resources").resolve(fileName)
}

operator fun <T> List<T>.component6(): T {
    return get(5)
}

operator fun <T> List<T>.component7(): T {
    return get(6)
}

fun iteratePartitions(count: Int, sum: Int, block: (List<Int>) -> Unit) {
    val partitions = mutableListOf<Int>().apply {
        for (i in 0 until count) {
            add(1)
        }
    }

    fun next(): Boolean {
        var currentIndex = partitions.lastIndex
        if (currentIndex < 0)
            return false

        partitions[currentIndex]++
        while (currentIndex >= 0 && partitions.sum() > sum) {
            partitions[currentIndex] = 1
            currentIndex--
            if (currentIndex < 0)
                return false

            partitions[currentIndex]++
        }
        return true
    }

    do {
        block(partitions)
    } while (next())
}