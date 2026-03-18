package greek

import utils.AnkiTxtWriter

fun main() {
    // Temporary helper for manually generating the current batch of gamma verb cards.
    val words = setOf(
        "λέγομαι", "γυμνάζομαι", "εργάζομαι", "ενδιαφέρομαι", "μοιράζομαι", "πνίγομαι", "κρύβομαι", "βρέχομαι",
        "καίγομαι", "εύχομαι", "δέχομαι", "συμπεριφέρομαι", "στεναχωριέμαι", "φέρομαι", "φαίνομαι", "ασχολούμαι",
        "ερωτεύομαι", "σέβομαι", "κατευθύνομαι", "βιάζομαι", "αναφέρομαι", "τρελαίνομαι", "μαζεύομαι", "παραπονιέμαι",
        "βαριέμαι", "προσαρμόζομαι", "συμβουλεύομαι", "ενοχλούμαι", "ικανοποιούμαι", "οδηγούμαι", "χρησιμοποιούμαι",
        "αρνούμαι", "περιποιούμαι", "συνεννοούμαι", "αναρωτιέμαι", "χασμουριέμαι", "κουνιέμαι", "συναντιέμαι",
        "ευχαριστιέμαι", "αγαπιέμαι"
    )
    val conjugations = GreekConjugations.readConjugations()
    val unseenWords = mutableSetOf<String>()

    AnkiTxtWriter.writeTxtDeck("/Users/Vyacheslav.Moklev/Verbs_gamma.txt", tagsColumn = 7) {
        conjugations.flatMap { entry ->
            if (entry.word !in words) return@flatMap emptyList()
            unseenWords.remove(entry.word)

            listOf(
                listOf(entry.futureSimple[0][0], "", entry.word, "", "", "True", "aplos_melodas"),
                listOf(entry.pastSimple[0][0], "", entry.word, "", "", "True", "simple_past")
            )
        }
    }

    println("Unseen words: ${unseenWords.joinToString()}")
}
