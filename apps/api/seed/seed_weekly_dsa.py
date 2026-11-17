from typing import List, Dict, Any
from models.schema import CodingProblem, TestCase

WEEKLY_DSA_DATA: List[Dict[str, Any]] = [
    {
        "id": "prob_two_sum",
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "topic": "Arrays & Hash Map",
        "company_tags": "Amazon, Google",
        "week_info": "Week 1 · Foundation · 1 of 3",
        "statement": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.",
        "constraints": "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9",
        "starter_code": "class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        seen = {}\n        for i, num in enumerate(nums):\n            diff = target - num\n            if diff in seen:\n                return [seen[diff], i]\n            seen[num] = i\n        return []",
        "trainer_notes": "Use a hash map for single-pass O(n) lookup. Discuss why sorting with two pointers is O(n log n).",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_ts_01", "nums = [2,7,11,15], target = 9", "[0,1]", "nums[0] + nums[1] == 9"),
            ("tc_ts_02", "nums = [3,2,4], target = 6", "[1,2]", "nums[1] + nums[2] == 6")
        ]
    },
    {
        "id": "prob_container_water",
        "slug": "container-with-most-water",
        "title": "Container With Most Water",
        "difficulty": "Medium",
        "topic": "Two Pointers",
        "company_tags": "Meta, Amazon",
        "week_info": "Week 1 · Pattern drill · 2 of 3",
        "statement": "You are given an integer array height of length n. There are n vertical lines drawn such that the two endpoints of the ith line are (i, 0) and (i, height[i]).\n\nFind two lines that together with the x-axis form a container, such that the container contains the most water.",
        "constraints": "n == height.length\n2 <= n <= 10^5\n0 <= height[i] <= 10^4",
        "starter_code": "class Solution:\n    def maxArea(self, height: list[int]) -> int:\n        left, right = 0, len(height) - 1\n        max_water = 0\n        while left < right:\n            width = right - left\n            max_water = max(max_water, width * min(height[left], height[right]))\n            if height[left] < height[right]:\n                left += 1\n            else:\n                right -= 1\n        return max_water",
        "trainer_notes": "Move the pointer with the smaller height inward at each step to seek higher boundaries.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_cw_01", "height = [1,8,6,2,5,4,8,3,7]", "49", "Lines at index 1 and 8 enclose area 7 * 7 = 49."),
            ("tc_cw_02", "height = [1,1]", "1", "Width is 1, height is 1.")
        ]
    },
    {
        "id": "prob_3sum",
        "slug": "3sum",
        "title": "3Sum",
        "difficulty": "Medium",
        "topic": "Two Pointers",
        "company_tags": "Microsoft, Apple",
        "week_info": "Week 1 · Advanced drill · 3 of 3",
        "statement": "Given an integer array nums, return all the triplets [nums[i], nums[j], nums[k]] such that i != j, i != k, and j != k, and nums[i] + nums[j] + nums[k] == 0.\n\nNotice that the solution set must not contain duplicate triplets.",
        "constraints": "3 <= nums.length <= 3000\n-10^5 <= nums[i] <= 10^5",
        "starter_code": "class Solution:\n    def threeSum(self, nums: list[int]) -> list[list[int]]:\n        nums.sort()\n        res = []\n        for i in range(len(nums) - 2):\n            if i > 0 and nums[i] == nums[i-1]:\n                continue\n            l, r = i + 1, len(nums) - 1\n            while l < r:\n                s = nums[i] + nums[l] + nums[r]\n                if s < 0:\n                    l += 1\n                elif s > 0:\n                    r -= 1\n                else:\n                    res.append([nums[i], nums[l], nums[r]])\n                    while l < r and nums[l] == nums[l+1]: l += 1\n                    while l < r and nums[r] == nums[r-1]: r -= 1\n                    l += 1; r -= 1\n        return res",
        "trainer_notes": "Sort the array first to apply two pointers and easily skip consecutive duplicates.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_3s_01", "nums = [-1,0,1,2,-1,-4]", "[[-1,-1,2],[-1,0,1]]", "Unique triplets summing to zero."),
            ("tc_3s_02", "nums = [0,1,1]", "[]", "No valid triplets.")
        ]
    },
    {
        "id": "prob_longest_substring",
        "slug": "longest-substring-without-repeating-characters",
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "Medium",
        "topic": "Sliding Window",
        "company_tags": "Amazon, Bloomberg",
        "week_info": "Week 2 · Pattern drill · 1 of 2",
        "statement": "Given a string s, find the length of the longest substring without duplicate characters.",
        "constraints": "0 <= s.length <= 5 * 10^4\ns consists of English letters, digits, symbols and spaces.",
        "starter_code": "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:\n        char_map = {}\n        left = 0\n        max_len = 0\n        for right, ch in enumerate(s):\n            if ch in char_map and char_map[ch] >= left:\n                left = char_map[ch] + 1\n            char_map[ch] = right\n            max_len = max(max_len, right - left + 1)\n        return max_len",
        "trainer_notes": "Maintain window start with last seen character index map for O(n) time.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_ls_01", "s = \"abcabcbb\"", "3", "The answer is 'abc', with length 3."),
            ("tc_ls_02", "s = \"bbbbb\"", "1", "The answer is 'b', with length 1.")
        ]
    },
    {
        "id": "prob_subarray_sum_k",
        "slug": "subarray-sum-equals-k",
        "title": "Subarray Sum Equals K",
        "difficulty": "Medium",
        "topic": "Prefix Sum",
        "company_tags": "Meta, Google",
        "week_info": "Week 2 · Advanced drill · 2 of 2",
        "statement": "Given an array of integers nums and an integer k, return the total number of subarrays whose sum equals to k.\n\nA subarray is a contiguous non-empty sequence of elements within an array.",
        "constraints": "1 <= nums.length <= 2 * 10^4\n-1000 <= nums[i] <= 1000\n-10^7 <= k <= 10^7",
        "starter_code": "class Solution:\n    def subarraySum(self, nums: list[int], k: int) -> int:\n        prefix_counts = {0: 1}\n        curr_sum = 0\n        count = 0\n        for num in nums:\n            curr_sum += num\n            if (curr_sum - k) in prefix_counts:\n                count += prefix_counts[curr_sum - k]\n            prefix_counts[curr_sum] = prefix_counts.get(curr_sum, 0) + 1\n        return count",
        "trainer_notes": "Prefix sum + hash map pattern counts occurrences in single pass.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_ss_01", "nums = [1,1,1], k = 2", "2", "Subarrays [1,1] at index 0-1 and 1-2."),
            ("tc_ss_02", "nums = [1,2,3], k = 3", "2", "[1,2] and [3].")
        ]
    },
    {
        "id": "prob_valid_parentheses",
        "slug": "valid-parentheses",
        "title": "Valid Parentheses",
        "difficulty": "Easy",
        "topic": "Stack",
        "company_tags": "Amazon, Microsoft",
        "week_info": "Week 3 · Foundation · 1 of 3",
        "statement": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nOpen brackets must be closed by the same type of brackets in the correct order.",
        "constraints": "1 <= s.length <= 10^4\ns consists of parentheses only '()[]{}'.",
        "starter_code": "class Solution:\n    def isValid(self, s: str) -> bool:\n        stack = []\n        mapping = {')': '(', '}': '{', ']': '['}\n        for ch in s:\n            if ch in mapping:\n                top = stack.pop() if stack else '#'\n                if mapping[ch] != top: return False\n            else:\n                stack.append(ch)\n        return not stack",
        "trainer_notes": "LIFO stack property ensures inner brackets close before outer brackets.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_vp_01", "s = \"()[]{}\"", "true", "All brackets match properly."),
            ("tc_vp_02", "s = \"(]\"", "false", "Bracket type mismatch.")
        ]
    },
    {
        "id": "prob_daily_temperatures",
        "slug": "daily-temperatures",
        "title": "Daily Temperatures",
        "difficulty": "Medium",
        "topic": "Monotonic Stack",
        "company_tags": "Meta, Google",
        "week_info": "Week 3 · Pattern drill · 2 of 3",
        "statement": "Given an array of integers temperatures represents the daily temperatures, return an array answer such that answer[i] is the number of days you have to wait after the ith day to get a warmer temperature. If there is no future day for which this is possible, keep answer[i] == 0 instead.",
        "constraints": "1 <= temperatures.length <= 10^5\n30 <= temperatures[i] <= 100",
        "starter_code": "class Solution:\n    def dailyTemperatures(self, temperatures: list[int]) -> list[int]:\n        n = len(temperatures)\n        res = [0] * n\n        stack = [] # indices of decreasing temperatures\n        for i, temp in enumerate(temperatures):\n            while stack and temperatures[stack[-1]] < temp:\n                prev_idx = stack.pop()\n                res[prev_idx] = i - prev_idx\n            stack.append(i)\n        return res",
        "trainer_notes": "Monotonic decreasing stack resolves next greater element in O(n) total pushes and pops.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_dt_01", "temperatures = [73,74,75,71,69,72,76,73]", "[1,1,4,2,1,1,0,0]", "Days until warmer temperature."),
            ("tc_dt_02", "temperatures = [30,40,50,60]", "[1,1,1,0]", "Increasing sequence.")
        ]
    },
    {
        "id": "prob_min_stack",
        "slug": "min-stack",
        "title": "Min Stack",
        "difficulty": "Medium",
        "topic": "Design / Stack",
        "company_tags": "Bloomberg, Uber",
        "week_info": "Week 3 · Design drill · 3 of 3",
        "statement": "Design a stack that supports push, pop, top, and retrieving the minimum element in constant time.\n\nImplement the MinStack class:\n- MinStack() initializes the stack object.\n- void push(int val) pushes the element val onto the stack.\n- void pop() removes the element on the top of the stack.\n- int top() gets the top element of the stack.\n- int getMin() retrieves the minimum element in the stack.",
        "constraints": "-2^31 <= val <= 2^31 - 1\nMethods pop, top and getMin operations will always be called on non-empty stacks.\nAt most 3 * 10^4 calls will be made to push, pop, top, and getMin.",
        "starter_code": "class MinStack:\n    def __init__(self):\n        self.stack = []\n        self.min_stack = []\n\n    def push(self, val: int) -> None:\n        self.stack.append(val)\n        m = min(val, self.min_stack[-1] if self.min_stack else val)\n        self.min_stack.append(m)\n\n    def pop(self) -> None:\n        self.stack.pop()\n        self.min_stack.pop()\n\n    def top(self) -> int:\n        return self.stack[-1]\n\n    def getMin(self) -> int:\n        return self.min_stack[-1]",
        "trainer_notes": "Pair each pushed value with current minimum or use parallel min_stack for O(1) retrieval.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_ms_01", "[\"push(-2)\",\"push(0)\",\"push(-3)\",\"getMin()\",\"pop()\",\"top()\",\"getMin()\"]", "[-3,0,-2]", "Returns -3 min, top 0, then -2 min.")
        ]
    },
    {
        "id": "prob_reverse_linked_list",
        "slug": "reverse-linked-list",
        "title": "Reverse Linked List",
        "difficulty": "Easy",
        "topic": "Linked List",
        "company_tags": "Amazon, Apple",
        "week_info": "Week 4 · Foundation · 1 of 2",
        "statement": "Given the head of a singly linked list, reverse the list, and return the reversed list.",
        "constraints": "The number of nodes in the list is the range [0, 5000].\n-5000 <= Node.val <= 5000",
        "starter_code": "# Definition for singly-linked list.\n# class ListNode:\n#     def __init__(self, val=0, next=None):\n#         self.val = val\n#         self.next = next\nclass Solution:\n    def reverseList(self, head):\n        prev = None\n        curr = head\n        while curr:\n            nxt = curr.next\n            curr.next = prev\n            prev = curr\n            curr = nxt\n        return prev",
        "trainer_notes": "Iterative three-pointer approach (prev, curr, nxt) reverses pointers in O(1) space.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_rl_01", "head = [1,2,3,4,5]", "[5,4,3,2,1]", "Reversed order of elements."),
            ("tc_rl_02", "head = [1,2]", "[2,1]", "Two node list.")
        ]
    },
    {
        "id": "prob_linked_list_cycle",
        "slug": "linked-list-cycle-ii",
        "title": "Linked List Cycle II",
        "difficulty": "Medium",
        "topic": "Fast & Slow Pointers",
        "company_tags": "Microsoft, Amazon",
        "week_info": "Week 4 · Pattern drill · 2 of 2",
        "statement": "Given the head of a linked list, return the node where the cycle begins. If there is no cycle, return null.\n\nDo not modify the linked list.",
        "constraints": "The number of nodes in the list is in the range [0, 10^4].\n-10^5 <= Node.val <= 10^5",
        "starter_code": "class Solution:\n    def detectCycle(self, head):\n        slow = fast = head\n        while fast and fast.next:\n            slow = slow.next\n            fast = fast.next.next\n            if slow == fast:\n                entry = head\n                while entry != slow:\n                    entry = entry.next\n                    slow = slow.next\n                return entry\n        return None",
        "trainer_notes": "Floyd's cycle-finding algorithm: mathematical distance proves entry meets slow pointer.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_lc_01", "head = [3,2,0,-4], pos = 1", "tail connects to node index 1", "Cycle starts at index 1."),
            ("tc_lc_02", "head = [1], pos = -1", "no cycle", "Single node with no cycle.")
        ]
    },
    {
        "id": "prob_search_rotated",
        "slug": "search-in-rotated-sorted-array",
        "title": "Search in Rotated Sorted Array",
        "difficulty": "Medium",
        "topic": "Binary Search",
        "company_tags": "Meta, Google",
        "week_info": "Week 5 · Pattern drill · 1 of 2",
        "statement": "There is an integer array nums sorted in ascending order (with distinct values). Prior to being passed to your function, nums is possibly rotated at an unknown pivot index.\n\nGiven the array nums after the possible rotation and an integer target, return the index of target if it is in nums, or -1 if it is not in nums.\n\nYou must write an algorithm with O(log n) runtime complexity.",
        "constraints": "1 <= nums.length <= 5000\n-10^4 <= nums[i] <= 10^4\nAll values of nums are unique.\n-10^4 <= target <= 10^4",
        "starter_code": "class Solution:\n    def search(self, nums: list[int], target: int) -> int:\n        l, r = 0, len(nums) - 1\n        while l <= r:\n            mid = (l + r) // 2\n            if nums[mid] == target: return mid\n            # Left half sorted\n            if nums[l] <= nums[mid]:\n                if nums[l] <= target < nums[mid]:\n                    r = mid - 1\n                else:\n                    l = mid + 1\n            # Right half sorted\n            else:\n                if nums[mid] < target <= nums[r]:\n                    l = mid + 1\n                else:\n                    r = mid - 1\n        return -1",
        "trainer_notes": "Identify which half of the array is normally sorted; check if target lies within that range.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_sr_01", "nums = [4,5,6,7,0,1,2], target = 0", "4", "Index of element 0 is 4."),
            ("tc_sr_02", "nums = [4,5,6,7,0,1,2], target = 3", "-1", "Target not in array.")
        ]
    },
    {
        "id": "prob_find_peak_element",
        "slug": "find-peak-element",
        "title": "Find Peak Element",
        "difficulty": "Medium",
        "topic": "Binary Search",
        "company_tags": "Google, Amazon",
        "week_info": "Week 5 · Advanced drill · 2 of 2",
        "statement": "A peak element is an element that is strictly greater than its neighbors.\n\nGiven a 0-indexed integer array nums, find a peak element, and return its index. If the array contains multiple peaks, return the index to any of the peaks.\n\nYou must write an algorithm that runs in O(log n) time.",
        "constraints": "1 <= nums.length <= 1000\n-2^31 <= nums[i] <= 2^31 - 1\nnums[i] != nums[i + 1] for all valid i.",
        "starter_code": "class Solution:\n    def findPeakElement(self, nums: list[int]) -> int:\n        l, r = 0, len(nums) - 1\n        while l < r:\n            mid = (l + r) // 2\n            if nums[mid] > nums[mid + 1]:\n                r = mid\n            else:\n                l = mid + 1\n        return l",
        "trainer_notes": "Binary search on answers: climb the gradient toward the higher neighboring slope.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_fp_01", "nums = [1,2,3,1]", "2", "3 is a peak element and its index is 2."),
            ("tc_fp_02", "nums = [1,2,1,3,5,6,4]", "5", "Index 1 or 5 are valid peaks.")
        ]
    },
    {
        "id": "prob_max_depth_tree",
        "slug": "maximum-depth-of-binary-tree",
        "title": "Maximum Depth of Binary Tree",
        "difficulty": "Easy",
        "topic": "Tree / DFS",
        "company_tags": "Amazon, Microsoft",
        "week_info": "Week 6 · Foundation · 1 of 2",
        "statement": "Given the root of a binary tree, return its maximum depth.\n\nA binary tree's maximum depth is the number of nodes along the longest path from the root node down to the farthest leaf node.",
        "constraints": "The number of nodes in the tree is in the range [0, 10^4].\n-100 <= Node.val <= 100",
        "starter_code": "class Solution:\n    def maxDepth(self, root) -> int:\n        if not root:\n            return 0\n        return 1 + max(self.maxDepth(root.left), self.maxDepth(root.right))",
        "trainer_notes": "Post-order DFS traversal recursively calculates depth as 1 + max(left, right).",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_md_01", "root = [3,9,20,null,null,15,7]", "3", "Maximum depth is 3."),
            ("tc_md_02", "root = [1,null,2]", "2", "Depth is 2.")
        ]
    },
    {
        "id": "prob_lowest_common_ancestor",
        "slug": "lowest-common-ancestor-of-a-binary-search-tree",
        "title": "Lowest Common Ancestor of a BST",
        "difficulty": "Medium",
        "topic": "BST",
        "company_tags": "Amazon, Meta",
        "week_info": "Week 6 · Pattern drill · 2 of 2",
        "statement": "Given a binary search tree (BST), find the lowest common ancestor (LCA) node of two given nodes in the BST.\n\nAccording to the definition of LCA on Wikipedia: “The lowest common ancestor is defined between two nodes p and q as the lowest node in T that has both p and q as descendants (where we allow a node to be a descendant of itself).”",
        "constraints": "The number of nodes in the tree is in the range [2, 10^5].\n-10^9 <= Node.val <= 10^9\nAll Node.val are unique.\np != q and both p and q will exist in the BST.",
        "starter_code": "class Solution:\n    def lowestCommonAncestor(self, root, p, q):\n        curr = root\n        while curr:\n            if p.val > curr.val and q.val > curr.val:\n                curr = curr.right\n            elif p.val < curr.val and q.val < curr.val:\n                curr = curr.left\n            else:\n                return curr",
        "trainer_notes": "Utilize BST ordering property: split point where p and q diverge is the LCA.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_lca_01", "root = [6,2,8,0,4,7,9,null,null,3,5], p = 2, q = 8", "6", "LCA of 2 and 8 is 6."),
            ("tc_lca_02", "root = [6,2,8,0,4,7,9,null,null,3,5], p = 2, q = 4", "2", "LCA of 2 and 4 is 2.")
        ]
    },
    {
        "id": "prob_climbing_stairs",
        "slug": "climbing-stairs",
        "title": "Climbing Stairs",
        "difficulty": "Easy",
        "topic": "Dynamic Programming",
        "company_tags": "Google, Amazon",
        "week_info": "Week 7 · Foundation · 1 of 3",
        "statement": "You are climbing a staircase. It takes n steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?",
        "constraints": "1 <= n <= 45",
        "starter_code": "class Solution:\n    def climbStairs(self, n: int) -> int:\n        if n <= 2: return n\n        a, b = 1, 2\n        for _ in range(3, n + 1):\n            a, b = b, a + b\n        return b",
        "trainer_notes": "Fibonacci recurrence relation dp[i] = dp[i-1] + dp[i-2] with O(1) space optimization.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_cs_01", "n = 2", "2", "1+1 or 2 steps."),
            ("tc_cs_02", "n = 3", "3", "1+1+1, 1+2, or 2+1 steps.")
        ]
    },
    {
        "id": "prob_coin_change",
        "slug": "coin-change",
        "title": "Coin Change",
        "difficulty": "Medium",
        "topic": "Dynamic Programming",
        "company_tags": "Amazon, Microsoft",
        "week_info": "Week 7 · Pattern drill · 2 of 3",
        "statement": "You are given an integer array coins representing coins of different denominations and an integer amount representing a total amount of money.\n\nReturn the fewest number of coins that you need to make up that amount. If that amount of money cannot be made up by any combination of the coins, return -1.",
        "constraints": "1 <= coins.length <= 12\n1 <= coins[i] <= 2^31 - 1\n0 <= amount <= 10^4",
        "starter_code": "class Solution:\n    def coinChange(self, coins: list[int], amount: int) -> int:\n        dp = [float('inf')] * (amount + 1)\n        dp[0] = 0\n        for coin in coins:\n            for x in range(coin, amount + 1):\n                dp[x] = min(dp[x], dp[x - coin] + 1)\n        return dp[amount] if dp[amount] != float('inf') else -1",
        "trainer_notes": "Unbounded knapsack pattern: bottom-up DP computing minimum transitions for each sub-amount.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_cc_01", "coins = [1,2,5], amount = 11", "3", "11 = 5 + 5 + 1."),
            ("tc_cc_02", "coins = [2], amount = 3", "-1", "Cannot make 3 with only 2s.")
        ]
    },
    {
        "id": "prob_longest_increasing_subsequence",
        "slug": "longest-increasing-subsequence",
        "title": "Longest Increasing Subsequence",
        "difficulty": "Medium",
        "topic": "Dynamic Programming",
        "company_tags": "Google, Meta",
        "week_info": "Week 7 · Advanced drill · 3 of 3",
        "statement": "Given an integer array nums, return the length of the longest strictly increasing subsequence.\n\nA subsequence is an array that can be derived from another array by deleting some or no elements without changing the order of the remaining elements.",
        "constraints": "1 <= nums.length <= 2500\n-10^4 <= nums[i] <= 10^4",
        "starter_code": "import bisect\nclass Solution:\n    def lengthOfLIS(self, nums: list[int]) -> int:\n        tails = []\n        for x in nums:\n            idx = bisect.bisect_left(tails, x)\n            if idx == len(tails):\n                tails.append(x)\n            else:\n                tails[idx] = x\n        return len(tails)",
        "trainer_notes": "Patience sorting / binary search achieves O(n log n) time over classic O(n^2) DP.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_lis_01", "nums = [10,9,2,5,3,7,101,18]", "4", "Longest increasing subsequence is [2,3,7,101]."),
            ("tc_lis_02", "nums = [0,1,0,3,2,3]", "4", "[0,1,2,3].")
        ]
    },
    {
        "id": "prob_redundant_connection",
        "slug": "redundant-connection",
        "title": "Redundant Connection",
        "difficulty": "Medium",
        "topic": "Disjoint Set Union",
        "company_tags": "Amazon, Google",
        "week_info": "Week 8 · Pattern drill · 4 of 6",
        "statement": "In this problem, a tree is an undirected graph that is connected and has no cycles.\n\nYou are given a graph that started as a tree with n nodes labeled from 1 to n, with one additional edge added. Return an edge that can be removed so that the resulting graph is a tree of n nodes.",
        "constraints": "n == edges.length\n3 <= n <= 1000\nedges[i].length == 2\n1 <= ai < bi <= edges.length",
        "starter_code": "class Solution:\n    def findRedundantConnection(self, edges: list[list[int]]) -> list[int]:\n        parent = list(range(len(edges) + 1))\n        def find(x):\n            if parent[x] != x:\n                parent[x] = find(parent[x])\n            return parent[x]\n        for u, v in edges:\n            ru, rv = find(u), find(v)\n            if ru == rv:\n                return [u, v]\n            parent[ru] = rv\n        return []",
        "trainer_notes": "Cycle detection with Union-Find: the edge whose vertices already share the same root is the redundant edge.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_rc_01", "edges = [[1,2],[1,3],[2,3]]", "[2,3]", "[2,3] creates a cycle."),
            ("tc_rc_02", "edges = [[1,2],[2,3],[3,4],[1,4],[1,5]]", "[1,4]", "[1,4] creates the redundant cycle.")
        ]
    },
    {
        "id": "prob_course_schedule",
        "slug": "course-schedule",
        "title": "Course Schedule",
        "difficulty": "Medium",
        "topic": "Graph / Topological Sort",
        "company_tags": "Amazon, Microsoft, Meta",
        "week_info": "Week 8 · Advanced drill · 5 of 6",
        "statement": "There are a total of numCourses courses you have to take, labeled from 0 to numCourses - 1. You are given an array prerequisites where prerequisites[i] = [ai, bi] indicates that you must take course bi first if you want to take course ai.\n\nReturn true if you can finish all courses. Otherwise, return false.",
        "constraints": "1 <= numCourses <= 2000\n0 <= prerequisites.length <= 5000\nprerequisites[i].length == 2\n0 <= ai, bi < numCourses\nAll the pairs prerequisites[i] are unique.",
        "starter_code": "from collections import deque\nclass Solution:\n    def canFinish(self, numCourses: int, prerequisites: list[list[int]]) -> bool:\n        adj = [[] for _ in range(numCourses)]\n        indegree = [0] * numCourses\n        for dest, src in prerequisites:\n            adj[src].append(dest)\n            indegree[dest] += 1\n        q = deque([i for i in range(numCourses) if indegree[i] == 0])\n        taken = 0\n        while q:\n            node = q.popleft()\n            taken += 1\n            for neighbor in adj[node]:\n                indegree[neighbor] -= 1\n                if indegree[neighbor] == 0:\n                    q.append(neighbor)\n        return taken == numCourses",
        "trainer_notes": "Kahn's algorithm for topological sorting: detect directed cycles by comparing processed nodes count.",
        "trainer_author": "Arun K.",
        "sample_cases": [
            ("tc_cs_01", "numCourses = 2, prerequisites = [[1,0]]", "true", "Take 0 then 1."),
            ("tc_cs_02", "numCourses = 2, prerequisites = [[1,0],[0,1]]", "false", "Cyclic dependency.")
        ]
    }
]

