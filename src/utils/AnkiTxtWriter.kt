package utils

import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter

object AnkiTxtWriter {
    fun writeTxtDeck(path: String, notes: () -> Iterable<List<String>>) {
        val file = File(path)
        OutputStreamWriter(FileOutputStream(file), Charsets.UTF_8).use { writer ->
            writer.write("#separator:tab\n")
            writer.write("#html:true\n")
            notes().forEach { note ->
                note.forEachIndexed { index, part ->
                    if (index > 0) {
                        writer.write("\t")
                    }
                    writer.write(part)
                }
                writer.write("\n")
            }
        }
    }
}