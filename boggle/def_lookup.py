from bs4 import BeautifulSoup
import copy
import json
import re
import requests


def capitalize_string(text=''):
    text = str(text)
    if text:
        return text[0].upper() + text[1:]
    else:
        return text


def set_nested_dict2(root, keys, value):
    """Safely set a nested dictionary value without using exec()."""
    d = root
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


def url_lookup(word):
    url = f'https://www.merriam-webster.com/dictionary/{word}'
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        #return ("Error fetching page:", e)
        return {"status":False, "def":f'Error fetching page: {e}'}


def non_standard_definitions(entry_section):
    # Placeholder for now
    # This next section is for words with the cxl-ref class
    # <a class="cxt" href="night"><span class="text-uppercase">night</span></a>
    full_def = {
        "word": entry_section.find(class_="hword").text,
        "def": "Unable to parse the definition."
    }
    cxt_ref_check = entry_section.find(class_="cxt")
    if cxt_ref_check:
        try:
            full_def["alt_def"] = def_lookup(cxt_ref_check.text)
        except:
            full_def["alt_def"] = f'Unable to define: {cxt_ref_check.text}'
    cxl_ref_check = entry_section.find(class_="cxl-ref")
    if cxl_ref_check:
        full_def["def"] = capitalize_string(re.sub(r'\n', " ", cxl_ref_check.text).lstrip().rstrip())
    return full_def


def set_nested_dict(d, path, value):
    """Sets a nested dictionary based on the path."""
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def extract_pos(definition):
    pos_tag = definition.find(class_="parts-of-speech")
    return capitalize_string(re.sub(r' \([0-9]\)', "", pos_tag.text) if pos_tag else "unknown")


def extract_inflections(definition):
    inflection_results = []
    for inflection in definition.find_all(class_="va"):
        inflection_results.append(inflection)
    for inflection in definition.find_all(class_="if"):
        inflection_results.append(inflection)
    inflection_results = set(inflection_results)
    return [inf.text for inf in inflection_results] if inflection_results else []


def check_duplicate_inflections(full_def):
    if not full_def.get('inflections'):
        return full_def
    extra_inflections = []
    for inflection in full_def['inflections']:
        if inflection in extra_inflections: continue
        for val in full_def:
            if not isinstance(val, int) or not full_def[val].get('inflections'): continue
            if inflection in full_def[val].get('inflections'):
                extra_inflections.append(inflection)
                break
    #print(extra_inflections)
    for inflection in extra_inflections:
        full_def['inflections'].remove(inflection)
    return full_def


def parse_standard_definition_block(definition, def_count):
    full_def = {
        "word": definition.find(class_="hword").text,
        "POS": extract_pos(definition)
    }

    inflections = extract_inflections(definition)
    if inflections:
        full_def["inflections"] = inflections

    def_items = definition.find_all(class_="vg")
    #<span class="sl badge mw-badge-gray-100 text-start text-wrap d-inline">informal + impolite</span>
    definitions = {}
    subpos_blocks = {}

    for def_item in def_items:
        sub_pos_tag = def_item.find(class_="vd")
        entries = def_item.find_all(class_="vg-sseq-entry-item")

        current_block = {}  # Will hold numbered definitions
        def_index = 1

        for entry in entries:
            senses = entry.find_all(class_=re.compile(r'sb-\d sb-entry'))
            for new_item in senses:
                sense_blocks = new_item.find_all(class_="sense")
                for sense in sense_blocks:
                    entry_data = {"def":False}
                    #<span class="lb badge mw-badge-gray-100 text-start text-wrap d-inline">often not capitalized</span>
                    dt_text = sense.find(class_="dtText")

                    if dt_text and dt_text.text:
                        entry_data["def"] = capitalize_string(dt_text.text.lstrip(": "))
                    unText = sense.find(class_="unText")
                    if unText and unText.text:
                        if entry_data["def"]:
                            entry_data["def"] += f' -- {unText.text}'
                        else:
                            entry_data["def"] = capitalize_string(unText.text)
                    if not entry_data["def"]:
                        entry_data["def"] = "Unable to parse a definition."
                    example = sense.find(class_="sub-content-thread")
                    if example and example.text:
                        entry_data["ex"] = capitalize_string(example.text)
                    if entry_data:
                        current_block[def_index] = entry_data
                        def_index += 1

        if sub_pos_tag:
            label = sub_pos_tag.text.title()
            subpos_blocks.setdefault(label, {"defs": {}})["defs"].update(current_block)
        else:
            definitions.update(current_block)

    if subpos_blocks:
        full_def["subPOS"] = subpos_blocks
    if definitions:
        full_def["defs"] = definitions

    return full_def


def def_lookup(word, debug=False):
    response = url_lookup(word)
    if isinstance(response, dict):  # error occurred
        return response

    def_response = {"status":True}
    full_def = {}
    soup = BeautifulSoup(response.text, "html.parser")


    def_elements = soup.find_all("div", {"class": "entry-word-section-container"})
    def_list = [copy.deepcopy(element) for element in def_elements]

    for element in def_elements:
        element.decompose()

    full_def['inflections'] = extract_inflections(soup)

    if not def_list:
        def_response["status"] = False
        def_response["def"] = f'No definitions found.'
        if full_def["inflections"]:
            def_response["def"] += f' Variations found on the page: {", ".join(full_def["inflections"])}'
        return def_response

    for def_count, definition in enumerate(def_list, start=1):
        pos_tag = definition.find(class_="parts-of-speech")
        if pos_tag:
            full_def[def_count] = parse_standard_definition_block(definition, def_count)
        else:
            full_def[def_count] = non_standard_definitions(definition)
    if debug: return full_def
    alt_defs = {}
    for i, key in enumerate(full_def, start=1):
        if isinstance(full_def[key], dict) and full_def[key].get('alt_def'):
            alt_defs[f'alt_def_{i}'] = full_def[key]['alt_def']
            del full_def[key]['alt_def']

    full_def = check_duplicate_inflections(full_def)
    def_response["def"] = full_def
    for x, key in enumerate(alt_defs, start=1):
        def_response[f'alt_def_{x}'] = alt_defs[key]
    return def_response

def save_def(word):
    response = url_lookup(word)
    if isinstance(response, dict):  # error occurred
        return response

    soup = BeautifulSoup(response.text, "html.parser")
    path = f'./definitions/'
    file_name = f'{path}{word}0.txt'
    open(file_name, 'w').writelines(str(soup.prettify()))
    print(f'File saved: {file_name}')
    definition_list = soup.find_all("div", {"class": "entry-word-section-container"})

    if not definition_list:
        return {"status":False, "def": "No definitions found"}
    for x in range(0, len(definition_list)):
        file_name = f'{path}{word}{x+1}.txt'
        open(file_name, 'w').writelines(str(definition_list[x]()))
        print(f'File saved: {file_name}')

def dump(val):
    print(json.dumps(val, indent=2))


def test(word="spell"):
    response = def_lookup(word)
    print(json.dumps(response,indent=2))
    return response

def dtest(word="spell"):
    response = def_lookup(word, debug=True)
    print(json.dumps(response,indent=2))
    return response

'''
R = []
R.append(def_lookup("excellent"))
testWords = ["ass", "neet"]
def test():
    global R
    global testWords
    for val in R:
        R.remove(val)
    for word in testWords:
        R.append(def_lookup(word))
    for value in R:
        print(value)
'''


