package dict

enum class PartOfSpeech(val description: String, val localizedDescription: String? = null) {
    ADJ_F("noun or verb acting prenominally"),
    ADJ_I("adjective (keiyoushi)", "い-прилагательное"),
    ADJ_IX("adjective (keiyoushi) - yoi/ii class", "い-прилагательное - よい/いい класс"),
    ADJ_KARI("kari adjective (archaic)"),
    ADJ_KU("ku adjective (archaic)"),
    ADJ_NA("adjectival nouns or quasi-adjectives (keiyodoshi)", "な-прилагательное"),
    ADJ_NARI("archaic/formal form of na-adjective"),
    ADJ_NO("nouns which may take the genitive case particle `no'", "の-прилагательное"),
    ADJ_PN("pre-noun adjectival (rentaishi)"),
    ADJ_SHIKU("shiku adjective (archaic)"),
    ADJ_T("`taru' adjective"),
    ADV("adverb (fukushi)"),
    ADV_TO("adverb taking the `to' particle"),
    AUX("auxiliary"),
    AUX_ADJ("auxiliary adjective"),
    AUX_V("auxiliary verb"),
    CONJ("conjunction"),
    COP("copula"),
    CTR("counter"),
    EXP("Expressions (phrases, clauses, etc.)"),
    INT("interjection (kandoushi)"),
    N("noun (common) (futsuumeishi)", "существительное"),
    N_ADV("adverbial noun (fukushitekimeishi)"),
    N_PR("proper noun"),
    N_PREF("noun, used as a prefix"),
    N_SUF("noun, used as a suffix"),
    N_T("noun (temporal) (jisoumeishi)"),
    NUM("numeric"),
    PN("pronoun"),
    PREF("prefix"),
    PRT("particle"),
    SUF("suffix"),
    UNC("unclassified"),
    V_UNSPEC("verb unspecified"),
    V1("Ichidan verb"),
    V1_S("Ichidan verb - kureru special class"),
    V2A_S("Nidan verb with 'u' ending (archaic)"),
    V2B_K("Nidan verb (upper class) with bu ending (archaic)"),
    V2B_S("Nidan verb (lower class) with bu ending (archaic)"),
    V2D_K("Nidan verb (upper class) with dzu ending (archaic)"),
    V2D_S("Nidan verb (lower class) with dzu ending (archaic)"),
    V2G_K("Nidan verb (upper class) with gu ending (archaic)"),
    V2G_S("Nidan verb (lower class) with gu ending (archaic)"),
    V2H_K("Nidan verb (upper class) with hu/fu ending (archaic)"),
    V2H_S("Nidan verb (lower class) with hu/fu ending (archaic)"),
    V2K_K("Nidan verb (upper class) with ku ending (archaic)"),
    V2K_S("Nidan verb (lower class) with ku ending (archaic)"),
    V2M_K("Nidan verb (upper class) with mu ending (archaic)"),
    V2M_S("Nidan verb (lower class) with mu ending (archaic)"),
    V2N_S("Nidan verb (lower class) with nu ending (archaic)"),
    V2R_K("Nidan verb (upper class) with ru ending (archaic)"),
    V2R_S("Nidan verb (lower class) with ru ending (archaic)"),
    V2S_S("Nidan verb (lower class) with su ending (archaic)"),
    V2T_K("Nidan verb (upper class) with tsu ending (archaic)"),
    V2T_S("Nidan verb (lower class) with tsu ending (archaic)"),
    V2W_S("Nidan verb (lower class) with u ending and we conjugation (archaic)"),
    V2Y_K("Nidan verb (upper class) with yu ending (archaic)"),
    V2Y_S("Nidan verb (lower class) with yu ending (archaic)"),
    V2Z_S("Nidan verb (lower class) with zu ending (archaic)"),
    V4B("Yodan verb with bu ending (archaic)"),
    V4G("Yodan verb with gu ending (archaic)"),
    V4H("Yodan verb with `hu/fu' ending (archaic)"),
    V4K("Yodan verb with ku ending (archaic)"),
    V4M("Yodan verb with mu ending (archaic)"),
    V4N("Yodan verb with nu ending (archaic)"),
    V4R("Yodan verb with `ru' ending (archaic)"),
    V4S("Yodan verb with su ending (archaic)"),
    V4T("Yodan verb with tsu ending (archaic)"),
    V5ARU("Godan verb - -aru special class"),
    V5B("Godan verb with `bu' ending"),
    V5G("Godan verb with `gu' ending"),
    V5K("Godan verb with `ku' ending"),
    V5K_S("Godan verb - Iku/Yuku special class"),
    V5M("Godan verb with `mu' ending"),
    V5N("Godan verb with `nu' ending"),
    V5R("Godan verb with `ru' ending"),
    V5R_I("Godan verb with `ru' ending (irregular verb)"),
    V5S("Godan verb with `su' ending"),
    V5T("Godan verb with `tsu' ending"),
    V5U("Godan verb with `u' ending"),
    V5U_S("Godan verb with `u' ending (special class)"),
    V5URU("Godan verb - Uru old class verb (old form of Eru)"),
    VI("intransitive verb", "переходный глагол"),
    VK("Kuru verb - special class"),
    VN("irregular nu verb"),
    VR("irregular ru verb, plain form ends with -ri"),
    VS("noun or participle which takes the aux. verb suru", "する-глагол"),
    VS_C("su verb - precursor to the modern suru"),
    VS_I("suru verb - included"),
    VS_S("suru verb - special class"),
    VT("transitive verb", "переходный глагол"),
    VZ("Ichidan verb - zuru verb (alternative form of -jiru verbs)");

    val prettyDescription: String
        get() = localizedDescription ?: description

    companion object {
        val DanVerbs = listOf(
            V1, V1_S, V5ARU, V5B, V5G, V5K, V5K_S, V5M, V5N, V5R, V5R_I, V5S, V5T, V5U, V5U_S, V5URU
        )
        val SuruVerbs = listOf(
            VS, VS_C, VS_I, VS_S
        )
        val IAdjectives = listOf(
            ADJ_I, ADJ_IX
        )

        fun fromDescription(description: String): PartOfSpeech? {
            fun normalize(text: String) = text
                .lowercase()
                .replace("`", "")
                .replace("'", "")

            return values().find {
                normalize(it.description) == normalize(description)
            }
        }
    }
}