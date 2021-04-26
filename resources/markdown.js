class HtmlBuilder {
    text = "";
    #listStack = [];

    enterList(isNumbered) {
        console.log("enterList(" + isNumbered + ")")
        this.#listStack.push(isNumbered);
        this.text += isNumbered ? "<ol>" : "<ul>";
    }

    leaveList() {
        console.log("leaveList");
        const isNumbered = this.#listStack.pop();
        this.text += isNumbered ? "</ol>" : "</ul>";
    }

    setListLevel(indentLevel, isNumbered) {
        let listLevel = indentLevel < 0 ? 0 : (Math.round(indentLevel / 4.0) + 1);
        console.log(listLevel);
        while (this.#listStack.length > listLevel) {
            this.leaveList();
        }
        if (listLevel > 0 && this.#listStack.length === listLevel && this.#listStack[listLevel - 1] !== isNumbered) {
            this.leaveList();
        }
        while (this.#listStack.length < listLevel) {
            this.enterList(isNumbered)
        }
    }
}

function replaceBold(s) {
    return s.replace(/\*\*(.*?)\*\*/g, (_, x) => "<b>" + x + "</b>");
}

function replaceUnderscoreItalic(s) {
    return s.replace(/\b_(.*?)_/g, (_, x) => "<i>" + x + "</i>");
}

function replaceStaredItalic(s) {
    return s.replace(/\*(.*?)\*/g, (_, x) => "<i>" + x + "</i>");
}

function replaceCode(s) {
    return s.replace(/`(.*?)`/g, (_, x) => "<code>" + x + "</code>");
}

function getIndentBeforeListMarker(s) {
    let indent = 0;
    while (indent < s.length && s[indent] === " ") {
        indent++;
    }
    let index = indent;
    if (index >= s.length)
        return [-1, 0, 0];

    if (s[index] >= '0' && s[index] <= '9') {
        let number = "";
        while (index < s.length && s[index] >= '0' && s[index] <= '9') {
            number += s[index];
            index++;
        }
        if (index + 1 < s.length && s[index] === '.' && s[index + 1] === ' ')
            return [indent, parseInt(number), index + 2];
    } else if (s[index] === '-' || s[index] === '+' || s[index] === '*') {
        index++;
        if (index < s.length && s[index] === ' ')
            return [indent, s[index - 1], index + 1];
    }
    return [-1, 0, 0]
}

function processHeader(s, postProcessors) {
    if (s[0] !== '#')
        return s;

    let level = 0;
    while (s[level] === "#") {
        level++;
    }
    if (s[level] !== ' ')
        return s;

    postProcessors.push(x => "<h" + level + ">" + x + "</h" + level + ">");
    return s.substring(level) ;
}

function processListItem(s, postProcessors, builder) {
    const [olIndentLevel, olItemMarker, olPrefixLength] = getIndentBeforeListMarker(s);
    console.log(s);
    builder.setListLevel(olIndentLevel, typeof olItemMarker === "number");
    if (olIndentLevel >= 0) {
        postProcessors.push(x => "<li>" + x + "</li>");
    }
    return s.substring(olPrefixLength);
}

function replaceLineBreak(s) {
    if (!s.endsWith("  "))
        return s;

    return s.substring(0, s.length - 2) + "<br>";
}

function ensureSpace(s, builder) {
    if (builder.text.endsWith(">") || s.startsWith("<")) {
        return s;
    }
    return " " + s;
}

function parseLine(line, builder) {
    const postProcessors = [];

    let result = line;
    result = processHeader(result, postProcessors);
    result = processListItem(result, postProcessors, builder);

    result = replaceBold(result);
    result = replaceStaredItalic(result);
    result = replaceUnderscoreItalic(result);
    result = replaceCode(result);
    result = replaceLineBreak(result);

    postProcessors.forEach(p => result = p(result));
    result = ensureSpace(result, builder);
    builder.text += result;
}

function parseText(text) {
    const lines = text.split(/\r?\n/);
    const builder = new HtmlBuilder();
    lines.forEach(s => parseLine(s, builder));
    return builder.text;
}

document.addEventListener("DOMContentLoaded", () => {
    const markdownElements = document.getElementsByClassName("markdown");
    Array.from(markdownElements).forEach(element => {
        element.innerHTML = parseText(element.innerHTML);
    });
});