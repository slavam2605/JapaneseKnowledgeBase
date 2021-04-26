package dict

import dict.OutlierDict.ComponentKind.*

private typealias KanjiComponent = String

object OutlierDict {
    val entries: Map<KanjiComponent, Entry> = listOf(
        "現".entry(
            "𤣩" to Empty("Знак, чтобы отличать от 見"),
            "見" to SoundSimilar("けん", "げん"),
            "見" to Meaning()
        ),

        "見".entry(
            "目" to Form(),
            "儿" to Form()
        ),

        "𤣩".entry(
            "玉" to ComponentForm
        )
    ).associateBy { it.kanji }

    private fun KanjiComponent.entry(vararg components: Pair<KanjiComponent, ComponentKind>) =
        Entry(this, components.toList())

    class Entry(val kanji: KanjiComponent, val components: List<Pair<KanjiComponent, ComponentKind>>)

    sealed class ComponentKind {
        class Empty(val comment: String = "") : ComponentKind()
        class Form(val comment: String = "") : ComponentKind()
        class Meaning(val comment: String = "") : ComponentKind()
        class SoundExact(val sound: String) : ComponentKind()
        class SoundSimilar(val fromSound: String, val toSound: String) : ComponentKind()
        class SoundNotObvious(val fromSound: String, val toSound: String = "") : ComponentKind()
        object ComponentForm : ComponentKind()
    }
}