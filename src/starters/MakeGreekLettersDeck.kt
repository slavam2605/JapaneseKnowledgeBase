package starters

import greek.spelling.GreekSpellingV1
import greek.spelling.GreekSpellingV2
import greek.spelling.GreekSpellingV3
import utils.AnkiDataManager
import utils.AnkiNote
import utils.AnkiTxtWriter

fun main() {
    val notes = AnkiDataManager.readDeck(AnkiDataManager.PES_TO_ELLINIKA_DECK)
        .filter { note -> !note.tags.any { it.trim() == "to_remove" } }

    val oldVersion = GreekSpellingV2()
    val newVersion = GreekSpellingV3()
    val oldResults = oldVersion.getSpellings(notes)
    val newResults = newVersion.getSpellings(notes)
    val resultList = mutableListOf<AnkiNote>()
    for (keyNote in oldResults.keys + newResults.keys) {
        val oldResult = oldResults[keyNote]
        val newResult = newResults[keyNote]
        if (oldResult == newResult) continue

        if (oldResult != null) {
            resultList.add(AnkiNote(listOf(oldResult), listOf("to_remove")))
        }
        if (newResult != null) {
            resultList.add(AnkiNote(listOf(newResult), emptyList()))
        }

        if (oldResult != null && newResult == null) {
            println("Removed: ${keyNote.fields[0]}")
        }
        if (oldResult == null && newResult != null) {
            println("Added: ${keyNote.fields[0]}")
        }
        if (oldResult != null && newResult != null) {
            val translationOnly = newResult.substringAfter("<br><br>").substringBefore("<br><br>")
            println("Modified: ${keyNote.fields[0]} -> $translationOnly")
        }
    }

    AnkiTxtWriter.writeTxtDeck("/Users/Vyacheslav.Moklev/Greek spelling.txt") {
        resultList.map { listOf(it.fields[0], "", it.tags.joinToString(" ")) }.shuffled()
    }
}