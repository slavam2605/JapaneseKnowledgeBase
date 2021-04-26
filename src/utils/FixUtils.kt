package utils

import dict.WordEntry
import dict.WordEntryImpl

fun fixKnownMistakes(map: MutableMap<Char, MutableList<WordEntry>>) {
    map.forEach { (_, wordList) ->
        wordList.forEach { word ->
            fixFurigana(word)?.let {
                (word as WordEntryImpl).furigana = it
            }
            fixTags(word)?.let {
                (word as WordEntryImpl).extraTags = it
            }
        }
    }
}

private fun fixFurigana(word: WordEntry): List<String>? = when (word.text) {
    "医薬" -> listOf("い", "やく")
    "医薬品" -> listOf("い", "やく", "ひん")
    "国会議事堂" -> listOf("こっ", "かい", "ぎ", "じ", "どう")
    "選挙運動" -> listOf("せん", "きょ", "うん", "どう")
    "着工" -> listOf("ちゃっ", "こう")
    "試合" -> listOf("し", "あい")
    "国家試験" -> listOf("こっ", "か", "し", "けん")
    "北海道開発庁長官" -> listOf("ほっ", "かい", "どう", "かい", "はつ", "ちょう", "ちょう", "かん")
    "小売り店" -> listOf("こ", "う", "", "てん")
    "小売価格" -> listOf("こ", "うり", "か", "かく")
    "小売" -> listOf("こ", "うり")
    "奥行き" -> listOf("おく", "ゆ", "")
    "画数" -> listOf("かく", "すう")
    "雲行き" -> listOf("くも", "ゆ", "")
    "詩歌" -> listOf("しいか")
    "口調" -> listOf("くちょう")
    "河原" -> listOf("かわら")
    "枠組み" -> listOf("わく", "ぐ", "")
    "放流" -> listOf("ほう", "りゅう")
    "薬局" -> listOf("やっ", "きょく")
    "落書き" -> listOf("らく", "が", "")
    "借金" -> listOf("しゃっ", "きん")
    "借款" -> listOf("しゃっ", "かん")
    "無駄" -> listOf("む", "だ")
    "無茶" -> listOf("む", "ちゃ")
    "日本式" -> listOf("に", "ほん", "しき")
    "各国" -> listOf("かっ", "こく")
    "眼差し" -> listOf("まな", "ざ", "")
    "日課" -> listOf("にっ", "か")
    "北極" -> listOf("ほっ", "きょく")
    "積極的" -> listOf("せっ", "きょく", "てき")
    "北極圏" -> listOf("ほっ", "きょく", "けん")
    "積極" -> listOf("せっ", "きょく")
    "楽器" -> listOf("がっ", "き")
    "食器" -> listOf("しょっ", "き")
    "石器" -> listOf("せっ", "き")
    else -> null
}

private fun fixTags(word: WordEntry): List<String>? = when (word.text) {
    "通夜" -> emptyList()
    else -> null
}

val knownMistakesInENAM = setOf(
    "津山工業高等専門学校", "えんじん橋", "大庭城跡公園", "東武動物公園駅", "オビヤタンナイ沢川",
    "ポロケシ川"
)