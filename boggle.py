from bs4 import BeautifulSoup
# from definitionLookup import def_lookup # Assuming this is a custom module
import requests
import re
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
        # Iterate over each character in the word, converting to lowercase
        for char in word.lower():  # lowercase for consistency
            # If the character is not already a child of the current node, add it
            if char not in node.children:
                node.children[char] = TrieNode()
            # Move to the child node
            node = node.children[char]
        # Mark the end of a word
        node.is_end_of_word = True

    def _find_node(self, prefix):
        """Helper function to find the node corresponding to the end of a prefix."""
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return None
            node = node.children[char]
        return node

    def search(self, word):
        """Checks if a complete word exists in the trie."""
        node = self._find_node(word)
        return node is not None and node.is_end_of_word

    def starts_with(self, prefix):
        """Checks if any word in the trie starts with the given prefix."""
        return self._find_node(prefix) is not None

    def load_word_list(self, file_path, max_length=None):
        """Loads words from a JSON file into the trie."""
        file_path = os.path.expanduser(file_path) # Expands ~ to user's home directory
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Error: Word list file not found at {file_path}")
            return self # Return self to allow chaining even if file not found
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
            return self

        # Assuming data is a dictionary where values are lists of words
        for word_list_key in data:
            if isinstance(data[word_list_key], list):
                for word in data[word_list_key]:
                    if isinstance(word, str): # Ensure word is a string
                        if max_length is None or len(word) <= max_length:
                            self.insert(word)
                    else:
                        print(f"Warning: Non-string item '{word}' found in word list under key '{word_list_key}'. Skipping.")
            else:
                print(f"Warning: Value for key '{word_list_key}' is not a list. Skipping.")
        return self  # for chaining

    def count_words(self):
        """Counts the total number of words in the trie."""
        def dfs(node):
            count = 1 if node.is_end_of_word else 0
            for child in node.children.values():
                count += dfs(child)
            return count
        return dfs(self.root)

    def get_all_words_from_prefix(self, prefix): # Changed to be a method of Trie
        """Gets all words in the trie that start with the given prefix."""
        node = self._find_node(prefix)
        results = []

        def dfs(current_node, path):
            if current_node.is_end_of_word:
                results.append("".join(path))
            for char, child_node in current_node.children.items(): # Corrected variable name
                dfs(child_node, path + [char])

        if node:
            dfs(node, list(prefix.lower())) # Start DFS with the prefix itself
        return results


def dict_search(game_board, word_list_path = "/home/sonofwau/mysite/condensedWordList.json", word_to_find = None): # Renamed 'word' to 'word_to_find' for clarity
    found_words = {}
    # Initialize Trie: load all words if no specific word is given,
    # otherwise, insert only the specific word to search for.
    word_trie = Trie()
    if not word_to_find:
        word_trie.load_word_list(word_list_path, 36) # Max length 36 for Boggle-like game
    else:
        word_trie.insert(word_to_find)

    # Validate game board structure (must be 6x6 list of lists)
    if not game_board or not isinstance(game_board, list) or len(game_board) != 6:
        return {"Error": "Invalid board: Board must be a list of 6 rows."}

    for i, line in enumerate(game_board):
        if not isinstance(line, list) or len(line) != 6:
            return {"Error": f"Invalid board: Row {i} must be a list of 6 columns."}

    rows = 6
    cols = 6

    # Recursive function to find words starting from a given path
    def find_next_letter(current_combo, current_coord_list):
        # current_coord_list is a dictionary {0: {'x': x0, 'y': y0, 'letter': L0}, 1: {...}, ...}
        # Get the coordinates of the last letter added to the current combination
        last_index = max(current_coord_list.keys())
        last_x = current_coord_list[last_index]["x"]
        last_y = current_coord_list[last_index]["y"]

        # Define 8 possible directions to move from the current letter
        possible_directions = [
            (-1, 0), (-1, 1), (0, 1), (1, 1), # W, NW, N, NE
            (1, 0), (1, -1), (0, -1), (-1, -1)  # E, SE, S, SW
        ]

        for dx, dy in possible_directions:
            next_x, next_y = last_x + dx, last_y + dy

            # Check if the next coordinates are within the board boundaries
            if 0 <= next_x < cols and 0 <= next_y < rows:
                # Check if the next cell has already been used in the current path
                is_used = False
                for key in current_coord_list:
                    if current_coord_list[key]["x"] == next_x and current_coord_list[key]["y"] == next_y:
                        is_used = True
                        break
                if is_used:
                    continue

                next_letter_on_board = game_board[next_y][next_x]
                # Ensure the character on board is a single alphabetic character or a recognized multi-char string (e.g. "Qu")
                # For simplicity here, we'll stick to isalpha() for single chars.
                # If "Th" is treated as 'T' then 'h', board setup or trie insertion needs to handle it.
                # Current code treats game_board[y][x] as a single unit.
                if isinstance(next_letter_on_board, str) and next_letter_on_board.isalpha(): # Check if it's a letter
                    new_combo = current_combo + next_letter_on_board

                    # If the new combination is a prefix of any word in the trie
                    if word_trie.starts_with(new_combo):
                        new_coord_list = current_coord_list.copy()
                        new_coord_list[max(current_coord_list.keys()) + 1] = {
                            "x": next_x,
                            "y": next_y,
                            "letter": next_letter_on_board
                        }

                        # If the new combination is a complete word
                        if word_trie.search(new_combo):
                            # Store the found word (capitalized) and its coordinates
                            # Avoid overwriting if found via a different path (though less common with this coord_list structure)
                            if new_combo.title() not in found_words:
                                found_words[new_combo.title()] = new_coord_list

                        # Continue searching for longer words from this new combination
                        find_next_letter(new_combo, new_coord_list)
            # else: coordinates are out of bounds

    # Iterate over each cell in the game board to start a new word search
    for r in range(rows):  # Corrected: Iterate from 0 to 5 (inclusive for a 6-row board)
        for c in range(cols):  # Corrected: Iterate from 0 to 5 (inclusive for a 6-col board)
            start_letter = game_board[r][c]
            # Only start a search if the cell contains a valid single alphabetic character.
            # Modify this if your game has special tiles like "Qu" or "Th" treated as single units.
            if isinstance(start_letter, str) and start_letter.isalpha():
                initial_coords = {0: {"x": c, "y": r, "letter": start_letter}}

                # Check if the starting letter itself is a word
                if word_trie.search(start_letter):
                    if start_letter.title() not in found_words:
                         found_words[start_letter.title()] = initial_coords

                # Begin recursive search for words starting with this letter
                find_next_letter(start_letter, initial_coords)

            # If searching for a specific word and it's found, return immediately
            if word_to_find and word_to_find.title() in found_words:
                return {word_to_find.title(): found_words[word_to_find.title()]} # Return dict with the word

    # Return results based on whether a specific word was sought
    if word_to_find:
        if word_to_find.title() in found_words:
             return {word_to_find.title(): found_words[word_to_find.title()]}
        else:
            return {"status": False, "msg": f'{word_to_find.title()} not found on board'}
    else:
        return found_words


