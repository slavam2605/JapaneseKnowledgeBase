package server

import java.awt.Color
import java.awt.image.BufferedImage

class KanjiVisualCompare {
    private val renderCache = mutableMapOf<String, KanjiRender>()

    fun getOrCreateRender(kanji: String): KanjiRender {
        if (kanji in renderCache)
            return renderCache[kanji]!!

        val render = KanjiRender(kanji)
        renderCache[kanji] = render
        return render
    }

    class KanjiRender(val kanji: String) {
        val data = Array(RenderSize) { BooleanArray(RenderSize) }

        init {
            val render = BufferedImage(RenderSize, RenderSize, BufferedImage.TYPE_BYTE_GRAY)
            val graphics = render.createGraphics()
            graphics.background = Color.WHITE
            graphics.color = Color.BLACK
            graphics.clearRect(0, 0, RenderSize, RenderSize)
            graphics.font = graphics.font.deriveFont(RenderSize.toFloat())

            val metrics = graphics.getFontMetrics(graphics.font)
            val x = (RenderSize - metrics.stringWidth(kanji)) / 2
            val y = (RenderSize - metrics.height) / 2 + metrics.ascent
            graphics.drawString(kanji, x, y)
            for (i in 0 until RenderSize) {
                for (j in 0 until RenderSize) {
                    data[i][j] = render.getRGB(i, j) != -1
                }
            }
        }

        companion object {
            const val RenderSize = 400
        }
    }
}