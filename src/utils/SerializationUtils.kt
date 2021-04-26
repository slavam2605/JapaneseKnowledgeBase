import java.util.*

fun <T> Iterable<T>.writeToString(separator: String, block: (T) -> String): String {
    return map(block).joinToString(separator) { it.toBase64() }
}

fun <T> readFromString(value: String, separator: String, block: (String) -> T): List<T> {
    val parts = value.split(separator)
    if (parts.size == 1 && parts[0] == "")
        return emptyList()

    return parts.map { it.fromBase64() }.map(block)
}

fun String.toBase64(): String {
    return Base64.getEncoder().encodeToString(toByteArray())
}

fun String.fromBase64(): String {
    return String(Base64.getDecoder().decode(this))
}