package utils

import kotlin.math.roundToInt

fun convertDaysToString(days: Int): String {
    return when {
        days < 30 -> "$days дней"
        days < 365 -> "${(days / 3.0).roundToInt() / 10.0} месяцев"
        else -> "${(days / 36.5).roundToInt() / 10.0} лет"
    }
}