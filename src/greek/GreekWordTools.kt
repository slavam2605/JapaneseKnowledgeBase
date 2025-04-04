package greek

import kotlin.collections.contains
import kotlin.collections.map

private const val skipUncommonForms = true

private val greekVowels = setOf('α', 'ά', 'ε', 'έ', 'η', 'ή', 'ι', 'ί', 'ϊ', 'ο', 'ό', 'υ', 'ύ', 'ϋ', 'ω', 'ώ')
private val greekStressedVowels = setOf('ά', 'έ', 'ή', 'ί', 'ό', 'ύ', 'ώ')
private val vowelDiphthongs = setOf("ει", "ου", "αι", "οι", "ευ", "ιω", "ια") // Used to determine vowel count for stress
private val vowelTriphtongs = setOf("ιει", "ιου", "οια")
private val allVowelTongs = vowelTriphtongs + vowelDiphthongs + listOf("α", "ε", "η", "ι", "ϊ", "ο", "υ", "ϋ", "ω")
private val greekVowelsStressMap = mapOf('ά' to 'α', 'έ' to 'ε', 'ή' to 'η', 'ί' to 'ι', 'ό' to 'ο', 'ύ' to 'υ', 'ώ' to 'ω')
private val greekVowelsMakeStressMap = mapOf('α' to 'ά', 'ε' to 'έ', 'η' to 'ή', 'ι' to 'ί', 'ο' to 'ό', 'υ' to 'ύ', 'ω' to 'ώ')

private val knownExceptions = mutableMapOf(
    "λέω" to listOf("λέω", "λες", "λέει", "λέμε", "λέτε", "λένε"),
    "κλαίω" to listOf("κλαίω", "κλαις", "κλαίει", "κλαίμε", "κλαίτε", "κλαίνε"),
    "τρώω" to listOf("τρώω", "τρως", "τρώει", "τρώμε", "τρώτε", "τρώνε"),
    "ακούω" to listOf("ακούω", "ακούς", "ακούει", "ακούμε", "ακούτε", "ακούνε"),
    "πάω" to listOf("πάω", "πας", "πάει", "πάμε", "πάτε", "πάνε"),
    "σπάω" to listOf("σπάω", "σπας", "σπάει", "σπάμε", "σπάτε", "σπάνε"),
)
private val knownB1Verbs = mutableSetOf("βοηθάω", "συζητάω", "ζητάω", "προχωράω", "χωράω", "μιλάω", "περπατάω", "κρατάω")
private val knownB2Verbs = mutableSetOf("τηλεφωνώ")

private val knownIrregularFuture = mutableMapOf(
    // Irregular verbs
    "βλέπω" to "δω",
    "πηγαίνω" to "πάω",
    "πίνω" to "πιω",
    "καταπίνω" to "καταπιώ",
    "λέω" to "πω",
    "τρώω" to "φάω",
    "δίνω" to "δώσω",
    "βρίσκω" to "βρω",
    "βγαίνω" to "βγω",
    "μπαίνω" to "μπω",
    "αντικαθιστώ" to "αντικαταστήσω",

    // Verbs that don't change in the future
    "έχω" to "έχω",
    "ξέρω" to "ξέρω",
    "πάω" to "πάω",
    "περιμένω" to "περιμένω",
    "μεταφέρω" to "μεταφέρω",
    "προσφέρω" to "προσφέρω",
    "προτείνω" to "προτείνω",

    // Verbs with -αίνω -> -ω
    "μαθαίνω" to "μάθω",
    "παθαίνω" to "πάθω",
    "καταλαβαίνω" to "καταλάβω",
    "κατεβαίνω" to "κατέβω",
    "ανεβαίνω" to "ανέβω",
    "παίρνω" to "πάρω",

    // Verbs with έ -> εί or έ -> ύ
    "μένω" to "μείνω",
    "παραγγέλνω" to "παραγγείλω",
    "στέλνω" to "στείλω",
    "πλένω" to "πλύνω",
    "φεύγω" to "φύγω",

    // Irregular verbs with -σω
    "ακούω" to "ακούσω",
    "σπάω" to "σπάσω",
    "αναπνέω" to "αναπνεύσω",
    "αποθηκεύω" to "αποθηκεύσω",
    "πέφτω" to "πέσω",
    "νιώθω" to "νιώσω",

    // Verbs with ζω -> λω
    "βάζω" to "βάλω",
    "βγάζω" to "βγάλω",

    // Verbs with unexpected -ξω
    "κοιτάζω" to "κοιτάξω",
    "παίζω" to "παίξω",
    "πετάω" to "πετάξω",
    "εισπράττω" to "εισπράξω",
    "αλλάζω" to "αλλάξω",
    "φωνάζω" to "φωνάξω",

    // B1-group verbs with -άσω
    "πεινάω" to "πεινάσω",
    "διψάω" to "διψάσω",
    "γελάω" to "γελάσω",
    "χαμογελάω" to "χαμογελάσω",
    "χαλάω" to "χαλάσω",
    "περνάω" to "περάσω", // also ν is dropped
    "ξεχνάω" to "ξεχάσω", // also ν is dropped

    // B1/B2-group with -έσω
    "μπορώ" to "μπορέσω",
    "προσκαλώ" to "προσκαλέσω",
    "χωράω" to "χωρέσω",
    "καλώ" to "καλέσω",

    // Irregular B1 forms
    "τραβάω" to "τραβήξω",
    "φυσάω" to "φυσήξω",

    // Unsorted list of exceptions
    "κλαίω" to "κλάψω",
    "παραλαμβάνω" to "παραλάβω",
    "φέρνω" to "φέρω",
    "ξηραίνω" to "ξηράνω",
    "πεθαίνω" to "πεθάνω",
    "αρρωσταίνω" to "αρρωστήσω",
    "θέλω" to "θελήσω", // TODO: discuss if this form is actually used
)

