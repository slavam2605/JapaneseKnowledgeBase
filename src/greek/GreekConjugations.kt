package greek

import utils.AnkiTxtWriter
import utils.PathConstants
import utils.resolveResource
import java.io.File

object GreekConjugations {
    private fun String.getFormsList(listName: String): List<String?> {
        val parts = split("|")
        check(parts[0] == listName)
        return parts.drop(1).map { if (it == "<null>") null else it }
    }

    private fun fixConjugations(list: MutableList<GreekVerb>) {
        list.replaceAll { entry ->
            val newPresent = entry.guessPresentForms()
            val newFutureSimple = entry.guessFutureSimpleForms()
            val newPastSimple = entry.guessPastSimpleForms()
            (0 until 6).forEach { index ->
                // Check guessed present forms
                check(entry.present[index].size <= 1)
                entry.present[index].firstOrNull()?.let { dictForm ->
                    if (dictForm !in newPresent[index]) {
                        println("Wrong forms: $dictForm is not a part of ${newPresent[index]}")
                    }
                }

                // Check guessed future simple forms
                check(entry.futureSimple[index].size <= 1)
                entry.futureSimple[index].firstOrNull()?.let { dictForm ->
                    if (dictForm !in newFutureSimple[index]) {
                        println("Wrong future for ${entry.word}: " +
                                "$dictForm is not a part of ${newFutureSimple[index]}")
                    }
                }

                // Check guessed past simple forms
                check(entry.pastSimple[index].size <= 1)
                entry.pastSimple[index].firstOrNull()?.let { dictForm ->
                    if (dictForm !in newPastSimple[index]) {
                        println("Wrong past for ${entry.word}: " +
                                "$dictForm is not a part of ${newPastSimple[index]}")
                    }
                }
            }
            GreekVerb(
                word = entry.word,
                present = newPresent,
                futureSimple = newFutureSimple,
                pastSimple = newPastSimple
            )
        }
    }

    fun readConjugations(): List<GreekVerb> {
        val lines = resolveResource(PathConstants.greekConjugations).readLines()
        val result = mutableListOf<GreekVerb>()
        for (index in 0 until lines.size step 4) {
            if (index + 3 >= lines.size) {
                break
            }

            val word = lines[index].let {
                check(it.startsWith(">>>"))
                it.removePrefix(">>>")
            }
            val present = lines[index + 1].getFormsList("present")
            val futureSimple = lines[index + 2].getFormsList("aplos_melodas")
            val pastSimple = lines[index + 3].getFormsList("aoristos")
            result.add(GreekVerb(
                word,
                present.map { listOfNotNull(it) },
                futureSimple.map { listOfNotNull(it) },
                pastSimple.map { listOfNotNull(it) }
            ))
        }

        fixConjugations(result)
        return result
    }
}

fun main() {
    val words = GreekConjugations.readConjugations()

    // Fact: future simple is always A group, apart from some exceptions
    // Fact: past simple is always the same, without exceptions (but not always formed from future simple)

    val categories = Array<MutableList<GreekVerb>>(6) { mutableListOf() }
    words.forEach { word ->
        categories[word.guessGroup().ordinal].add(word)
    }
    println()

    val russianPronouns = listOf("я", "ты", "он/она/оно", "мы", "вы", "они")
    val skipWords = setOf("οφείλω", "ταιριάζω", "σχολάω", "θέλω")
    AnkiTxtWriter.writeTxtDeck("/Users/Vyacheslav.Moklev/Greek word forms.txt") {
        words.filter { it.word !in skipWords }
            .map { word ->
                (1 until 6).map { index ->
                    listOf(
                        "${word.present[0].first()}, ${word.futureSimple[0].first()}, ${word.pastSimple[0].first()}",
                        russianPronouns[index],
                        word.present[index].joinToString(" / ") + "<br>" +
                                word.futureSimple[index].joinToString(" / ") + "<br>" +
                                word.pastSimple[index].joinToString(" / ")
                    )
                }
            }
            .flatten()
            .shuffled()
    }
}