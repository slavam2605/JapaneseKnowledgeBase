package parser

import utils.Hiragana
import utils.KanaVowel
import utils.isKanji

object VerbsLemmatizer {
    fun toNormalForm(text: String): List<String> {
        // ignore する-verbs, should be parsed as Noun + する
        return toPlainForm(text).flatMap { toBaseVerb(it) }
    }

    /**
     * Transform all variations of dictionary form (like
     * causative, passive voice ans so on) to a base verb
     */
    private fun toBaseVerb(text: String): List<String> {
        return listOf(
            listOf(text),
            fromCausativeForm(text),
            fromPassiveForm(text),
            fromPotentialForm(text)
        ).flatten()
    }

    /**
     * Transform from terminal forms (-ます, -て and so on)
     * to dictionary form of the verb (but maybe not base, like causative or passive voice)
     */
    private fun toPlainForm(text: String): List<String> {
        return listOf(
            listOf(text),
            fromMasuForm(text),
            fromMashitaForm(text),
            fromMasenForm(text),
            fromNaiForm(text),
            fromNakattaForm(text),
            fromTaForm(text),
            fromTeForm(text),
            fromZuForm(text),
            fromIStem(text),
            fromVolitionalForm(text)
        ).flatten()
    }

    private fun fromZuForm(text: String): List<String> {
        return if (text.endsWith("ず"))
            fromAStem(text.dropLast(1))
        else
            emptyList()
    }

    private fun fromNakattaForm(text: String): List<String> {
        return AdjectivesLemmatizer.fromPastForm(text).flatMap {
            fromNaiForm(it)
        }
    }

    private fun fromPotentialForm(text: String): List<String> {
        val hiragana = text.getHiragana(-2)
        val result = mutableListOf<String>()
        if (text.endsWith("られる")) {
            result.add(text.dropLast(3) + "る")
        }
        if (text.endsWith("る") && hiragana?.vowel == KanaVowel.E) {
            result.add(text.dropLast(2) + hiragana.changeVowelToChar(KanaVowel.U))
        }
        return result
    }

    private fun fromPassiveForm(text: String): List<String> {
        return fromPassCausForm(text, 'ら', "れる")
    }

    private fun fromCausativeForm(text: String): List<String> {
        return fromPassCausForm(text, 'さ', "せる")
    }

    private fun fromPassCausForm(text: String, p: Char, s: String): List<String> {
        val hiragana = text.getHiragana(-3)
        val group1List = when {
            text.endsWith(s) && hiragana?.vowel == KanaVowel.A -> fromAStem(text.dropLast(2))
            else -> emptyList()
        }
        val group2List = when {
            text.endsWith("$p$s") -> fromAStem(text.dropLast(3))
            else -> emptyList()
        }
        return group1List + group2List
    }

    private fun fromVolitionalForm(text: String): List<String> {
        val hiragana = text.getHiragana(-2)
        val drop2 = text.dropLast(2)
        return when {
            text.endsWith("よう") -> listOf(drop2 + "る")
            text.endsWith("う") && hiragana?.vowel == KanaVowel.O ->
                listOf(drop2 + hiragana.changeVowelToChar(KanaVowel.U))
            else -> emptyList()
        }
    }

    private fun fromNaiForm(text: String): List<String> {
        return if (text.endsWith("ない"))
            fromAStem(text.dropLast(2))
        else
            emptyList()
    }

    private fun fromTeTaForm(text: String, t: Char, d: Char): List<String> {
        val stem1 = text.dropLast(1)
        val stem2 = text.dropLast(2)
        val group1list = when {
            text.endsWith("っ$t") -> listOf(stem2 + "う", stem2 + "つ", stem2 + "る")
            text.endsWith("ん$d") -> listOf(stem2 + "む", stem2 + "ぬ", stem2 + "ぶ")
            text.endsWith("い$t") -> listOf(stem2 + "く")
            text.endsWith("い$d") -> listOf(stem2 + "ぐ")
            text.endsWith("し$t") -> listOf(stem2 + "す")
            else -> emptyList()
        }
        val group2list = when {
            text.endsWith("$t") -> listOf(stem1 + "る")
            else -> emptyList()
        }
        return group1list + group2list
    }

    private fun fromTeForm(text: String) =
        fromTeTaForm(text, 'て', 'で')

    private fun fromTaForm(text: String) =
        fromTeTaForm(text, 'た', 'だ')

    private fun fromMashitaForm(text: String): List<String> {
        if (!text.endsWith("ました"))
            return emptyList()

        return fromIStem(text.dropLast(3))
    }

    private fun fromMasenForm(text: String): List<String> {
        if (!text.endsWith("ません"))
            return emptyList()

        return fromIStem(text.dropLast(3))
    }

    private fun fromMasuForm(text: String): List<String> {
        if (!text.endsWith("ます"))
            return emptyList()

        return fromIStem(text.dropLast(2))
    }

    private fun fromIStem(text: String): List<String> {
        val lastChar = text.last()
        val end = Hiragana.fromChar(lastChar) ?: return emptyList()
        return when {
            end.vowel == KanaVowel.I ->
                listOf(text.dropLast(1) + end.changeVowelToChar(KanaVowel.U))
            lastChar.isKanji || end.vowel == KanaVowel.E ->
                listOf(text + "る")
            else -> emptyList()
        }
    }

    private fun fromAStem(text: String): List<String> {
        val hiragana = text.getHiragana(-1) ?: return emptyList()
        val result = mutableListOf(text + "る")
        if (hiragana.vowel == KanaVowel.A) {
            val newKana = if (hiragana.toChar() == 'わ') 'う' else hiragana.changeVowelToChar(KanaVowel.U)
            result.add(text.dropLast(1) + newKana)
        }
        return result
    }
}