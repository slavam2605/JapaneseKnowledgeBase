package starters

import dict.jishoDataset
import utils.KanjiLists
import utils.downloadKanjiInfo
import utils.resolveResource

fun main() {
    val allKanji = KanjiLists.jouyou.toSet() + jishoDataset.keys
    downloadKanjiInfo(
        resolveResource("kanji_info.json"),
        *allKanji.toCharArray()
    )
}