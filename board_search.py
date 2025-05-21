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
        for char in word.lower(): # lowercase for consistency
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
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Error: Word list file not found at {file_path}")
            return self
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
            return self

        for word_list_key in data:
            if isinstance(data[word_list_key], list):
                for word in data[word_list_key]:
                    if isinstance(word, str):
                        if max_length is None or len(word) <= max_length:
                            self.insert(word)
                    else:
                        print(f"Warning: Non-string item '{word}' found in word list under key '{word_list_key}'. Skipping.")
            else:
                print(f"Warning: Value for key '{word_list_key}' is not a list. Skipping.")
        return self

    def count_words(self):
        def dfs(node):
            count = 1 if node.is_end_of_word else 0
            for child in node.children.values():
                count += dfs(child)
            return count
        return dfs(self.root)

    def get_all_words_from_prefix(self, prefix):
        node = self._find_node(prefix)
        results = []
        def dfs(current_node, path):
            if current_node.is_end_of_word:
                results.append("".join(path))
            for char, child_node in current_node.children.items():
                dfs(child_node, path + [char])
        if node:
            dfs(node, list(prefix.lower()))
        return results


def board_search(game_board, word_list_path = "/home/sonofwau/mysite/condensedWordList.json", word_to_find = None):
    found_words = {}
    word_trie = Trie()
    if not word_to_find:
        word_trie.load_word_list(word_list_path, 36)
    else:
        # When searching for a specific word, we still need the trie to validate it.
        # However, the original logic only inserted the specific word.
        # For consistency, it's better if board_search always assumes the word list is for validation.
        # The flask app should manage one global trie.
        # For now, to match the user's current structure where board_search loads its own trie:
        word_trie.load_word_list(word_list_path, 36) # Load all words to check against
        # Then, we just check if word_to_find is in this loaded trie and on the board.


    if not game_board or not isinstance(game_board, list) or len(game_board) != 6:
        return {"Error": "Invalid board: Board must be a list of 6 rows."}
    for i, line in enumerate(game_board):
        if not isinstance(line, list) or len(line) != 6:
            return {"Error": f"Invalid board: Row {i} must be a list of 6 columns."}

    rows = 6
    cols = 6

    # Internal dictionary to store paths for found words during the search
    _internal_found_paths = {}

    def find_next_letter(current_combo, current_coord_list):
        last_index = max(current_coord_list.keys())
        last_x = current_coord_list[last_index]["x"]
        last_y = current_coord_list[last_index]["y"]
        possible_directions = [
            (-1, 0), (-1, 1), (0, 1), (1, 1),
            (1, 0), (1, -1), (0, -1), (-1, -1)
        ]
        for dx, dy in possible_directions:
            next_x, next_y = last_x + dx, last_y + dy
            if 0 <= next_x < cols and 0 <= next_y < rows:
                is_used = False
                for key_idx in current_coord_list: # Check by key_idx to iterate through dict
                    if current_coord_list[key_idx]["x"] == next_x and current_coord_list[key_idx]["y"] == next_y:
                        is_used = True
                        break
                if is_used:
                    continue

                next_letter_on_board = game_board[next_y][next_x]
                if isinstance(next_letter_on_board, str) and next_letter_on_board.isalpha() or len(next_letter_on_board) > 1 : # Allow multi-char strings like "Qu", "Th"
                    # For multi-char strings, they should be treated as a single unit in the trie as well.
                    # E.g., "Qu" on board matches "Qu" in trie path.
                    # The trie's insert method uses .lower(), so "Qu".lower() is "qu".
                    # current_combo also needs to be built with lowercase for starts_with and search.

                    # Build combo for Trie search in lowercase
                    current_combo_lower = current_combo.lower()
                    next_letter_lower = next_letter_on_board.lower()
                    new_combo_lower = current_combo_lower + next_letter_lower

                    # Build combo for display/key in uppercase/titlecase later
                    new_combo_display = current_combo + next_letter_on_board


                    if word_trie.starts_with(new_combo_lower):
                        new_coord_list = current_coord_list.copy()
                        new_coord_list[max(current_coord_list.keys()) + 1] = {
                            "x": next_x, "y": next_y, "letter": next_letter_on_board
                        }
                        if word_trie.search(new_combo_lower):
                            # Store with the display case, path is universal
                            word_key_display = new_combo_display.title()
                            if word_key_display not in _internal_found_paths:
                                _internal_found_paths[word_key_display] = new_coord_list
                        find_next_letter(new_combo_display, new_coord_list) # Recursive call with display combo

    for r in range(rows):
        for c in range(cols):
            start_letter = game_board[r][c]
            if isinstance(start_letter, str) and start_letter.isalpha() or len(start_letter) > 1:
                initial_coords = {0: {"x": c, "y": r, "letter": start_letter}}
                start_letter_lower = start_letter.lower() # For trie search

                if word_trie.search(start_letter_lower):
                    word_key_display = start_letter.title()
                    if word_key_display not in _internal_found_paths:
                        _internal_found_paths[word_key_display] = initial_coords

                # Start recursive search with display case for current_combo
                find_next_letter(start_letter, initial_coords)

    if word_to_find:
        # Check if the specific word (title cased) is in our found paths
        word_to_find_title = word_to_find.title()
        if word_to_find_title in _internal_found_paths:
            # ****MODIFICATION HERE****
            return {"status": True, word_to_find_title: _internal_found_paths[word_to_find_title]}
        else:
            return {"status": False, "msg": f'{word_to_find.title()} not found on board or is not a valid word.'}
    else:
        # Return all found words (paths)
        return _internal_found_paths


