import argparse
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

FONT_FACE_CSS = """\
@font-face { font-family: "宋體繁"; src: local("STSongTC-Light"), local("STSongTC"); }
@font-face { font-family: "宋體繁"; font-weight: bold; src: local("STSongTC-Bold"); }
@font-face { font-family: "黑體繁"; src: local("STHeitiTC-Light"), local("STHeitiTC"); }
@font-face { font-family: "黑體繁"; font-weight: bold; src: local("STHeitiTC-Medium"); }
@font-face { font-family: "楷體繁"; src: local("STKaitiTC"), local("STKaitiTC-Regular"); }
@font-face { font-family: "楷體繁"; font-weight: bold; src: local("STKaitiTC-Bold"); }
@font-face { font-family: "圓體繁"; src: local("STYuanTC-Light"), local("STYuanTC"); }
@font-face { font-family: "圓體繁"; font-weight: bold; src: local("STYuanTC-Bold"); }
@font-face { font-family: "宋體"; src: local("STSong"), local("STSong-Regular"); }
@font-face { font-family: "黑體"; src: local("STHeiti"), local("STHeiti-Regular"); }
@font-face { font-family: "楷體"; src: local("STKai"), local("STKai-Regular"); }
@font-face { font-family: "圓體"; src: local("STYuan"), local("STYuan-Regular"); }
@font-face { font-family: "TBMincho"; src: local("TBMincho-Regular"); }
@font-face { font-family: "TBGothic"; src: local("TBGothic-Regular"); }
@font-face { font-family: "TsukushiMincho"; src: local("TsukushiMincho-Regular"); }
"""

EXTRA_CSS = """\
body {
  writing-mode: vertical-rl;
  -webkit-writing-mode: vertical-rl;
  -epub-writing-mode: vertical-rl;
}
body, p {
  font-family: "宋體繁";
}
h1, h2, h3, h4, h5, h6 {
  font-family: "黑體繁";
}
blockquote, blockquote p {
  font-family: "楷體繁";
}
"""

OPF_NAMESPACES = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}

CONTAINER_NS = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}


HEADING_RE = re.compile(r"^h[1-6]$", re.IGNORECASE)


def _strip_font_family_from_style(style_value):
    """Remove font-family declarations from an inline CSS style string."""
    result = re.sub(r"\s*font-family\s*:[^;]*;?", "", style_value)
    return result.strip()


def strip_css_font_family(css):
    """Remove font-family declarations from CSS (original stylesheet content)."""
    return re.sub(r"[ \t]*font-family\s*:[^;]*;\n?", "", css)


def strip_body_inline_fonts(xhtml):
    """Strip font-family from inline styles on non-heading elements in XHTML."""

    def _process_tag(match):
        tag_name = match.group(1)
        attrs = match.group(2) or ""

        # Get local name without any namespace prefix
        local_name = tag_name.rsplit(":", 1)[-1]

        # Keep headings unchanged
        if HEADING_RE.match(local_name):
            return match.group(0)

        if "font-family" not in attrs:
            return match.group(0)

        def _fix_style(m):
            quote = m.group(1)
            value = m.group(2)
            new_value = _strip_font_family_from_style(value)
            if not new_value:
                return ""
            return f"style={quote}{new_value}{quote}"

        new_attrs = re.sub(r'style=(["\'])(.*?)\1', _fix_style, attrs)
        new_attrs = re.sub(r"  +", " ", new_attrs)
        return f"<{tag_name}{new_attrs}>"

    return re.sub(r"<([a-zA-Z][\w:-]*)(\s[^>]*)?\s*/?>", _process_tag, xhtml)


def find_opf_path(zip_file):
    """Find the OPF file path via META-INF/container.xml, or by extension."""
    if "META-INF/container.xml" in zip_file.namelist():
        container_xml = zip_file.read("META-INF/container.xml")
        root = ET.fromstring(container_xml)
        rootfiles = root.findall(
            ".//container:rootfile", CONTAINER_NS
        )
        for rf in rootfiles:
            path = rf.get("full-path")
            if path and path.endswith(".opf"):
                return path

    for name in zip_file.namelist():
        if name.endswith(".opf"):
            return name

    return None