# --- Example Entry point ---
if __name__ == '__main__':
    board = [
        ["O", "N", "C", "B", "T", "S"],
        ["V", "I", "Y", "O", "U", "R"], # R is at board[1][5]
        ["A", "M", "A", "R", "K", "I"], # I is at board[2][5]
        ["G", "E", "T", "I", "N", "G"], # G is at board[3][5]
        ["Y", "Th", "-", "S", "E", "T"], # T is at board[4][5]
        ["B", "O", "G", "G", "L", "E"]  # B is at board[5][0], E is at board[5][5]
    ]
    # Ensure your JSON path is correct or provide a sample JSON structure for testing
    # For example, a condensedWordList.json might look like:
    # {
    #   "common": ["on", "in", "it", "is", "be", "as", "at", "so", "we", "he", "by", "or", "of", "to", "rig", "get", "bog", "boggle"],
    #   "other": ["try", "you", "mark"]
    # }
    # Create a dummy condensedWordList.json for testing if you don't have one
    dummy_word_list_path = "condensedWordList.json"
    if not os.path.exists(dummy_word_list_path):
        with open(dummy_word_list_path, 'w') as f:
            json.dump({
                "test_words": ["on", "or", "rig", "rin", "our", "run", "get", "gin", "got", "gob", "bog", "boggle", "set", "see", "ski", "king", "ring", "kit", "sir", "vie", "via", "ego", "got", "get", "leg", "log", "let", "big", "bit", "bet", "bot", "buy", "bun", "bus", "but", "try", "toy", "ton", "tour", "son", "soy", "sit", "sin", "sing", "sat", "set", "sub", "sum", "sun", "sue", "rub", "run", "rut", "rob", "rot", "roe", "rue"]
            }, f)
        print(f"Created dummy word list at {dummy_word_list_path}")
    else:
        print(f"Using existing word list at {dummy_word_list_path}")


    print("Searching for all words...")
    all_found = dict_search(board, word_list_path=dummy_word_list_path)
    if "Error" in all_found:
        print(f"Error: {all_found['Error']}")
    else:
        print(f"Found {len(all_found)} words:")
        for word, path in sorted(all_found.items()):
            print(f"- {word}: {path}")
    print("-" * 20)

    # Example: Search for a specific word "RIG"
    # Assuming 'R' at board[1][5], 'I' at board[2][5], 'G' at board[3][5]
    # This would require 'RIG' to be in your word list.
    print("Searching for 'RIG'...")
    specific_word_result = dict_search(board, word_list_path=dummy_word_list_path, word_to_find="RIG")
    print(specific_word_result)
    print("-" * 20)

    print("Searching for 'BOGGLE'...")
    specific_word_result_boggle = dict_search(board, word_list_path=dummy_word_list_path, word_to_find="BOGGLE")
    print(specific_word_result_boggle)
    print("-" * 20)

    print("Searching for 'SET'...") # Starts at board[4][5]
    specific_word_result_set = dict_search(board, word_list_path=dummy_word_list_path, word_to_find="SET")
    print(specific_word_result_set)
    print("-" * 20)

    # Clean up dummy file
    # if os.path.exists(dummy_word_list_path) and "test_words" in json.load(open(dummy_word_list_path)):
    #     os.remove(dummy_word_list_path)
    #     print(f"Removed dummy word list: {dummy_word_list_path}")