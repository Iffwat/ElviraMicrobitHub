from microbithub.transport.base import LineBuffer


def test_lines_split_across_chunks():
    buf = LineBuffer()
    assert buf.feed(b"VAL:A1") == []
    assert buf.feed(b":512\nVAL:A") == ["VAL:A1:512"]
    assert buf.feed(b"2:3\n") == ["VAL:A2:3"]


def test_crlf_and_empty_lines():
    buf = LineBuffer()
    assert buf.feed(b"HB:1\r\n\r\n\nHB:2\n") == ["HB:1", "HB:2"]


def test_multibyte_character_split():
    data = "LOG:café\n".encode()
    buf = LineBuffer()
    cut = data.index(b"\xc3") + 1  # split inside the 2-byte 'e acute'
    assert buf.feed(data[:cut]) == []
    assert buf.feed(data[cut:]) == ["LOG:café"]