def modify_css(content):
    """Prepend font-face declarations and append writing-mode rules to CSS."""
    content = strip_css_font_family(content)
    return FONT_FACE_CSS + "\n" + content + "\n" + EXTRA_CSS


def modify_opf(content):
    """Modify OPF XML: set language, writing mode meta, and spine direction."""
    for prefix, uri in OPF_NAMESPACES.items():
        ET.register_namespace(prefix, uri)
    ET.register_namespace("", OPF_NAMESPACES["opf"])

    root = ET.fromstring(content)

    # Find or create dc:language and set to zh-tw
    metadata = root.find("opf:metadata", OPF_NAMESPACES)
    if metadata is None:
        metadata = root.find("metadata")
    if metadata is None:
        raise ValueError("No <metadata> element found in OPF file")

    lang_elem = metadata.find("dc:language", OPF_NAMESPACES)
    if lang_elem is None:
        lang_elem = ET.SubElement(
            metadata, f'{{{OPF_NAMESPACES["dc"]}}}language'
        )
    lang_elem.text = "zh-tw"

    # Add primary-writing-mode meta if not present
    has_writing_mode = False
    for meta in metadata.findall("opf:meta", OPF_NAMESPACES):
        if meta.get("name") == "primary-writing-mode":
            meta.set("content", "vertical-rl")
            has_writing_mode = True
            break
    if not has_writing_mode:
        for meta in metadata.findall("meta"):
            if meta.get("name") == "primary-writing-mode":
                meta.set("content", "vertical-rl")
                has_writing_mode = True
                break
    if not has_writing_mode:
        new_meta = ET.SubElement(metadata, "meta")
        new_meta.set("name", "primary-writing-mode")
        new_meta.set("content", "vertical-rl")

    # Set page-progression-direction on <spine>
    spine = root.find("opf:spine", OPF_NAMESPACES)
    if spine is None:
        spine = root.find("spine")
    if spine is not None:
        spine.set("page-progression-direction", "rtl")

    xml_decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
    tree_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return xml_decl + tree_bytes


def process_epub(input_path, output_path):
    """Process an EPUB file: modify CSS and OPF, write to output."""
    opf_path = None
    entries = {}

    with zipfile.ZipFile(input_path, "r") as zin:
        opf_path = find_opf_path(zin)

        for info in zin.infolist():
            data = zin.read(info.filename)
            entries[info.filename] = (info, data)

    # Modify CSS files
    for filename in list(entries.keys()):
        if filename.lower().endswith(".css"):
            info, data = entries[filename]
            modified = modify_css(data.decode("utf-8"))
            entries[filename] = (info, modified.encode("utf-8"))

    # Strip inline font-family from body elements in XHTML files
    for filename in list(entries.keys()):
        if filename.lower().endswith((".xhtml", ".html", ".htm")):
            info, data = entries[filename]
            modified = strip_body_inline_fonts(data.decode("utf-8"))
            entries[filename] = (info, modified.encode("utf-8"))

    # Modify OPF file
    if opf_path and opf_path in entries:
        info, data = entries[opf_path]
        modified = modify_opf(data.decode("utf-8"))
        entries[opf_path] = (info, modified.encode("utf-8"))
    else:
        print("Warning: No OPF file found in EPUB")

    # Write output EPUB
    with zipfile.ZipFile(output_path, "w") as zout:
        # mimetype must be first and uncompressed per EPUB spec
        if "mimetype" in entries:
            info, data = entries.pop("mimetype")
            zout.writestr(
                "mimetype", data, compress_type=zipfile.ZIP_STORED
            )

        for filename, (info, data) in entries.items():
            zout.writestr(info, data)

    print(f"Written to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Modify EPUB for Traditional Chinese vertical text (Kindle-ready)"
    )
    parser.add_argument("input", help="Input EPUB file path")
    parser.add_argument(
        "--output", "-o",
        help="Output EPUB file path (default: <input>_vertical.epub)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")
    if not input_path.suffix.lower() == ".epub":
        parser.error(f"Input file is not an EPUB: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_stem(input_path.stem + "_vertical")

    if output_path.resolve() == input_path.resolve():
        parser.error("Output path must differ from input path")

    process_epub(input_path, output_path)


if __name__ == "__main__":
    main()
