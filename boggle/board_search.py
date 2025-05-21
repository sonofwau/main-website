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


def board_search(game_board, word_list_path = "/home/sonofwau/mysite/boggle/condensedWordList.json", word_to_find = None): # Default path
    # This function now uses its own default word_list_path if none is provided.
    # Flask app will call this without the word_list_path argument.

    found_words = {} # This will store the final words to be returned (if not word_to_find)
    word_trie = Trie()

    # Load the word list using the provided path or the default.
    # board_search is responsible for its own Trie instance and loading.
    word_trie.load_word_list(word_list_path, max_length=36)
    if word_trie.count_words() == 0:
        # If no words are loaded (e.g., file not found, empty, or bad format),
        # it's problematic for searching.
        print(f"Warning from board_search: Trie loaded 0 words from {word_list_path}. Search might not find anything.")
        # Depending on desired behavior, you could return an error here.
        # For now, it will proceed, likely finding no words.

    # Validate game board structure (must be 6x6 list of lists)
    if not game_board or not isinstance(game_board, list) or len(game_board) != 6:
        return {"Error": "Invalid board: Board must be a list of 6 rows."}

    for i, line in enumerate(game_board):
        if not isinstance(line, list) or len(line) != 6:
            return {"Error": f"Invalid board: Row {i} must be a list of 6 columns."}

    rows = 6
    cols = 6

    # Internal dictionary to store paths for found words during the search
    _internal_found_paths = {}

    # Recursive function to find words starting from a given path
    def find_next_letter(current_combo_display, current_coord_list):
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
                for key_idx in current_coord_list: # Iterate through the dictionary keys
                    if current_coord_list[key_idx]["x"] == next_x and current_coord_list[key_idx]["y"] == next_y:
                        is_used = True
                        break
                if is_used:
                    continue

                next_letter_on_board = game_board[next_y][next_x]
                # Allow single alphabetic char or multi-char strings (like "Qu", "Th")
                if isinstance(next_letter_on_board, str) and (next_letter_on_board.isalpha() or len(next_letter_on_board) > 1):

                    # Build combo for Trie search in lowercase
                    # current_combo_display is passed with original casing, convert to lower for trie operations
                    current_combo_lower = current_combo_display.lower()
                    next_letter_lower = next_letter_on_board.lower()
                    new_combo_for_trie = current_combo_lower + next_letter_lower

                    # Build combo for display/key (maintains original casing from board)
                    new_combo_for_display = current_combo_display + next_letter_on_board

                    if word_trie.starts_with(new_combo_for_trie):
                        new_coord_list = current_coord_list.copy()
                        new_coord_list[max(current_coord_list.keys()) + 1] = {
                            "x": next_x,
                            "y": next_y,
                            "letter": next_letter_on_board # Store original case from board
                        }
                        if word_trie.search(new_combo_for_trie):
                            # Store with the display case (Title Case), path is universal
                            word_key_display_title = new_combo_for_display.title()
                            if word_key_display_title not in _internal_found_paths:
                                _internal_found_paths[word_key_display_title] = new_coord_list

                        # Continue searching for longer words from this new combination
                        # Pass the display combo for recursion
                        find_next_letter(new_combo_for_display, new_coord_list)

    # Iterate over each cell in the game board to start a new word search
    for r in range(rows):
        for c in range(cols):
            start_letter_on_board = game_board[r][c]
            # Allow single alphabetic char or multi-char strings
            if isinstance(start_letter_on_board, str) and (start_letter_on_board.isalpha() or len(start_letter_on_board) > 1):
                initial_coords = {0: {"x": c, "y": r, "letter": start_letter_on_board}}
                start_letter_for_trie = start_letter_on_board.lower() # For trie search

                if word_trie.search(start_letter_for_trie):
                    word_key_display_title = start_letter_on_board.title()
                    if word_key_display_title not in _internal_found_paths:
                         _internal_found_paths[word_key_display_title] = initial_coords

                # Begin recursive search for words starting with this letter
                # Pass the original case from board for current_combo_display
                find_next_letter(start_letter_on_board, initial_coords)

    # Return results based on whether a specific word was sought
    if word_to_find:
        word_to_find_title = word_to_find.title() # Search for the title-cased version
        if word_to_find_title in _internal_found_paths:
            return {"status": True, word_to_find_title: _internal_found_paths[word_to_find_title]}
        else:
            return {"status": False, "msg": f'{word_to_find.title()} not found on board or is not a valid word.'}
    else:
        # Return all found words (paths are stored in _internal_found_paths)
        return _internal_found_paths


# --- Example Entry point ---
if __name__ == '__main__':
    board_example = [
        ["O", "N", "C", "B", "T", "S"], ["V", "I", "Y", "O", "U", "R"], ["A", "M", "A", "R", "K", "I"],
        ["G", "E", "T", "I", "N", "G"], ["Y", "Th", "-", "S", "E", "T"], ["B", "O", "G", "G", "L", "E"]
    ]
    # This example will use the default path in board_search function definition
    # Ensure your JSON path is correct or provide a sample JSON structure for testing
    # For example, a condensedWordList.json might look like:
    # {
    #   "common": ["on", "in", "it", "is", "be", "as", "at", "so", "we", "he", "by", "or", "of", "to", "rig", "get", "bog", "boggle"],
    #   "other": ["try", "you", "mark", "neet"]
    # }
    # Create a dummy condensedWordList.json for testing if you don't have one
    # The default path in board_search is absolute, so this local dummy might not be used unless you change the default.
    # For local testing of this __main__ block, you might temporarily change the default path in board_search
    # or ensure the absolute path /home/sonofwau/mysite/boggle/condensedWordList.json exists and is correct.

    # Assuming the default path in board_search is used:
    print("Searching for all words (using default path in board_search function)...")
    all_found = board_search(board_example) # No word_list_path, uses default
    if "Error" in all_found:
        print(f"Error: {all_found['Error']}")
    else:
        print(f"Found {len(all_found)} words:")
        for word, path_val in sorted(all_found.items()):
            print(f"- {word}: {path_val}")
    print("-" * 20)

    print("Searching for 'NEET' (using default path in board_search function)...")
    specific_word_result = board_search(board_example, word_to_find="NEET")
    print(json.dumps(specific_word_result, indent=2))
    print("-" * 20)

    print("Searching for 'BOGGLE' (using default path in board_search function)...")
    specific_word_result_boggle = board_search(board_example, word_to_find="BOGGLE")
    print(json.dumps(specific_word_result_boggle, indent=2))
    print("-" * 20)

    print("Searching for 'XYZ' (not on board, using default path)...")
    specific_word_result_xyz = board_search(board_example, word_to_find="XYZ")
    print(json.dumps(specific_word_result_xyz, indent=2))
    print("-" * 20)
