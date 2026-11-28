"""Coding Lab hints (screen 24): three hints per problem, chosen by the problem's topic.

Hint 1 is shown for free on the problem page; hints 2 and 3 are unlocked one at a time and counted.
Problems have no hint text of their own yet, so the hints follow the topic (pattern) the problem drills.
"""
from typing import List

TOPIC_HINTS = {
    "union-find": [
        "Think of this as a connectivity problem. Each edge connects two nodes. Can you maintain the count of disjoint components starting from n?",
        "Remember that if an edge connects two already connected nodes (same root), the component count does not decrease.",
        "Notice how path compression in find() flattens the tree. For best worst-case complexity, combine with union-by-rank.",
    ],
    "disjoint set": [
        "Process the edges in order and keep a disjoint-set structure of the nodes seen so far.",
        "An edge whose two ends already share a root closes a cycle: that edge is your candidate.",
        "Use path compression and union by rank so each find() is almost O(1).",
    ],
    "hash": [
        "For each element, what value would complete the pair? Can you look that value up in O(1)?",
        "Store each value you have already seen (with its index) in a hash map as you scan once.",
        "Check the map before inserting the current element, so an element is never paired with itself.",
    ],
    "two pointers": [
        "Sorting first often lets two pointers replace a nested loop.",
        "Start one pointer at each end and decide which one to move from how the current result compares to the target.",
        "Skip equal neighbours after a match to avoid duplicate answers.",
    ],
    "sliding window": [
        "Keep a window [left, right] that is always valid and grow it one step at a time.",
        "When the new element breaks the rule, move left forward until the window is valid again.",
        "A map from character to its last index lets you jump left directly instead of stepping.",
    ],
    "binary search": [
        "The input has an order you can exploit: can you discard half of the range at every step?",
        "Compare the middle element with an end of the range to tell which half is sorted (or which way is uphill).",
        "Be careful with the loop condition (lo < hi vs lo <= hi) and with how mid moves, so the loop always shrinks.",
    ],
    "dynamic programming": [
        "Define what dp[i] means in words first: the answer for the first i items, or for amount i.",
        "Write the recurrence: how does dp[i] follow from smaller sub-problems you have already solved?",
        "Fill the table in an order where every dependency is ready, then check whether you only need the last few values.",
    ],
    "stack": [
        "Process the input left to right and keep the items still waiting for their match on a stack.",
        "When the current item matches the top of the stack, pop it; otherwise push it.",
        "At the end, an empty stack (or the values left on it) gives the answer.",
    ],
    "monotonic stack": [
        "You need the next greater element for every position: a nested loop is O(n^2).",
        "Keep a stack of indices whose answer is still unknown, with temperatures decreasing from bottom to top.",
        "When a warmer day arrives, pop every colder index and fill in its answer as the distance between indices.",
    ],
    "prefix sum": [
        "The sum of a subarray is prefix[j] - prefix[i]. Can you count pairs with the difference you need?",
        "Keep a map from each prefix sum seen so far to how many times it occurred.",
        "Start the map with {0: 1} so subarrays that begin at index 0 are counted too.",
    ],
    "linked list": [
        "Draw three pointers on paper: previous, current and next.",
        "Save next before you change current.next, or you lose the rest of the list.",
        "When the loop ends, previous is the new head.",
    ],
    "fast & slow": [
        "Move one pointer one step and another two steps. If there is a cycle, they meet.",
        "After they meet, put one pointer back at the head.",
        "Move both one step at a time: where they meet again is where the cycle starts.",
    ],
    "tree": [
        "Solve it for one node, assuming the answers for its children are already known.",
        "The base case is an empty subtree (None).",
        "Combine the children's answers in one line, for example 1 + max(left, right).",
    ],
    "bst": [
        "Use the BST ordering: every value on the left is smaller and every value on the right is larger.",
        "If both target values are smaller than the current node, the answer is on the left (and the same for larger).",
        "The first node where the two targets split to different sides (or equal the node) is the answer.",
    ],
    "graph": [
        "Model the courses as a directed graph: an edge from a prerequisite to the course that needs it.",
        "Count the in-degree of every node and start from the nodes with in-degree 0.",
        "If you cannot visit all nodes this way (Kahn's algorithm), the graph has a cycle.",
    ],
    "design": [
        "Every operation must be O(1): what extra information do you need to keep at each level of the stack?",
        "Store, with each pushed value, the minimum of the stack at that moment.",
        "Pop removes both together, so the minimum of the remaining stack is always on top.",
    ],
}

GENERIC_HINTS = [
    "Restate the problem in your own words and work through the example by hand before you write code.",
    "Name the pattern this problem drills (two pointers, hashing, DP, graph search...) and write the brute force first.",
    "Find the repeated work in the brute force and remove it with the right data structure; then check the edge cases.",
]

# more specific topic names first ("Monotonic Stack" before "Stack", "Disjoint Set" before "Hash")
_ORDER = ["monotonic stack", "union-find", "disjoint set", "fast & slow", "bst", "design", "two pointers", "sliding window",
          "binary search", "dynamic programming", "prefix sum", "linked list", "graph", "tree", "hash", "stack"]


def hints_for(topic: str) -> List[str]:
    t = (topic or "").lower()
    for key in _ORDER:
        if key in t:
            return TOPIC_HINTS[key]
    return GENERIC_HINTS
