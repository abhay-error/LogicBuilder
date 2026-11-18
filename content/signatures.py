"""Language-neutral function signatures for every practice problem.

Starter code and test drivers for Java/C++/Go/C#/JS/TS are generated from these (app/langs.py),
so adding a problem needs ONE line here instead of seven hand-written harnesses.
Types: int, long, str, bool, list[int], list[str].
"""

SIGS = {
    "even-or-odd": ([("n", "int")], "str"),
    "max-of-three": ([("a", "int"), ("b", "int"), ("c", "int")], "int"),
    "sum-to-n": ([("n", "int")], "int"),
    "factorial": ([("n", "int")], "long"),
    "reverse-string": ([("s", "str")], "str"),
    "palindrome": ([("s", "str")], "bool"),
    "fizzbuzz": ([("n", "int")], "list[str]"),
    "two-sum": ([("nums", "list[int]"), ("target", "int")], "list[int]"),
    "binary-search": ([("nums", "list[int]"), ("target", "int")], "int"),
    "valid-parentheses": ([("s", "str")], "bool"),
    "is-prime": ([("n", "int")], "bool"),
    "fibonacci": ([("n", "int")], "int"),
    "count-vowels": ([("s", "str")], "int"),
    "remove-duplicates": ([("items", "list[int]")], "list[int]"),
    "anagram": ([("a", "str"), ("b", "str")], "bool"),
    "sort-list": ([("nums", "list[int]")], "list[int]"),
    "merge-sorted": ([("a", "list[int]"), ("b", "list[int]")], "list[int]"),
    "missing-number": ([("nums", "list[int]")], "int"),
    "max-subarray": ([("nums", "list[int]")], "int"),
}