private val knownIrregularFutureFull = mapOf(
    "τρώω" to listOf(listOf("θα φάω"), listOf("θα φας"), listOf("θα φάει"), listOf("θα φάμε"), listOf("θα φάτε"), listOf("θα φάνε"))
)

private val knownIrregularPastFull = mapOf(
    "πίνω" to listOf(listOf("ήπια"), listOf("ήπιες"), listOf("ήπιε"), listOf("ήπιαμε"), listOf("ήπιατε"), listOfNotNull(if (skipUncommonForms) null else "ήπιανε", "ήπιαν")),
    "καταπίνω" to listOf(listOf("κατάπια"), listOf("κατάπιες"), listOf("κατάπιε"), listOf("κατάπιαμε"), listOf("κατάπιατε"), listOf("κατάπιαν")),
    "παρουσιάζω" to listOf(listOf("παρουσίασα"), listOf("παρουσίασες"), listOf("παρουσίασε"), listOf("παρουσιάσαμε"), listOf("παρουσιάσατε"), listOfNotNull(if (skipUncommonForms) null else "παρουσιάσανε", "παρουσίασαν")),
)

// Verbs with prefixes -> έ
private val wordsWithPastPrefix = mapOf(
    "επιστρέφω" to "επέστρεψα",
    "επιλέγω" to "επέλεξα",
    "καταθέτω" to "κατέθεσα",
    "εισπράττω" to "εισέπραξα",
    "παραλαμβάνω" to "παρέλαβα",
    "υπογράφω" to "υπέγραψα",
    "αντικαθιστώ" to "αντικατέστησα",
    "αναπνέω" to "ανέπνευσα",
    "συλλέγω" to "συνέλεξα",
    "παραγγέλνω" to "παρήγγειλα",
    "μεταφέρω" to "μετέφερα"
)

private val knownIrregularPastBase = mutableMapOf(
    // Irregular verbs
    "βλέπω" to "είδα",
    "έχω" to "είχα",
    "ξέρω" to "ήξερα",
    "πηγαίνω" to "πήγα",
    "πάω" to "πήγα",
    "πίνω" to "ήπια",
    "παίρνω" to "πήρα",
    "λέω" to "είπα",
    "τρώω" to "έφαγα",

    // -ηκα verbs
    "κατεβαίνω" to "κατέβηκα",
    "ανεβαίνω" to "ανέβηκα",
    "βρίσκω" to "βρήκα",
    "βγαίνω" to "βγήκα",
    "μπαίνω" to "μπήκα",

    // Exception in stress shift for -ια-
    "παρουσιάζω" to "παρουσίασα",

    // G1 verbs with -ηκα
    "σκέφτομαι" to "σκέφτηκα",
    "κουράζομαι" to "κουράστηκα",
    "ξεκουράζομαι" to "ξεκουράστηκα",
    "χτενίζομαι" to "χτενίστηκα",
    "σηκώνομαι" to "σηκώθηκα",
    "χρειάζομαι" to "χρειάστηκα",
    "πλένομαι" to "πλύθηκα",
    "βάφομαι" to "βάφτηκα",
    "βρίσκομαι" to "βρέθηκα",
    "ντύνομαι" to "ντήθηκα",
    "ετοιμάζομαι" to "ετοιμάστηκα",
    "φαντάζομαι" to "φαντάστηκα",
    "εμπιστεύομαι" to "εμπιστεύτηκα",
    "παντρεύομαι" to "παντρεύτηκα",
    "επισκέπτομαι" to "επισκέφτηκα",
    "αισθάνομαι" to "αισθάνθηκα",
    "φτερνίζομαι" to "φτερνίστηκα",
    "χαίρομαι" to "χάρηκα",

    // Other G1 verbs
    "έρχομαι" to "ήρθα",
    "κάθομαι" to "κάθισα",
    "γίνομαι" to "έγινα",

    // G2 verbs
    "κοιμάμαι" to "κοιμήθηκα",
    "φοβάμαι" to "φοβήθηκα",
    "λυπάμαι" to "λυπήθηκα",
    "θυμάμαι" to "θυμήθηκα",
    "γεννιέμαι" to "γεννήθηκα"
)

