package smart_parser

data class ParserState<T>(
    val value: T,
    val index: Int
)

fun <T, R> StateList<T>.valueMap(transform: (T) -> R) =
    map { ParserState(transform(it.value), it.index) }