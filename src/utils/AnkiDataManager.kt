package utils

import TxtWordEntry
import org.sqlite.SQLiteConfig
import utils.PathConstants.ankiCollectionPath
import java.nio.file.Path
import java.sql.Connection
import java.sql.DriverManager
import java.sql.ResultSet
import java.sql.SQLException
import kotlin.io.path.pathString

object AnkiDataManager {
    const val PES_TO_ELLINIKA_DECK = "Πες το ελληνικά"
    const val KANJI_DECK = "日本語\u001FKanji\u001FKanji"
    const val KANJI_WORDS_DECK = "日本語\u001FKanji\u001FKanji words"
    private val WORD_DECKS = listOf(
        "日本語\u001FWords\u001FWords MNN1-2",
        "日本語\u001FWords\u001FWords MNN3",
        "日本語\u001FWords\u001FWords 完全マスターN2"
    )

    val kanjiDeck: Map<String, TxtWordEntry> by lazy { readKanjiDeck() }
    val wordDecks: List<TxtWordEntry> by lazy { readWordDecks() }
    val kanjiWordsDeck: List<TxtWordEntry> by lazy { readKanjiWordsDeck() }

    fun readDeck(deckName: String): List<AnkiNote> {
        val result = mutableListOf<AnkiNote>()
        connectToDatabase(ankiCollectionPath)?.use { connection ->
            val deckId = connection.getDeckId(deckName)
            connection.executeQuery(selectNotesQuery(deckId))?.let {
                while (it.next()) {
                    result.add(AnkiNote(
                        fields = it.getString("flds").split("\u001F"),
                        tags = it.getString("tags").split("\u001F")
                    ))
                }
            }
        }
        return result
    }

    private fun readKanjiWordsDeck(): List<TxtWordEntry> {
        val result = mutableListOf<TxtWordEntry>()
        connectToDatabase(ankiCollectionPath)?.use { connection ->
            val deckId = connection.getDeckId(KANJI_WORDS_DECK)
            connection.executeQuery(selectNotesQuery(deckId))?.let {
                while (it.next()) {
                    val (kanji, kana, meaning) = it.getString("flds").split("\u001F")
                    result.add(TxtWordEntry(kana, kanji, "", meaning, emptyList()))
                }
            }
        }
        return result
    }

    private fun readWordDecks(): List<TxtWordEntry> {
        val result = mutableListOf<TxtWordEntry>()
        connectToDatabase(ankiCollectionPath)?.use { connection ->
            for (deckName in WORD_DECKS) {
                val deckId = connection.getDeckId(deckName)
                connection.executeQuery(selectNotesQuery(deckId))?.let {
                    while (it.next()) {
                        val (kana, kanji, definition, examples, _, type, _) = it.getString("flds").split("\u001F")
                        result.add(TxtWordEntry(kana, kanji, type, definition, examples.splitAnkiHtml()))
                    }
                }
            }
        }
        return result
    }

    private fun readKanjiDeck(): Map<String, TxtWordEntry> {
        val result = mutableMapOf<String, TxtWordEntry>()
        connectToDatabase(ankiCollectionPath)?.use { connection ->
            val deckId = connection.getDeckId(KANJI_DECK)
            connection.executeQuery(selectNotesQuery(deckId))?.let {
                while (it.next()) {
                    val (kanji, _, _, kana) = it.getString("flds").split("\u001F")
                    result.put(kanji, TxtWordEntry(
                        kana = kana,
                        kanji = kanji,
                        type = "",
                        definition = "",
                        examples = emptyList()
                    ))?.let {
                        System.err.println("Duplicated kanji in kanji deck: $kanji")
                    }
                }
            }
        }
        return result
    }

    private fun Connection.getDeckId(name: String): String {
        val deckId = executeQuery("select * from decks where name like '$name'")?.let {
            if (!it.next()) return@let null
            it.getString("id")
        }
        if (deckId == null) {
            error("Failed to find a deck with name '${name.replace("\u001F", "::")}'")
        }
        return deckId
    }

    private fun selectNotesQuery(deckId: String): String {
        return "SELECT DISTINCT notes.* FROM notes\n" +
                "JOIN cards ON notes.id = cards.nid\n" +
                "WHERE cards.did = $deckId"
    }

    private fun connectToDatabase(dbFilePath: Path): Connection? {
        return try {
            val url = "jdbc:sqlite:${dbFilePath.pathString}"
            val properties = SQLiteConfig().apply { setReadOnly(true) }.toProperties()
            DriverManager.getConnection(url, properties)
        } catch (e: SQLException) {
            println(e.message)
            null
        }
    }

    private fun Connection.executeQuery(query: String): ResultSet? {
        return try {
            createStatement().executeQuery(query)
        } catch (e: SQLException) {
            println(e.message)
            return null
        }
    }

    fun String.deckName() = replace("\u001F", "::")
}

data class AnkiNote(
    val fields: List<String>,
    val tags: List<String>
)