private val futureBaseGamma = mapOf(
    "σκέφτομαι" to "σκεφτώ",
    "γίνομαι" to "γίνω",
    "χαίρομαι" to "χαρώ",
    "επισκέπτομαι" to "επισκεφτώ",
    "κάθομαι" to "κάτσω",

    "έρχομαι" to "έρθω",
    "πλένομαι" to "πλυθώ",
    "βρίσκομαι" to "βρεθώ",
    "ντύνομαι" to "ντυθώ",
    "σηκώνομαι" to "σηκωθώ",
    "αισθάνομαι" to "αισθανθώ",

    "κουράζομαι" to "κουραστώ",
    "ξεκουράζομαι" to "ξεκουραστώ",
    "χτενίζομαι" to "χτενιστώ",
    "χρειάζομαι" to "χρειαστώ",
    "ετοιμάζομαι" to "ετοιμαστώ",
    "φαντάζομαι" to "φανταστώ",
    "φτερνίζομαι" to "φτερνιστώ",

    "βάφομαι" to "βαφτώ",
    "εμπιστεύομαι" to "εμπιστευτώ",
    "παντρεύομαι" to "παντρευτώ",

    "γεννιέμαι" to "γεννηθώ", // Gamma 2, but ιη -> η
)

private fun Char.isGreekVowel(): Boolean = this in greekVowels

private fun Char.isStressedVowel(): Boolean = this in greekStressedVowels

private fun String.countGreekVowels(): Int {
    // TODO replace with count syllables
    return splitToSyllables(this).size
}

private fun splitToSyllables(stressedWord: String): List<String> {
    val word = greekRemoveStress(stressedWord)
    val syllables = mutableListOf(StringBuilder())
    var syllableIndex = 0
    var index = 0
    outer@ while (index < word.length) {
        if (!word[index].isGreekVowel()) {
            syllables[syllableIndex].append(word[index])
            index++
            continue
        }

        for (t in allVowelTongs) {
            if (word.startsWith(t, startIndex = index)) {
                syllables[syllableIndex].append(stressedWord.substring(index, index + t.length))
                syllables.add(StringBuilder())
                syllableIndex++
                index += t.length
                continue@outer
            }
        }
        error("Unexpected symbol: ${word[index]}")
    }
    while (syllables.size > 1 && syllables.last().all { !it.isGreekVowel() }) {
        syllables[syllables.size - 2].append(syllables.last())
        syllables.removeLast()
    }
    return syllables.map { it.toString() }
}

private fun greekRemoveStress(s: CharSequence): String {
    return s.map { greekVowelsStressMap[it] ?: it }.joinToString("")
}

private fun greekSyllablePutStress(s: CharSequence): String {
    val chars = s.toMutableList()
    outer@ for (index in 0 until chars.size) {
        for (tong in allVowelTongs) {
            if (!s.startsWith(tong, startIndex = index)) continue
            chars[index + tong.length - 1] = greekVowelsMakeStressMap[chars[index + tong.length - 1]]!!
            break@outer
        }
    }
    return chars.joinToString("")
}

private fun removeStressIfNeeded(s: String): String {
    return if (s.countGreekVowels() == 1) greekRemoveStress(s) else s
}

private fun String.endsWithStressed(suffix: String): Boolean {
    return endsWith(suffix) || (endsWith(greekRemoveStress(suffix)) && countGreekVowels() == 1)
}

