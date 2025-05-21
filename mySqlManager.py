from bs4 import BeautifulSoup
import mysql.connector
import requests
import re
import json
import os
import re

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for char in word.lower():  # lowercase for consistency
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def _find_node(self, prefix):
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def search(self, word):
        node = self._find_node(word)
        return node is not None and node.is_end_of_word

    def starts_with(self, prefix):
        return self._find_node(prefix) is not None

    def load_word_list(self, file_path, max_length=None):
        file_path = os.path.expanduser(file_path)
        with open(file_path, 'r') as f:
            data = json.load(f)

        for word_list in data.values():
            for word in word_list:
                if max_length is None or len(word) <= max_length:
                    self.insert(word)

        return self  # for chaining

    def count_words(self):
        def dfs(node):
            count = 1 if node.is_end_of_word else 0
            for child in node.children.values():
                count += dfs(child)
            return count
        return dfs(self.root)

    def get_all_words_from_prefix(trie, prefix):
        node = trie._find_node(prefix)
        results = []

        def dfs(current_node, path):
            if current_node.is_end_of_word:
                results.append("".join(path))
            for char, child in current_node.children.items():
                dfs(child, path + [char])

        if node:
            dfs(node, list(prefix))
        return results


def wordSearch(board):
    return wordList


def getDefinitionFor(word):
    return defLookup(word)


def set_nested_dict2(root, keys, value):
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


def set_nested_dict(d, path, value):
    """Sets a nested dictionary based on the path."""
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def extract_pos(definition):
    pos_tag = definition.find(class_="parts-of-speech")
    return re.sub(r' \([0-9]\)', "", pos_tag.text) if pos_tag else "unknown"


def extract_inflections(definition):
    inflection_results = definition.find_all(class_="if")
    return [inf.text for inf in inflection_results] if inflection_results else []


def parse_standard_definition_block(definition, def_count):
    full_def = {
        "word": definition.find(class_="hword").text,
        "POS": extract_pos(definition)
    }

    inflections = extract_inflections(definition)
    if inflections:
        full_def["inflections"] = inflections

    def_items = definition.find_all(class_="vg")
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
                    entry_data = {}
                    dt_text = sense.find(class_="dtText")
                    if dt_text and dt_text.text:
                        entry_data["def"] = dt_text.text.lstrip(": ")
                    example = sense.find(class_="sub-content-thread")
                    if example and example.text:
                        entry_data["ex"] = example.text
                    if entry_data:
                        current_block[def_index] = entry_data
                        def_index += 1

        if sub_pos_tag:
            label = sub_pos_tag.text
            subpos_blocks.setdefault(label, {"definitions": {}})["definitions"].update(current_block)
        else:
            definitions.update(current_block)

    if subpos_blocks:
        full_def["subPOS"] = subpos_blocks
    if definitions:
        full_def["definitions"] = definitions

    return full_def


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
            fullDef[defCount] = parse_standard_definition_block(definition, defCount)
        else:
            fullDef[defCount] = nonStandardDefinitions(definition)
    return fullDef


def mySqlConnector(mydb = False, mycursor = False, close = False):
    if close:
        mycursor.close()
        mydb.close()
        return
    mydb = mysql.connector.connect(
        host="sonofwau.mysql.pythonanywhere-services.com",
        user="sonofwau",
        password="BiteMyShinyMetalAss",
        database="sonofwau$default"
    )
    mycursor = mydb.cursor()
    return mydb, mycursor

def getWordList():
    mydb, mycursor = mySqlConnector()

    mycursor.execute("SELECT priWord, variations, checked from word_list")

    rows = mycursor.fetchall()
    data = []
    for row in rows:
        wordInfo = {
            'word': row[0],
            'variations': row[1],
            'checked': row[2]
        }
        data.append(wordInfo)

    mySqlConnector(mydb, mycursor, close=True)
    return data

def findDefinitions(wordList):
    #mydb, mycursor = mySqlConnector()
    #posList = ["noun", "pronoun", "verb", "adjective", "adverb", "preposition", "conjunction", "interjection"]
    newWordList = {}
    count = 0
    for word in wordList:
        if count > 50:
            break
        else:
            count += 1
        print(f'{count} - {word}')
        wordDef = defLookup(word)
        for definition in wordDef:
            if not definition["POS"]:
                continue
            pos_tokens = re.findall(r'\b(noun|pronoun|verb|adjective|adverb|preposition|conjunction|interjection)\b', definition["POS"].lower())
            if pos_tokens:
                if not newWordList[word]:
                    newWordList[word] = [word]
                if definition['inflections']:
                    for variation in definition['inflections']:
                        if not variation in newWordList[word]:
                            newWordList.append[variation]

    return newWordList

def test():
    wordList = getWordList()
    badWords = []
    goodWords = []
    i = 0
    while i < len(wordList):
        word = wordList[i]["word"]
        charTest = re.search(r'[^a-zA-Z]', word)
        if i < 5:
            print ('word:', word)
            print('charTest:', charTest)
        if charTest:
            badWords.append(wordList[i])
        else:
            goodWords.append(wordList[i])
        i += 1
    len(badWords)
    len(goodWords)
    wordList = getWordList()
    newList = findDefinitions(wordList)
    return newList

# --- Entry point ---
wordListPath = "/home/sonofwau/mysite/condensedWordList.json"
wordList = {}

