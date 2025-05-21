import requests
import re
import json
from bs4 import BeautifulSoup


def getDefinitionFor(word):
    return defLookup(word)


def set_nested_dict(root, keys, value):
    """Safely set a nested dictionary value without using exec()."""
    d = root
    for key in keys[:-1]:
        if key not in d or not isinstance(d[key], dict):
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


def urlLookup(word):
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
        return ("❌ Error fetching page:", e)


def nonStandardDefinitions(entry_section):
    # Placeholder for now
    # This next section is for words with the cxl-ref class
    cxl_refCheck = entry_section.find(class_="cxl-ref")
    if cxl_refCheck:
        return re.sub(r'\n', " ", cxl_refCheck.text).lstrip().rstrip()
    return "Unable to parse definition"


def parseStandardDefinitionBlock(definition, defCount):
    fullDef = {}

    # Extract POS
    pos_tag = definition.find(class_="parts-of-speech")
    fullDef["POS"] = re.sub(r' \([0-9]\)', "", pos_tag.text) if pos_tag else "unknown"

    # Inflections
    inflectionResults = definition.find_all(class_="if")
    if inflectionResults:
        fullDef["inflections"] = [inf.text for inf in inflectionResults]

    # Definitions
    defItems = definition.find_all(class_="vg")
    for defItem in defItems:
        subPOS = defItem.find(class_="vd")
        if subPOS:
            basePath = ["subPOS", subPOS.text]
            fullDef.setdefault("subPOS", {})
        else:
            basePath = ["definitions"]
            fullDef.setdefault("definitions", {})

        entries = defItem.find_all(class_="vg-sseq-entry-item")
        for entry in entries:
            entryLabel = entry.find(class_="vg-sseq-entry-item-label")
            if entryLabel:
                entryPath = basePath + [entryLabel.text]
            else:
                entryPath = basePath

            set_nested_dict(fullDef, entryPath, {})

            nextSetList = re.findall(r'sb-[0-9] sb-entry', str(entry))
            for item in nextSetList:
                newItem = entry.find(class_=item)
                if not newItem:
                    continue

                subLetter = newItem.find(class_="letter")
                if subLetter:
                    subPath = entryPath + [subLetter.text]
                    set_nested_dict(fullDef, subPath, {})
                else:
                    subPath = entryPath

                senses = newItem.find_all(class_="sense")
                for sense in senses:
                    subNum = sense.find(class_="sub-num")
                    if subNum:
                        finalPath = subPath + [subNum.text]
                        set_nested_dict(fullDef, finalPath, {})
                    else:
                        finalPath = subPath

                    dtText = sense.find(class_="dtText")
                    if dtText and dtText.text:
                        set_nested_dict(fullDef, finalPath + ["def"], dtText.text.lstrip(": "))

                    example = sense.find(class_="sub-content-thread")
                    if example and example.text:
                        set_nested_dict(fullDef, finalPath + ["ex"], example.text)

    return fullDef


def defLookup(word):
    response = urlLookup(word)
    if isinstance(response, tuple):  # error occurred
        return {"error": str(response)}

    soup = BeautifulSoup(response.text, "html.parser")
    definitionList = soup.find_all("div", {"class": "entry-word-section-container"})

    if not definitionList:
        return {"error": "No definitions found"}

    fullDef = {}
    defCount = 0

    for definition in definitionList:
        defCount += 1
        pos_tag = definition.find(class_="parts-of-speech")
        if pos_tag:
            fullDef[defCount] = parseStandardDefinitionBlock(definition, defCount)
        else:
            fullDef[defCount] = nonStandardDefinitions(definition)

    return fullDef


# --- Entry point ---

dictList = {}
wordList = ["asdf", "neet", "excellent", "spell"]