def seed_weekly_problems(db, college_id="col_demo_001"):
    """Seeds the 19 weekly problems if not already present."""
    from sqlalchemy import select
    seeded_count = 0
    for p_data in WEEKLY_DSA_DATA:
        existing = db.execute(select(CodingProblem).filter_by(id=p_data["id"], college_id=college_id)).scalar_one_or_none()
        if not existing:
            first_in = p_data["sample_cases"][0][1] if p_data.get("sample_cases") else "N/A"
            first_out = p_data["sample_cases"][0][2] if p_data.get("sample_cases") else "N/A"
            p = CodingProblem(
                id=p_data["id"],
                college_id=college_id,
                slug=p_data["slug"],
                title=p_data["title"],
                difficulty=p_data["difficulty"],
                topic=p_data["topic"],
                company_tags=p_data["company_tags"],
                week_info=p_data["week_info"],
                statement=p_data["statement"],
                example_input=first_in,
                example_output=first_out,
                constraints=p_data["constraints"],
                time_limit_ms=2000,
                memory_limit_mb=256,
                starter_code=p_data["starter_code"],
                starter_codes={"python": p_data["starter_code"]},
                trainer_notes=p_data["trainer_notes"],
                trainer_author=p_data["trainer_author"]
            )
            db.add(p)
            db.flush()
            
            for idx, (tc_id, in_d, exp_o, expl) in enumerate(p_data["sample_cases"], 1):
                tc = TestCase(
                    id=f"{p_data['id']}_{tc_id}",
                    college_id=college_id,
                    problem_id=p.id,
                    test_order=idx,
                    is_hidden=False,
                    name=f"Sample Case {idx}",
                    input_data=in_d,
                    expected_output=exp_o,
                    explanation=expl
                )
                db.add(tc)
            seeded_count += 1
            
    db.commit()
    return seeded_count

