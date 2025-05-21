


def format_definitions_html(def_dict):
    entries = def_dict.get("def")
    def get_definitions(def_parent, html_parts):
        if not def_parent or not isinstance(def_parent, dict):
            return def_parent
        if 'defs' in def_parent:
            html_parts.append('<ol>') # Numbered list for main definitions
            for def_num, def_detail in def_parent['defs'].items():
                html_parts.append(f'<li>{def_detail.get("def", "No definition text.")}')

                # Safely get the example ("ex")
                example = def_detail.get("ex")
                if example:
                    html_parts.append(f'<br><em><small>Ex: {example}</small></em>')

                html_parts.append('</li>')
            html_parts.append('</ol>')
        if 'def' in def_parent:
            html_parts.append(f'<ul><li>{def_parent.get("def", "No definition text.")}')

            # Safely get the example ("ex")
            example = def_parent.get("ex")
            if example:
                html_parts.append(f'<br><em><small>Ex: {example}</small></em>')

            html_parts.append('</li></ul>')

        return html_parts

    html_parts = []

    # Handle inflections first, if they exist
    inflections = entries.get('inflections')
    if inflections:
        html_parts.append(f'<p style="margin-bottom: 0">Generic variants: {", ".join(inflections)}</p>')
        # Start the main list of entries with a style if inflections were present
        html_parts.append('<ol style="margin-top: 0">')
    else:
        # No inflections, just start the main list of entries
        html_parts.append('<ol>')

    # Get actual word entries, excluding 'inflections'
    # Sort by key to ensure consistent order if keys are like "0", "1", "2"
    entry_keys = sorted([k for k in entries.keys() if k != 'inflections'])

    if not entry_keys and not inflections:
        return "<p>No definition data found.</p>" # Or just return an empty string: ""

    if not entry_keys and inflections: # Only inflections, no actual entries
        html_parts.append('</ol>') # Close the opened <ol>
        return "".join(html_parts)

    for entry_id in entry_keys:
        entry = entries[entry_id]

        html_parts.append(f'<li><b>{entry.get("word", "N/A")}</b>') # Use .get for safety on "word" too

        if "POS" in entry:
            html_parts.append(f' <small>({entry["POS"]})</small>')

        inflections = entry.get('inflections')
        if inflections:
            html_parts.append(f'<br><em>Variations: {", ".join(inflections)}</em>')

        # Handle sub-parts of speech (subPOS) if they exist
        if 'subPOS' in entry:
            for sense_type, sense_data in entry['subPOS'].items():
                html_parts.append(f'<ul><li>{sense_type}') # List for sense type
                html_parts = get_definitions(sense_data, html_parts)
                html_parts.append('</li></ul>') # Close sense_type li and ul

        # Handle main definitions if they exist
        html_parts = get_definitions(entry, html_parts)

        html_parts.append('</li>') # Close the main list item for this entry

    html_parts.append('</ol>') # Close the main list of all entries

    def_dict['def'] = "".join(html_parts)

    alt_list = []
    for key in def_dict:
        if key.startswith("alt_def"):
            def_dict["def"] += "<p>See also:</p>"
            def_dict["def"] += format_definitions_html(def_dict[key])["def"]
            alt_list.append(key)

    for key in alt_list:
        del def_dict[key]

    return def_dict


# --- Entry point ---
def test(word="spell"):
    import json
    from definitionLookup import def_lookup
    from bs4 import BeautifulSoup
    response = def_lookup(word)
    html_code = format_definitions_html(response["def"])
    print(BeautifulSoup(html_code, "html.parser").prettify())
    return html_code

