package utils

val Char.isKana: Boolean
    get() = this in '\u3040'..'\u31FF'

val Char.isHiragana: Boolean
    get() = this in '\u3041'..'\u309e'

val Char.isKatakana: Boolean
    get() = isHalfWidthKatakana || isFullWidthKatakana

val Char.isHalfWidthKatakana: Boolean
    get() = this in '\uff66'..'\uff9d'

val Char.isFullWidthKatakana: Boolean
    get() = this in '\u30a1'..'\u30fe'

val Char.isKanji: Boolean
    get() = this in '\u4e00'..'\u9fa5' || this in '\u3005'..'\u3007'

val Char.isSmallHiragana: Boolean
    get() = this in smallHiraganaSet

val Char.possibleReadings: List<String>
    get() = when {
        isHiragana -> when (this) {
            'ゐ' -> listOf("ゐ", "い")
            'ゑ' -> listOf("ゑ", "え")
            else -> listOf("$this")
        }
        isKatakana -> when (this) {
            'ヶ' -> listOf("が")
            'ヰ' -> listOf("ヰ", "い")
            'ヱ' -> listOf("ヱ", "え")
            else -> listOf("$this", "${toHiragana()}")
        }
        else -> listOf()
    }

private val planeHiraganaSet = setOf(
    'あ', 'い', 'う', 'え', 'お',
    'か', 'き', 'く', 'け', 'こ',
    'さ', 'し', 'す', 'せ', 'そ',
    'た', 'ち', 'つ', 'て', 'と',
    'な', 'に', 'ぬ', 'ね', 'の',
    'は', 'ひ', 'ふ', 'へ', 'ほ',
    'ま', 'み', 'む', 'め', 'も',
    'や', 'ゆ', 'よ',
    'ら', 'り', 'る', 'れ', 'ろ',
    'わ', 'ゐ', 'ゑ', 'を', 'ん'
)

private val voicedHiraganaSet = setOf(
    'が', 'ぎ', 'ぐ', 'げ', 'ご',
    'ざ', 'じ', 'ず', 'ぜ', 'ぞ',
    'だ', 'ぢ', 'づ', 'で', 'ど',
    'ば', 'び', 'ぶ', 'べ', 'ぼ',
    'ゔ'
)

private val voicelessHiraganaSet = setOf(
    'ぱ', 'ぴ', 'ぷ', 'ぺ', 'ぽ'
)

private val smallHiraganaSet = setOf(
    'ぁ', 'ぃ', 'ぅ', 'ぇ', 'ぉ',
    'っ', 'ゃ', 'ゅ', 'ょ', 'ゎ',
    'ゕ', 'ゖ'
)

private val voicableConsonantHiraganaSet = setOf(
    'か', 'き', 'く', 'け', 'こ',
    'さ', 'し', 'す', 'せ', 'そ',
    'た', 'ち', 'つ', 'て', 'と',
    'は', 'ひ', 'ふ', 'へ', 'ほ'
)

private val voicelessableConsonantHiraganaSet = setOf(
    'は', 'ひ', 'ふ', 'へ', 'ほ'
)

fun Char.toKatakana(): Char =
    if (isHiragana) (toInt() + 0x60).toChar() else this

fun Char.toHiragana(): Char {
    if (isFullWidthKatakana) {
        return (toInt() - 0x60).toChar()
    } else if (isHalfWidthKatakana) {
        return (toInt() - 0xcf25).toChar()
    }
    return this
}

fun Char.toVoicedHiragana(): Char {
    if (this in voicableConsonantHiraganaSet)
        return (toInt() + 1).toChar()

    return this
}

fun Char.toVoicelessHiragana(): Char {
    if (this in voicelessableConsonantHiraganaSet)
        return (toInt() + 2).toChar()

    return this
}

fun Char.toPlainHiragana(): Char {
    return when (this) {
        'ゔ' -> 'う'
        in voicedHiraganaSet -> (toInt() - 1).toChar()
        in voicelessHiraganaSet -> (toInt() - 2).toChar()
        else -> this
    }
}

fun Char.possiblePlainHiragana(): Set<Char> {
    return when (this) {
        'ず' -> setOf(toPlainHiragana(), 'つ')
        else -> setOf(toPlainHiragana())
    }
}

enum class KanaConsonant {
    EMPTY, K, S, T, N, H, M, Y, R, W
}

enum class KanaVowel {
    A, I, U, E, O, SPECIAL_N
}

enum class KanaSign {
    NO, DAKUTEN, HANDAKUTEN
}