private fun String.endsWithAny(vararg suffix: String): Boolean {
    return suffix.any { endsWith(it) }
}

enum class GreekVerbGroup {
    A, B1, B2, G1, G2, EX
}

data class GreekVerb(
    val word: String,
    val present: List<List<String>> = emptyList(),
    val futureSimple: List<List<String>> = emptyList(),
    val pastSimple: List<List<String>> = emptyList()
) {
    fun guessGroup(): GreekVerbGroup {
        return when {
            word in knownExceptions -> GreekVerbGroup.EX
            word in knownB1Verbs -> GreekVerbGroup.B1
            word in knownB2Verbs -> GreekVerbGroup.B2
            word.endsWith("άω") -> GreekVerbGroup.B1
            word.endsWithStressed("ώ") -> GreekVerbGroup.B2
            word.endsWith("ω") -> GreekVerbGroup.A
            word.endsWith("ομαι") -> GreekVerbGroup.G1
            word.endsWith("μαι") && word.getOrNull(word.length - 4) in greekStressedVowels -> GreekVerbGroup.G2
            else -> error("Unknown word form: '$word'")
        }
    }

    fun guessPresentForms(): List<List<String>> {
        return when (guessGroup()) {
            GreekVerbGroup.A -> a1Forms(word)
            GreekVerbGroup.B1 -> b1Forms(word)
            GreekVerbGroup.B2 -> b2Forms(word)
            GreekVerbGroup.G1 -> g1Forms(word)
            GreekVerbGroup.G2 -> g2Forms(word)
            GreekVerbGroup.EX -> {
                knownExceptions[word]
                    ?.map { listOf(it) }
                    ?: List(6) { emptyList() }
            }
        }
    }

    fun guessFutureBaseForm(): String? {
        // Try to get an irregular form first
        knownIrregularFuture[word]?.let {
            return it
        }

        // Then check for G1 verbs (with one G2 exception)
        futureBaseGamma[word]?.let {
            return it
        }

        return when (guessGroup()) {
            GreekVerbGroup.A -> {
                val stem = word.dropLast(1)
                return when {
                    stem.endsWith("εύ") -> stem.dropLast(2) + "έψω"
                    stem.endsWithAny("χν", "σκ") -> stem.dropLast(2) + "ξω"
                    stem.endsWithAny("φ", "π", "β") -> stem.dropLast(1) + "ψω"
                    stem.endsWithAny("ζ", "σ", "ν", "τ") -> stem.dropLast(1) + "σω"
                    stem.endsWithAny("κ", "γ", "χ") -> stem.dropLast(1) + "ξω"
                    else -> null
                }
            }
            GreekVerbGroup.B1 -> {
                word.dropLast(2) + "ήσω"
            }
            GreekVerbGroup.B2 -> {
                word.dropLast(1) + "ήσω"
            }
            GreekVerbGroup.G1 -> null // No deducible rule, only explicit forms list
            GreekVerbGroup.G2 -> {
                val stem = word.dropLast(4)
                stem + "ηθώ"
            }
            GreekVerbGroup.EX -> null
        }
    }

    fun guessFutureSimpleForms(): List<List<String>> {
        knownIrregularFutureFull[word]?.let {
            return it
        }

        val futureForm = guessFutureBaseForm() ?: return List(6) { emptyList() }
        return GreekVerb(futureForm).guessPresentForms().map { it.map { "θα $it" } }
    }

    fun guessPastSimpleForms(): List<List<String>> {
        // TODO are -ane prefixes even used?
        // List of examples that Google thinks are incorrect:
        // συνηθίσανε, μιλήσανε, ακούσανε, διαβάσανε, δουλέψανε, θελήσανε, καταλάβανε, ήπιανε, ταξιδέψανε, αρχίσανε, σπουδάσανε
        // But here is the list of words that Google thinks are correct:
        // πιάσανε, βάλανε, γράψανε, μείνανε, μάθανε, συμφωνήσανε

        // If there is an unpredictable moving of stress
        knownIrregularPastFull[word]?.let {
            return it
        }

        // If a base past simple form is an exception
        knownIrregularPastBase[word]?.let { knownPast ->
            val pastStem = knownPast.dropLast(1)
            val syllables = splitToSyllables(pastStem).toMutableList()
            val stressedIndex = syllables.indexOfFirst { it.any { it.isStressedVowel() } }.takeIf { it >= 0 } ?: 0
            if (stressedIndex < syllables.size - 1) {
                syllables[stressedIndex] = greekRemoveStress(syllables[stressedIndex])
                syllables[stressedIndex + 1] = greekSyllablePutStress(syllables[stressedIndex + 1])
                if (stressedIndex == 0 && syllables.first() in listOf("η", "ε")) {
                    syllables.removeFirst()
                }
            }
            val movedStem = syllables.joinToString("")

            return listOf(
                listOf(pastStem + "α"),
                listOf(pastStem + "ες"),
                listOf(pastStem + "ε"),
                listOf(movedStem + "αμε"),
                listOf(movedStem + "ατε"),
                listOfNotNull(pastStem + "αν", if (skipUncommonForms) null else movedStem + "ανε")
            )
        }

        // Otherwise, derive past simple from future simple form (and handle prefix words correctly)
        val futureBase = guessFutureBaseForm() ?: return List(6) { emptyList() }
        val futureStem = futureBase.dropLast(1)
        val pastStem = (wordsWithPastPrefix[word] ?: transformFutureToPast(futureBase)).dropLast(1)

        val aneForm = if (word in wordsWithPastPrefix) {
            // For words with prefix, -ανε is not commonly used
            null
        } else {
            if (skipUncommonForms) null else futureStem + "ανε"
        }
        return listOf(
            listOf(pastStem + "α"),
            listOf(pastStem + "ες"),
            listOf(pastStem + "ε"),
            listOf(futureStem + "αμε"),
            listOf(futureStem + "ατε"),
            listOfNotNull(pastStem + "αν", aneForm)
        )
    }

    companion object {
        private fun transformFutureToPast(future: String): String {
            val syllables = splitToSyllables(future).toMutableList()
            val stressedIndex = syllables.indexOfFirst { it.any { it.isStressedVowel() } }.takeIf { it >= 0 } ?: 0
            syllables[stressedIndex] = greekRemoveStress(syllables[stressedIndex])
            if (stressedIndex > 0) {
                syllables[stressedIndex - 1] = greekSyllablePutStress(syllables[stressedIndex - 1])
            } else {
                syllables.add(0, "έ")
            }
            return syllables.joinToString("")
        }

        private fun a1Forms(base: String) = base.dropLast(1).let { stem ->
            listOf(
                listOf(base),
                listOf(stem + "εις"),
                listOf(stem + "ει"),
                listOf(stem + "ουμε"),
                listOf(stem + "ετε"),
                listOfNotNull(stem + "ουν", if (skipUncommonForms) null else stem + "ουνε")
            )
        }

        private fun b1Forms(base: String) = base.dropLast(1).let { stem ->
            listOf(
                listOf(base, base.dropLast(2) + "ώ"),
                listOf(removeStressIfNeeded(stem + "ς")),
                listOf(stem + "ει", stem),
                listOf(stem + "με", stem.dropLast(1) + "ούμε"),
                listOf(stem + "τε"),
                if (skipUncommonForms) {
                    listOf(stem + "νε", stem.dropLast(1) + "ούν")
                } else {
                    listOf(stem + "νε", stem + "ν", stem.dropLast(1) + "ούνε", stem.dropLast(1) + "ούν")
                }
            )
        }

        private fun b2Forms(base: String) = base.dropLast(1).let { stem ->
            listOf(
                listOf(base),
                listOf(stem + "είς"),
                listOf(stem + "εί"),
                listOf((stem + "ούμε")),
                listOf(stem + "είτε"),
                listOfNotNull(stem + "ούν", if (skipUncommonForms) null else stem + "ούνε")
            ).map { it.map { removeStressIfNeeded(it) } }
        }

        private fun g1Forms(base: String) = base.dropLast(4).let { stem ->
            val noStress = greekRemoveStress(stem)
            listOf(
                listOf(stem + "ομαι"),
                listOf(stem + "εσαι"),
                listOf(stem + "εται"),
                listOf(noStress + "όμαστε"),
                listOf(stem + "εστε"),
                listOf(stem + "ονται")
            )
        }

        private fun g2Forms(base: String) = base.dropLast(3).let { stem ->
            listOf(
                listOf(stem + "μαι"),
                listOf(stem + "σαι"),
                listOf(stem + "ται"),
                listOf(stem.dropLast(1) + "όμαστε"),
                listOf(stem + "στε"),
                listOf(stem.dropLast(1) + "ούνται")
            )
        }
    }
}