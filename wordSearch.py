import json
import os

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
        import os
        import json

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

def findWords(gameBoard, word_trie):
    foundWords = {"[clear]":""}
    if not gameBoard or type(gameBoard) != list or len(board) != 6:
        return {"Error":"Invalid board"}
    
    for line in gameBoard:
        if type(line) != list or len(line) != 6:
            return {"Error":"Bad secondary"}
        
    def findNextletter(combo, coordList):
        lastCoord = max(coordList.keys())
        possibleDirections = {
            'w': {
                "x": coordList[lastCoord]["x"]-1, 
                "y": coordList[lastCoord]["y"]
            },
            'nw': {
                "x": coordList[lastCoord]["x"]-1, 
                "y": coordList[lastCoord]["y"]+1
            },
            'n': {
                "x": coordList[lastCoord]["x"], 
                "y": coordList[lastCoord]["y"]+1
            },
            'ne': {
                "x": coordList[lastCoord]["x"]+1, 
                "y": coordList[lastCoord]["y"]+1
            },
            'e': {
                "x": coordList[lastCoord]["x"]+1, 
                "y": coordList[lastCoord]["y"]
            },
            'se': {
                "x": coordList[lastCoord]["x"]+1, 
                "y": coordList[lastCoord]["y"]-1
            },
            's': {
                "x": coordList[lastCoord]["x"], 
                "y": coordList[lastCoord]["y"]-1
            },
            'sw': {
                "x": coordList[lastCoord]["x"]-1, 
                "y": coordList[lastCoord]["y"]-1
            }
        }
        for direction in possibleDirections:
            x = possibleDirections[direction]["x"]
            y = possibleDirections[direction]["y"]
            if not 0 <= x <= 5 or not 0 <= y <= 5 :
                continue
            newCombo = combo + gameBoard[y][x]
            if word_trie.starts_with(newCombo):
                newCoordList = coordList.copy()
                newCoordList[max(coordList.keys())+1] = {"x": x, "y": y, "letter":gameBoard[y][x]}
                if word_trie.search(newCombo):
                    if newCombo not in foundWords:
                        foundWords[newCombo] = newCoordList
                findNextletter(newCombo, newCoordList)
    
    for y in range(0, 5):
        for x in range (0, 5):
            findNextletter(gameBoard[y][x], {0: {"x":x, "y":y, "letter":gameBoard[y][x]}})
    return foundWords

''' Code entry starts here '''
wordListPath = 'C:\\Users\\JoeBob\\Documents\\Powershell\\boggle\\htmlBoggle\\condensedWordList.json'
word_trie = Trie().load_word_list(wordListPath, 36)
board = [
            ["O", "N", "C", "B", "T", "S"],
            ["V", "I", "Y", "O", "U", "R"],
            ["A", "M", "A", "R", "K", "I"],
            ["G", "E", "T", "I", "N", "G"],
            ["Y", "Th", "-", "S", "E", "T"],
            ["B", "O", "G", "G", "L", "E"]
        ]

foundWords = findWords(board, word_trie)

#print(f'Found {len(foundWords)} words out of {word_trie.count_words()}')