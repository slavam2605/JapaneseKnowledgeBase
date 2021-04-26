package smart_parser

import dict.WordEntry
import smart_parser.grammar.*

typealias StateList<T> = List<ParserState<T>>

class SmartParser(val text: String) {
    fun parse(): GrammarNode {
        TODO()
    }

    fun parseSentence(index: Int): StateList<Pair<WordEntry, WordEntry>> {
        return parseSequence(index, wordParser(), stringParser("は"), wordParser()) { r1, _, r3 ->
            r1 to r3
        }
    }

    fun wordParser(): ParseFunction<WordEntry> {
        return resultFunc@ { index ->
            val result = mutableListOf<ParserState<WordEntry>>()

            fun searchInTrie(trie: WordTrie) {
                var node = trie.root
                for (i in index until text.length) {
                    val textChar = text[i]
                    val nextNode = node.children[textChar] ?: break
                    for (word in nextNode.words) {
                        result.add(ParserState(word, i + 1))
                        break
                    }
                    node = nextNode
                }
            }

            searchInTrie(kanjiTrie)
            searchInTrie(hiraganaTrie)
            return@resultFunc result
        }
    }
}