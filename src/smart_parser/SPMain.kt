package smart_parser

fun main() {
//    SmartParser("""
//        日本では、むかしから引っ越しをしたとき、近所の家へあいさつに行く習慣があります。
//        「これからいろいろお世話になります。どうぞよろしくお願いします。」という意味です。
//        アパートやマンションでは、自分の部屋の隣に住んでいる人や、上の部屋と下の部屋に
//        住んでいる人などにあいさつをします。引っ越しをしたら、すぐにあいさつに行きましょう。
//        あいさつに行くときは、小さな品物を持って行くことが多いです。例えば、タオルやせっけん、
//        おかしなどです。しかし、大事なのはあいさつをすることなのですから、どんな物を持って
//        行くかはあまり心配しなくてもいいです。あいさつに行ったけれども、留守だったときは、
//        あいさつのことばを書いた手紙などを玄関のポストに入れておくのがいいです。
//        最近は、「引っ越しのあいさつ」をしない人も多くなっています。特に、一人で住むときは、
//        あいさつをしない人がたくさんいます。しかし、私は「引っ越しのあいさつ」は、
//        やはりいい習慣と思います。
//    """.trimIndent()).parse()

    val result = SmartParser("これは猫です").parseSentence(0)
    for (item in result) {
        val (w1, w2) = item.value
        println("$w1 ::: $w2")
    }
}