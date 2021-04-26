package smart_parser.grammar

import dict.JMDict
import smart_parser.*

typealias ParseFunction<T> = SmartParser.(index: Int) -> StateList<T>

fun <T1, T2, R> SmartParser.parseSequence(index: Int, f1: ParseFunction<T1>, f2: ParseFunction<T2>, transform: (T1, T2) -> R): StateList<R> {
    return f1(index).flatMap { (r1, nextIndex) ->
        f2(nextIndex).valueMap { transform(r1, it) }
    }
}

fun <T1, T2, T3, R> SmartParser.parseSequence(index: Int, f1: ParseFunction<T1>, f2: ParseFunction<T2>, f3: ParseFunction<T3>, transform: (T1, T2, T3) -> R): StateList<R> {
    return f1(index).flatMap { (r1, nextIndex) ->
        f2(nextIndex).flatMap { (r2, nextNextIndex) ->
            f3(nextNextIndex).valueMap { transform(r1, r2, it) }
        }
    }
}

fun stringParser(target: String): ParseFunction<String> {
    return resultFunc@ { index ->
        if (!text.startsWith(target, index))
            return@resultFunc emptyList()

        listOf(ParserState(target, index + target.length))
    }
}

val kanjiTrie by lazy {
    val trie = WordTrie()
    JMDict.instance.wordsMap.forEach { (_, wordList) ->
        wordList.forEach { word ->
            trie.addForKanji(word)
        }
    }
    trie
}

val hiraganaTrie by lazy {
    val trie = WordTrie()
    JMDict.instance.wordsMap.forEach { (_, wordList) ->
        wordList.forEach { word ->
            trie.addForHiragana(word)
        }
    }
    trie
}