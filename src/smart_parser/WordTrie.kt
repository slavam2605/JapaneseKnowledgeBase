package smart_parser

import dict.WordEntry

class WordTrie {
    val root = Node()

    fun addForKanji(word: WordEntry) {
        internalAdd(root, word.text, word)
    }

    fun addForHiragana(word: WordEntry) {
        internalAdd(root, word.getReading(), word)
    }

    private fun internalAdd(node: Node, text: String, word: WordEntry) {
        if (text.isEmpty()) {
            node.words.add(word)
            return
        }

        val childNode = node.children.getOrPut(text[0]) { Node() }
        internalAdd(childNode, text.substring(1), word)
    }

    class Node {
        val words = mutableListOf<WordEntry>()
        val children = mutableMapOf<Char, Node>()
    }
}