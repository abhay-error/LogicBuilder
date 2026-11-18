"""Lessons as data (content engine, HLD §6).

Block types
  text         markdown-lite
  code         runnable/visualizable example   (visualize: True)
  quiz         multiple choice                  (options, answer=index)
  predict      "what does this print?"          (code; expected output is computed by really running it)
  fill         fill in blanks                   (code with {{key}}, blanks {key: [accepted answers]})
  parsons      put the lines in order           (lines = correct order, indentation included)
  trace_table  fill a variable table            (code, line, vars; rows computed by the tracer)
  bug          click the buggy line             (code, bug_line)
Answers live only on the server (app/exercises.py strips them before sending to the browser).
Lessons with premium=True are gated only when LB_PAYWALL=1 (business mode).
"""

LESSONS = [
    # ---------------------------------------------------------------- LEVEL 0
    {
        "id": "think-like-a-computer", "level": 0, "title": "Thinking like a computer", "minutes": 8,
        "concepts": ["algorithm", "sequence"],
        "blocks": [
            {"type": "text", "md": """## A computer is a very fast, very literal helper
It does exactly what you say, in order, with no guessing. So *logic building* means: **break a goal into tiny, exact steps.**

Think of a recipe for tea:

1. Boil water
2. Put a tea bag in a cup
3. Pour the water
4. Wait 3 minutes
5. Remove the tea bag

That list of steps is an **algorithm**. Code is an algorithm written in a language the computer understands.

### Three building blocks of every program
- **Sequence**: do things one after another
- **Decision**: *if* something is true do A, otherwise do B
- **Repetition**: do something again and again until a goal is met"""},
            {"type": "text", "md": "Press **Visualize**, then **Next**. The yellow line is the one about to run. Watch the *Output* box fill up."},
            {"type": "code", "visualize": True, "code": 'print("Boil water")\nprint("Add tea bag")\nprint("Pour water")\nprint("Wait 3 minutes")\nprint("Done!")'},
            {"type": "parsons", "prompt": "The steps got shuffled! Put the tea program back in a sensible order (drag, or use the arrows).",
             "lines": ['print("Boil water")', 'print("Add tea bag")', 'print("Pour water")', 'print("Wait 3 minutes")', 'print("Done!")'],
             "explain": "Order matters. A computer cannot pour water that has not been boiled yet."},
            {"type": "quiz", "prompt": "Which building block is 'if the cup is empty, pour water'?",
             "options": ["Sequence", "Decision", "Repetition"], "answer": 1,
             "explain": "It chooses between doing something or not based on a condition, which is a decision."},
        ],
    },
    {
        "id": "break-it-down", "level": 0, "title": "Break big problems into small steps", "minutes": 10,
        "concepts": ["decomposition", "sequence"],
        "blocks": [
            {"type": "text", "md": """## The skill behind all coding: decomposition
Nobody solves a big problem in one move. Programmers **shrink it** until every piece is trivial.

Problem: *"Find the average of three test scores."*

Shrunk down:
1. Remember the three scores
2. Add them up
3. Divide by 3
4. Show the answer

The code is then just a translation of those steps. **The thinking is the hard part, typing is the easy part.**

### The method we'll use for every problem
**U**nderstand → **E**xamples → **P**lan → **C**ode → **T**est → **I**mprove

Before writing code: say the problem in your own words, work a tiny example by hand, and write your steps in plain English. You'll see a *Plan* box in every practice problem for exactly this."""},
            {"type": "parsons", "prompt": "Arrange the steps of the average program. (More than one order can be correct. Does it run?)",
             "lines": ["a = 4", "b = 8", "c = 6", "total = a + b + c", "average = total / 3", "print(average)"],
             "explain": "The three starting values can be in any order, but the sum must come after them, and the print must come last."},
            {"type": "predict", "prompt": "What does this program print? Work it out by hand first.",
             "code": "price = 120\nquantity = 3\ndiscount = 20\ntotal = price * quantity - discount\nprint(total)",
             "explain": "120 × 3 = 360, minus 20 = 340. Multiplication happens before subtraction."},
            {"type": "quiz", "prompt": "You get a big, scary problem. What's the best first move?",
             "options": ["Start typing code and see what happens", "Work a small example by hand and write the steps in plain words", "Search for the full solution"],
             "answer": 1, "explain": "A plan in plain words turns a scary problem into small steps you already know how to do."},
        ],
    },
    # ---------------------------------------------------------------- LEVEL 1
    {
        "id": "variables", "level": 1, "title": "Variables: boxes with names", "minutes": 10,
        "concepts": ["variables", "assignment"],
        "blocks": [
            {"type": "text", "md": """## Variables remember things
A **variable** is a labelled box. You put a value in, and later you can read it or replace it.

```
age = 20
```
means: *make a box called `age` and put 20 in it.* The `=` here is **not** math equality. It means **store**.

Step through and watch the *Call stack* panel: values appear as each line runs, and changed values flash."""},
            {"type": "code", "visualize": True, "code": "apples = 5\noranges = 3\ntotal = apples + oranges\napples = apples - 2\nprint(total, apples)"},
            {"type": "text", "md": """Notice `total` stayed **8** even after `apples` changed. `total` copied the *result* at that moment, it did not stay linked.

### Common types
- `int` whole numbers: `7`
- `float` decimals: `3.14`
- `str` text: `"hello"`
- `bool` `True` or `False`"""},
            {"type": "fill", "prompt": "Store the number 7 in a variable named `lucky`.", "code": "lucky = {{a}}\nprint(lucky + 1)",
             "blanks": {"a": ["7"]}, "explain": "Now lucky holds 7, so lucky + 1 prints 8."},
            {"type": "predict", "prompt": "Careful, this one is a classic trap. What is printed?",
             "code": "x = 10\ny = x\nx = 99\nprint(y)",
             "explain": "`y = x` copies the value 10 at that moment. Changing x later does not change y."},
            {"type": "quiz", "prompt": "After `x = 4` then `x = x + 1`, what is x?",
             "options": ["4", "5", "x + 1"], "answer": 1,
             "explain": "Python computes the right side first (4 + 1 = 5), then stores 5 back into x."},
        ],
    },
    {
        "id": "conditions", "level": 1, "title": "Decisions with if / else", "minutes": 12,
        "concepts": ["conditions", "comparison", "boolean-logic"],
        "blocks": [
            {"type": "text", "md": """## Programs can choose
An `if` checks a **condition** that is either `True` or `False`.

```
if temperature > 30:
    print("hot")
else:
    print("fine")
```

Indentation (the 4 spaces) tells Python *which lines belong to the if*.

Compare with `==` (equal), `!=`, `<`, `>`, `<=`, `>=`. Combine with `and`, `or`, `not`.

Watch which lines are **skipped**: the highlight jumps over the branch that does not run."""},
            {"type": "code", "visualize": True, "code": 'score = 72\nif score >= 90:\n    grade = "A"\nelif score >= 70:\n    grade = "B"\nelse:\n    grade = "C"\nprint(grade)'},
            {"type": "quiz", "prompt": "What does the program above print?", "options": ["A", "B", "C"], "answer": 1,
             "explain": "72 is not >= 90, but it is >= 70, so grade becomes B and the else is skipped."},
            {"type": "predict", "prompt": "Combine conditions. What is printed?",
             "code": 'temp = 25\nraining = True\nif temp > 20 and not raining:\n    print("park")\nelif temp > 20:\n    print("cafe")\nelse:\n    print("home")',
             "explain": "temp > 20 is True but `not raining` is False, so the first `and` fails. The elif checks only temp > 20, which is True: cafe."},
            {"type": "bug", "prompt": "This program should print `even` for even numbers. It prints the wrong thing. Click the buggy line.",
             "code": 'n = 10\nif n % 2 == 1:\n    print("even")\nelse:\n    print("odd")',
             "bug_line": 2, "explain": "`n % 2 == 1` is true for ODD numbers. The check should be `n % 2 == 0`. Finding bugs is a core coding skill: run it in your head with a real value."},
        ],
    },
    # ---------------------------------------------------------------- LEVEL 2
    {
        "id": "loops", "level": 2, "title": "Loops: repeat without copy-paste", "minutes": 14,
        "concepts": ["loops", "accumulator"],
        "blocks": [
            {"type": "text", "md": """## Do it again, smartly
Adding 1+2+3+4+5 by hand is easy. Adding up to 1000 is not. A **loop** repeats steps for you.

A very common loop pattern is the **accumulator**: start with a box (`total = 0`), and in every round add something to it.

`range(1, 6)` gives the numbers 1, 2, 3, 4, 5 (the end is *not* included).

Step through and watch `i` and `total` change together every round."""},
            {"type": "code", "visualize": True, "code": "total = 0\nfor i in range(1, 6):\n    total = total + i\nprint(total)"},
            {"type": "trace_table", "prompt": "Be the computer. Each time line 3 is about to run, what are `i` and `total`? Fill the table.",
             "code": "total = 0\nfor i in range(1, 5):\n    total = total + i\nprint(total)", "line": 3, "vars": ["i", "total"],
             "explain": "Each round adds the new i to total: 0, then 1, then 3, then 6. Tracing by hand like this is how you debug."},
            {"type": "fill", "prompt": "Print the numbers 0, 1, 2, 3, 4 (five numbers).", "code": "for i in {{a}}:\n    print(i)",
             "blanks": {"a": ["range(5)", "range(0,5)"]}, "explain": "range(5) starts at 0 and stops before 5."},
            {"type": "text", "md": """### `while` loops
Use `while` when you do not know how many rounds you need. Beware: if the condition never becomes false, the loop never ends (an **infinite loop**)."""},
            {"type": "code", "visualize": True, "code": "n = 37\nsteps = 0\nwhile n > 1:\n    if n % 2 == 0:\n        n = n // 2\n    else:\n        n = 3 * n + 1\n    steps += 1\nprint(steps)"},
            {"type": "quiz", "prompt": "How many times does the body of `for i in range(3)` run?", "options": ["2", "3", "4"], "answer": 1,
             "explain": "i takes the values 0, 1, 2, which is 3 rounds."},
        ],
    },
    {
        "id": "nested-loops", "level": 2, "title": "Loops inside loops: patterns", "minutes": 12,
        "concepts": ["loops", "nested-loops", "patterns"],
        "blocks": [
            {"type": "text", "md": """## A loop can contain a loop
Think of a clock: the minute hand does a full circle for **every single step** of the hour hand. The *inner* loop completes fully for each round of the *outer* loop.

This builds a triangle. Watch `row` and `col` and the output grow:"""},
            {"type": "code", "visualize": True, "code": 'for row in range(1, 4):\n    line = ""\n    for col in range(row):\n        line = line + "*"\n    print(line)'},
            {"type": "predict", "prompt": "What does this print? (Type each printed line on its own line.)",
             "code": 'for a in range(1, 4):\n    line = ""\n    for b in range(a):\n        line = line + str(a)\n    print(line)',
             "explain": "Row a repeats the digit a, a times: 1, then 22, then 333."},
            {"type": "quiz", "prompt": "An outer loop runs 3 times and an inner loop runs 4 times per round. How many times does the inner body run in total?",
             "options": ["7", "12", "4"], "answer": 1, "explain": "3 × 4 = 12. Nested loops multiply. (This is why nested loops get slow: remember this for Big-O later!)"},
        ],
    },
    # ---------------------------------------------------------------- LEVEL 3
    {
        "id": "functions", "level": 3, "title": "Functions and the call stack", "minutes": 16,
        "concepts": ["functions", "call-stack", "recursion"],
        "blocks": [
            {"type": "text", "md": """## Name a recipe, reuse it
A **function** packages steps under a name. It can take **inputs** (parameters) and give back an **output** (`return`).

When a function is called, Python makes a fresh *frame* (a private set of variables) and puts it on top of the **call stack**. When it returns, the frame disappears.

Step through. A new card appears for `square`, with its own `x`, then vanishes."""},
            {"type": "code", "visualize": True, "code": "def square(x):\n    return x * x\n\na = square(3)\nb = square(a)\nprint(b)"},
            {"type": "fill", "prompt": "Complete the function so that it gives back double the input.", "code": "def double(x):\n    {{a}} x * 2\n\nprint(double(4))",
             "blanks": {"a": ["return"]}, "explain": "`return` hands the result back to whoever called the function."},
            {"type": "predict", "prompt": "What is printed?", "code": "def add(a, b):\n    return a + b\n\nprint(add(2, 3) * 2)",
             "explain": "add(2, 3) gives 5, then 5 * 2 = 10."},
            {"type": "text", "md": """### Recursion: a function calling itself
`5! = 5 * 4 * 3 * 2 * 1`, and notice `5! = 5 * 4!`. A bigger problem is built from a smaller copy of itself. Every recursive function needs a **base case** (when to stop).

Watch the stack grow taller, then unwind as results return."""},
            {"type": "code", "visualize": True, "code": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n\nprint(factorial(4))"},
            {"type": "quiz", "prompt": "What would happen without the `if n <= 1` base case?",
             "options": ["It returns 0", "It never stops and crashes (stack overflow)", "It returns 1"], "answer": 1,
             "explain": "Without a stopping rule, the function keeps calling itself until Python runs out of stack space."},
        ],
    },
    # ---------------------------------------------------------------- LEVEL 4
    {
        "id": "lists", "level": 4, "title": "Lists: many values, one name", "minutes": 14,
        "concepts": ["lists", "arrays", "loops"],
        "blocks": [
            {"type": "text", "md": """## A row of numbered boxes
A **list** holds many values in order. Each box has an **index** starting at **0**.

```
nums = [4, 8, 15]
nums[0]  # 4
nums[2]  # 15
```

Lists + loops are the heart of most coding problems. The classic pattern: walk through the list and keep track of the best so far.

Watch the list drawn as cells, and `best` update."""},
            {"type": "code", "visualize": True, "code": "nums = [3, 9, 4, 12, 7]\nbest = nums[0]\nfor x in nums:\n    if x > best:\n        best = x\nprint(best)"},
            {"type": "trace_table", "prompt": "Each time line 4 is about to run, what are `x` and `best`?",
             "code": "nums = [3, 9, 4, 12, 7]\nbest = nums[0]\nfor x in nums:\n    if x > best:\n        best = x\nprint(best)", "line": 4, "vars": ["x", "best"],
             "explain": "best only changes when x beats it: 3, then 9, then still 9, then 12, then still 12."},
            {"type": "text", "md": """### Cost thinking (a first taste of Big-O)
That loop looks at each item once. Double the list, double the work. We call this **O(n)**, "grows in line with n". Later problems show how smarter ideas can beat this."""},
            {"type": "quiz", "prompt": "For nums = [10, 20, 30], what is nums[1]?", "options": ["10", "20", "30"], "answer": 1,
             "explain": "Indexes start at 0, so index 1 is the second value."},
        ],
    },
    {
        "id": "strings-and-dicts", "level": 4, "title": "Counting things with dictionaries", "minutes": 12,
        "concepts": ["dictionaries", "strings", "counting", "hashing"],
        "blocks": [
            {"type": "text", "md": """## A dictionary is a phone book
A **dictionary** (`dict`) stores **key → value** pairs. You look up by key, instantly, without scanning everything.

```
ages = {"Asha": 20, "Ravi": 25}
ages["Asha"]   # 20
```

The most useful pattern in all of DSA: **count things**. Walk through the items; for each one, add 1 to its counter.

Watch the dictionary fill up as the loop reads the word:"""},
            {"type": "code", "visualize": True, "code": 'word = "banana"\ncounts = {}\nfor ch in word:\n    if ch in counts:\n        counts[ch] = counts[ch] + 1\n    else:\n        counts[ch] = 1\nprint(counts)'},
            {"type": "predict", "prompt": "Using the same counting code, what does the last line print? (two values)",
             "code": 'word = "banana"\ncounts = {}\nfor ch in word:\n    if ch in counts:\n        counts[ch] = counts[ch] + 1\n    else:\n        counts[ch] = 1\nprint(counts["a"], len(counts))',
             "explain": "'a' appears 3 times, and there are 3 different letters (b, a, n): 3 3."},
            {"type": "quiz", "prompt": "Why is a dictionary great for 'have I seen this before?' questions?",
             "options": ["It sorts the data", "Lookup by key is instant, no scanning", "It uses less memory than a list"], "answer": 1,
             "explain": "Checking `x in my_dict` takes about the same time however big the dictionary is. You'll use this in Two Sum."},
        ],
    },
    # ---------------------------------------------------------------- LEVEL 5 (premium tier in business mode)
    {
        "id": "big-o", "level": 5, "title": "Big-O: how work grows", "minutes": 12, "premium": True,
        "concepts": ["big-o", "complexity"],
        "blocks": [
            {"type": "text", "md": """## Not "how fast", but "how does it grow?"
Computers differ in speed, so we count **steps** and ask: *when the input gets bigger, how much more work?*

- **O(1)**: same work no matter the size (grab `nums[0]`)
- **O(log n)**: halves the problem each step (binary search)
- **O(n)**: one pass (find the max)
- **O(n²)**: a loop inside a loop (compare every pair)

Run this and compare the two step counts. Change `n` in the playground and see how they grow."""},
            {"type": "code", "visualize": True, "code": 'n = 4\nsteps = 0\nfor i in range(n):\n    steps += 1\nprint("one loop:", steps)\nsteps = 0\nfor i in range(n):\n    for j in range(n):\n        steps += 1\nprint("nested:", steps)'},
            {"type": "predict", "prompt": "With n = 5, what does this print? (two lines)",
             "code": 'n = 5\nsteps = 0\nfor i in range(n):\n    steps += 1\nprint("one loop:", steps)\nsteps = 0\nfor i in range(n):\n    for j in range(n):\n        steps += 1\nprint("nested:", steps)',
             "explain": "One loop: 5. Nested: 5 × 5 = 25."},
            {"type": "quiz", "prompt": "Your O(n²) code takes 1 second for 1,000 items. Roughly how long for 2,000 items?",
             "options": ["2 seconds", "4 seconds", "1 second"], "answer": 1,
             "explain": "Doubling n makes n² four times bigger. That is why an O(n²) idea can be too slow when data grows."},
            {"type": "quiz", "prompt": "Binary search throws away half the list each step. Which growth is that?",
             "options": ["O(n)", "O(n²)", "O(log n)"], "answer": 2,
             "explain": "A million items need only about 20 halvings. That's the magic of O(log n)."},
        ],
    },
    {
        "id": "sorting", "level": 5, "title": "Sorting: bubble sort in motion", "minutes": 14, "premium": True,
        "concepts": ["sorting", "arrays", "nested-loops"],
        "blocks": [
            {"type": "text", "md": """## Swap neighbours until sorted
**Bubble sort**: walk along the list, compare neighbours, swap them if they are in the wrong order. Repeat. The biggest values "bubble" to the end.

Watch the pointer labels (**j**) move along the list cells, and see the list change when a swap happens. It is slow (two nested loops, O(n²)) but perfect for *seeing* sorting."""},
            {"type": "code", "visualize": True, "code": "nums = [5, 2, 4, 1]\nn = len(nums)\nfor i in range(n):\n    for j in range(n - 1 - i):\n        if nums[j] > nums[j + 1]:\n            temp = nums[j]\n            nums[j] = nums[j + 1]\n            nums[j + 1] = temp\nprint(nums)"},
            {"type": "trace_table", "prompt": "Each time line 5 (the comparison) is about to run, what are `i` and `j`?",
             "code": "nums = [5, 2, 4, 1]\nn = len(nums)\nfor i in range(n):\n    for j in range(n - 1 - i):\n        if nums[j] > nums[j + 1]:\n            temp = nums[j]\n            nums[j] = nums[j + 1]\n            nums[j + 1] = temp\nprint(nums)", "line": 5, "vars": ["i", "j"],
             "explain": "Each pass over the list gets one shorter, because the biggest value is already in place at the end."},
            {"type": "quiz", "prompt": "After the first full pass of bubble sort on [5, 2, 4, 1], where is the 5?",
             "options": ["Still at the start", "At the end", "In the middle"], "answer": 1,
             "explain": "The 5 keeps getting swapped past its neighbours until it reaches the end."},
        ],
    },
    {
        "id": "stacks", "level": 5, "title": "Stacks: last in, first out", "minutes": 10, "premium": True,
        "concepts": ["stack", "lists"],
        "blocks": [
            {"type": "text", "md": """## A stack of plates
You put plates on top (`append`) and take from the top (`pop`). The **last** plate in is the **first** one out.

Stacks power the *Undo* button, browser *Back*, matching brackets, and the very call stack you've been watching. Step through:"""},
            {"type": "code", "visualize": True, "code": 'stack = []\nstack.append("a")\nstack.append("b")\nstack.append("c")\ntop = stack.pop()\nprint(top, stack)'},
            {"type": "predict", "prompt": "What is printed at the end?", "code": "stack = []\nstack.append(1)\nstack.append(2)\nstack.append(3)\nstack.pop()\nstack.pop()\nprint(stack)",
             "explain": "Push 1, 2, 3. Two pops remove 3 then 2. Only [1] is left."},
            {"type": "quiz", "prompt": "To check that brackets like ( [ ] ) are balanced, which idea works?",
             "options": ["Push each opener, pop when you see a closer and check it matches", "Count the openers only", "Sort the characters"], "answer": 0,
             "explain": "The most recent opener must be closed first, which is exactly last-in-first-out. You'll solve Valid Parentheses with this."},
        ],
    },
]
