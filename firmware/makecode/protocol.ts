/**
 * MicrobitHub protocol v2: pure string helpers (no hardware calls).
 *
 * Line format: <TYPE>[:<payload>][*<checksum>]
 *   checksum = XOR of the UTF-8 bytes before '*', as 2 upper-case hex digits.
 * Free text is escaped: % -> %25, * -> %2A, , -> %2C, LF -> %0A, CR -> %0D.
 *
 * Must match src/microbithub/core/protocol.py. Written in the subset of
 * TypeScript that MakeCode (Static TypeScript) and Node both accept:
 * no regular expressions, no Map, no exceptions.
 */
namespace microbithub {
    export const PROTOCOL_VERSION = 2

    const HEX = "0123456789ABCDEF"

    /** Two upper-case hex digits for 0..255. */
    export function hex2(n: number): string {
        return HEX.charAt((n >> 4) & 15) + HEX.charAt(n & 15)
    }

    function isHexDigit(c: string): boolean {
        return c.length == 1 && "0123456789ABCDEFabcdef".indexOf(c) >= 0
    }

    /** XOR of the UTF-8 bytes of ``body``. */
    export function checksum(body: string): string {
        let x = 0
        let i = 0
        while (i < body.length) {
            let cp = body.charCodeAt(i)
            // Node strings are UTF-16: join surrogate pairs. MakeCode returns
            // whole code points, so this branch never runs there.
            if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < body.length) {
                const lo = body.charCodeAt(i + 1)
                if (lo >= 0xdc00 && lo <= 0xdfff) {
                    cp = 0x10000 + ((cp - 0xd800) << 10) + (lo - 0xdc00)
                    i++
                }
            }
            if (cp < 0x80) {
                x ^= cp
            } else if (cp < 0x800) {
                x ^= 0xc0 | (cp >> 6)
                x ^= 0x80 | (cp & 0x3f)
            } else if (cp < 0x10000) {
                x ^= 0xe0 | (cp >> 12)
                x ^= 0x80 | ((cp >> 6) & 0x3f)
                x ^= 0x80 | (cp & 0x3f)
            } else {
                x ^= 0xf0 | (cp >> 18)
                x ^= 0x80 | ((cp >> 12) & 0x3f)
                x ^= 0x80 | ((cp >> 6) & 0x3f)
                x ^= 0x80 | (cp & 0x3f)
            }
            i++
        }
        return hex2(x)
    }

    export function escape(text: string): string {
        let out = ""
        for (let i = 0; i < text.length; i++) {
            const c = text.charAt(i)
            if (c == "%") out += "%25"
            else if (c == "*") out += "%2A"
            else if (c == ",") out += "%2C"
            else if (c == "\n") out += "%0A"
            else if (c == "\r") out += "%0D"
            else out += c
        }
        return out
    }

    /** Reverses ``escape``. Any other '%' sequence is kept as it is. */
    export function unescape(text: string): string {
        if (text.indexOf("%") < 0) return text
        let out = ""
        let i = 0
        while (i < text.length) {
            const c = text.charAt(i)
            if (c == "%" && i + 2 < text.length) {
                const code = text.substr(i + 1, 2).toUpperCase()
                let decoded = ""
                if (code == "25") decoded = "%"
                else if (code == "2A") decoded = "*"
                else if (code == "2C") decoded = ","
                else if (code == "0A") decoded = "\n"
                else if (code == "0D") decoded = "\r"
                if (decoded != "") {
                    out += decoded
                    i += 3
                    continue
                }
            }
            out += c
            i++
        }
        return out
    }

    function isDigit(c: string): boolean {
        return c.length == 1 && "0123456789".indexOf(c) >= 0
    }

    function isLetter(c: string): boolean {
        if (c.length != 1) return false
        const n = c.charCodeAt(0)
        return (n >= 65 && n <= 90) || (n >= 97 && n <= 122)
    }

    /** True for "[+-]?digits" (the protocol's integer syntax). */
    export function isInteger(raw: string): boolean {
        let start = 0
        if (raw.length > 0 && (raw.charAt(0) == "+" || raw.charAt(0) == "-")) start = 1
        if (raw.length <= start) return false
        for (let i = start; i < raw.length; i++) {
            if (!isDigit(raw.charAt(i))) return false
        }
        return true
    }

    /** Integer value of "[+-]?digits"; call ``isInteger`` first. */
    export function toInteger(raw: string): number {
        let sign = 1
        let i = 0
        if (raw.charAt(0) == "-") { sign = -1; i = 1 }
        else if (raw.charAt(0) == "+") { i = 1 }
        let n = 0
        for (; i < raw.length; i++) n = n * 10 + (raw.charCodeAt(i) - 48)
        return sign * n
    }

    /**
     * Parse a value for a numeric card: an integer, or a decimal such as
     * "12.6" (rounded to 13). Returns [ok, value] with ok = 1 or 0, because
     * MakeCode code avoids exceptions.
     */
    export function parseNumber(raw: string): number[] {
        const s = raw.trim()
        if (isInteger(s)) return [1, toInteger(s)]
        const dot = s.indexOf(".")
        if (dot < 0) return [0, 0]
        let whole = s.substr(0, dot)
        const frac = s.substr(dot + 1)
        if (frac.length == 0 && (whole == "" || whole == "-" || whole == "+")) return [0, 0]
        for (let i = 0; i < frac.length; i++) if (!isDigit(frac.charAt(i))) return [0, 0]
        let negative = false
        if (whole.charAt(0) == "-") { negative = true; whole = whole.substr(1) }
        else if (whole.charAt(0) == "+") { whole = whole.substr(1) }
        if (whole != "" && !isInteger(whole)) return [0, 0]
        let n = whole == "" ? 0 : toInteger(whole)
        if (frac.length > 0 && frac.charCodeAt(0) - 48 >= 5) n += 1
        return [1, negative ? -n : n]
    }

    /** Card IDs: a letter, then up to 15 letters, digits or '_'. */
    export function isValidId(id: string): boolean {
        if (id.length < 1 || id.length > 16 || !isLetter(id.charAt(0))) return false
        for (let i = 1; i < id.length; i++) {
            const c = id.charAt(i)
            if (!(isLetter(c) || isDigit(c) || c == "_")) return false
        }
        return true
    }

    /** A received line split into tag and payload, or an error. */
    export class ParsedLine {
        constructor(public tag: string, public payload: string, public error: string) { }
    }

    /**
     * Check the optional checksum and split ``TAG:payload``.
     * The tag is upper-cased and trimmed, as in protocol.py.
     */
    export function parseLine(raw: string): ParsedLine {
        let line = raw
        while (line.length > 0 && (line.charAt(line.length - 1) == "\r" || line.charAt(line.length - 1) == "\n")) {
            line = line.substr(0, line.length - 1)
        }
        if (line.length == 0) return new ParsedLine("", "", "empty line")

        let body = line
        const n = line.length
        if (n >= 3 && line.charAt(n - 3) == "*" && isHexDigit(line.charAt(n - 2)) && isHexDigit(line.charAt(n - 1))) {
            body = line.substr(0, n - 3)
            if (checksum(body) != line.substr(n - 2, 2).toUpperCase()) {
                return new ParsedLine("", "", "checksum mismatch")
            }
        }
        const colon = body.indexOf(":")
        const tag = (colon < 0 ? body : body.substr(0, colon)).trim().toUpperCase()
        const payload = colon < 0 ? "" : body.substr(colon + 1)
        return new ParsedLine(tag, payload, "")
    }
}