data class Hiragana (
    val consonant: KanaConsonant,
    val vowel: KanaVowel,
    val sign: KanaSign,
    val isSmall: Boolean
) {
    companion object {
        fun fromChar(char: Char): Hiragana? = when (char) {
            'あ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'い' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'う' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'え' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'お' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'か' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'き' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'く' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'け' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'こ' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'さ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'し' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'す' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'せ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'そ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'た' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'ち' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'つ' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'て' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'と' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'な' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'に' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'ぬ' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'ね' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'の' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'は' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'ひ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'ふ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'へ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'ほ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'ま' -> Hiragana(
                KanaConsonant.M,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'み' -> Hiragana(
                KanaConsonant.M,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'む' -> Hiragana(
                KanaConsonant.M,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'め' -> Hiragana(
                KanaConsonant.M,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'も' -> Hiragana(
                KanaConsonant.M,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'や' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'ゆ' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'よ' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'ら' -> Hiragana(
                KanaConsonant.R,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'り' -> Hiragana(
                KanaConsonant.R,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'る' -> Hiragana(
                KanaConsonant.R,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'れ' -> Hiragana(
                KanaConsonant.R,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'ろ' -> Hiragana(
                KanaConsonant.R,
                KanaVowel.O,
                KanaSign.NO,
                false
            )
            'わ' -> Hiragana(
                KanaConsonant.W,
                KanaVowel.A,
                KanaSign.NO,
                false
            )
            'ゐ' -> Hiragana(
                KanaConsonant.W,
                KanaVowel.I,
                KanaSign.NO,
                false
            )
            'ゑ' -> Hiragana(
                KanaConsonant.W,
                KanaVowel.U,
                KanaSign.NO,
                false
            )
            'を' -> Hiragana(
                KanaConsonant.W,
                KanaVowel.E,
                KanaSign.NO,
                false
            )
            'ん' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.SPECIAL_N,
                KanaSign.NO,
                false
            )
            'が' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.A,
                KanaSign.DAKUTEN,
                false
            )
            'ぎ' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.I,
                KanaSign.DAKUTEN,
                false
            )
            'ぐ' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.U,
                KanaSign.DAKUTEN,
                false
            )
            'げ' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.E,
                KanaSign.DAKUTEN,
                false
            )
            'ご' -> Hiragana(
                KanaConsonant.N,
                KanaVowel.O,
                KanaSign.DAKUTEN,
                false
            )
            'ざ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.A,
                KanaSign.DAKUTEN,
                false
            )
            'じ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.I,
                KanaSign.DAKUTEN,
                false
            )
            'ず' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.U,
                KanaSign.DAKUTEN,
                false
            )
            'ぜ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.E,
                KanaSign.DAKUTEN,
                false
            )
            'ぞ' -> Hiragana(
                KanaConsonant.S,
                KanaVowel.O,
                KanaSign.DAKUTEN,
                false
            )
            'だ' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.A,
                KanaSign.DAKUTEN,
                false
            )
            'ぢ' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.I,
                KanaSign.DAKUTEN,
                false
            )
            'づ' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.U,
                KanaSign.DAKUTEN,
                false
            )
            'で' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.E,
                KanaSign.DAKUTEN,
                false
            )
            'ど' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.O,
                KanaSign.DAKUTEN,
                false
            )
            'ば' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.A,
                KanaSign.DAKUTEN,
                false
            )
            'び' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.I,
                KanaSign.DAKUTEN,
                false
            )
            'ぶ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.U,
                KanaSign.DAKUTEN,
                false
            )
            'べ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.E,
                KanaSign.DAKUTEN,
                false
            )
            'ぼ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.O,
                KanaSign.DAKUTEN,
                false
            )
            'ゔ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.U,
                KanaSign.DAKUTEN,
                false
            )
            'ぱ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.A,
                KanaSign.HANDAKUTEN,
                false
            )
            'ぴ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.I,
                KanaSign.HANDAKUTEN,
                false
            )
            'ぷ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.U,
                KanaSign.HANDAKUTEN,
                false
            )
            'ぺ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.E,
                KanaSign.HANDAKUTEN,
                false
            )
            'ぽ' -> Hiragana(
                KanaConsonant.H,
                KanaVowel.O,
                KanaSign.HANDAKUTEN,
                false
            )
            'ぁ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.A,
                KanaSign.NO,
                true
            )
            'ぃ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.I,
                KanaSign.NO,
                true
            )
            'ぅ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.U,
                KanaSign.NO,
                true
            )
            'ぇ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.E,
                KanaSign.NO,
                true
            )
            'ぉ' -> Hiragana(
                KanaConsonant.EMPTY,
                KanaVowel.O,
                KanaSign.NO,
                true
            )
            'っ' -> Hiragana(
                KanaConsonant.T,
                KanaVowel.U,
                KanaSign.NO,
                true
            )
            'ゃ' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.A,
                KanaSign.NO,
                true
            )
            'ゅ' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.U,
                KanaSign.NO,
                true
            )
            'ょ' -> Hiragana(
                KanaConsonant.Y,
                KanaVowel.O,
                KanaSign.NO,
                true
            )
            'ゎ' -> Hiragana(
                KanaConsonant.W,
                KanaVowel.A,
                KanaSign.NO,
                true
            )
            'ゕ' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.A,
                KanaSign.NO,
                true
            )
            'ゖ' -> Hiragana(
                KanaConsonant.K,
                KanaVowel.E,
                KanaSign.NO,
                true
            )
            else -> null
        }
    }

    fun toChar(): Char? {
        for (char in '\u3041'..'\u309e') {
            if (fromChar(char) == this)
                return char
        }
        return null
    }

    private val exists: Boolean
        get() = toChar() != null

    fun changeVowel(newVowel: KanaVowel): Hiragana? {
        val newHiragana = Hiragana(consonant, newVowel, sign, isSmall)
        return if (newHiragana.exists) newHiragana else null
    }
}