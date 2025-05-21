import html


def format_dictionary_html(data):
    def format_definitions(defs, indent=4):
        lines = []
        indent_str = '&nbsp;' * indent
        ex_indent_str = '&nbsp;' * (indent + 2)

        for value in defs.values():
            if isinstance(value, dict) and "def" in value:
                definition = html.escape(capitalize(value['def']))
                lines.append(f"{indent_str}- {definition}<br>")
                if "ex" in value:
                    example = html.escape(value['ex'])
                    lines.append(f"{ex_indent_str}- Ex: {example}<br>")
            elif isinstance(value, dict):
                lines.extend(format_definitions(value, indent))
        return lines

    def capitalize(text):
        return text[0].upper() + text[1:] if text else text

    output_lines = []
    for idx, entry in data.items():
        header = f"{idx}) {html.escape(entry['word'])} ({html.escape(entry['POS'])})"
        output_lines.append(f"<strong>{header}</strong><br>")

        if "inflections" in entry:
            inflections = ', '.join(html.escape(i) for i in entry["inflections"])
            output_lines.append(f"&nbsp;&nbsp;- Variations: {inflections}<br>")

        if "subPOS" in entry:
            for sub, defs in entry["subPOS"].items():
                output_lines.append(f"&nbsp;&nbsp;- {capitalize(html.escape(sub))}:<br>")
                output_lines.extend(format_definitions(defs, indent=6))

        if "definitions" in entry:
            output_lines.extend(format_definitions(entry["definitions"], indent=4))

        output_lines.append("<br>")  # Add spacing between entries

    return ''.join(output_lines)


def test(word = "spell"):
    from definitionLookup import def_lookup
    full_def = def_lookup(word)
    html_output = format_dictionary_html(full_def["def"])
    return html_output