# --- Example Entry point ---
if __name__ == '__main__':
    board_example = [
        ["O", "N", "C", "B", "T", "S"], ["V", "I", "Y", "O", "U", "R"], ["A", "M", "A", "R", "K", "I"],
        ["G", "E", "T", "I", "N", "G"], ["Y", "Th", "-", "S", "E", "T"], ["B", "O", "G", "G", "L", "E"]
    ]
    dummy_word_list_path = "condensedWordList.json" # Ensure this exists or provide path
    if not os.path.exists(dummy_word_list_path):
        with open(dummy_word_list_path, 'w') as f:
            json.dump({
                "test_words": ["on", "or", "rig", "rin", "our", "run", "get", "gin", "got", "gob", "bog", "boggle", "set", "see", "ski", "king", "ring", "kit", "sir", "vie", "via", "ego", "got", "get", "leg", "log", "let", "big", "bit", "bet", "bot", "buy", "bun", "bus", "but", "try", "toy", "ton", "tour", "son", "soy", "sit", "sin", "sing", "sat", "set", "sub", "sum", "sun", "sue", "rub", "run", "rut", "rob", "rot", "roe", "rue", "neet", "bogs"]
            }, f)
        print(f"Created dummy word list at {dummy_word_list_path}")

    print("Searching for all words...")
    all_found = board_search(board_example, word_list_path=dummy_word_list_path)
    if "Error" in all_found:
        print(f"Error: {all_found['Error']}")
    else:
        print(f"Found {len(all_found)} words:")
        for word, path_val in sorted(all_found.items()):
            print(f"- {word}: {path_val}")
    print("-" * 20)

    print("Searching for 'NEET'...")
    specific_word_result = board_search(board_example, word_list_path=dummy_word_list_path, word_to_find="NEET")
    print(json.dumps(specific_word_result, indent=2))
    print("-" * 20)

    print("Searching for 'BOGGLE'...")
    specific_word_result_boggle = board_search(board_example, word_list_path=dummy_word_list_path, word_to_find="BOGGLE")
    print(json.dumps(specific_word_result_boggle, indent=2))
    print("-" * 20)

    print("Searching for 'XYZ' (not on board)...")
    specific_word_result_xyz = board_search(board_example, word_list_path=dummy_word_list_path, word_to_find="XYZ")
    print(json.dumps(specific_word_result_xyz, indent=2))
    print("-" * 20)
