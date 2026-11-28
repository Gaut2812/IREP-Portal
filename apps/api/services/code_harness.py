"""Judge drivers for LeetCode-style ("function") problems, and starter stubs.

A function problem gives the student a class to fill in (`class Solution: def twoSum(...)`, or a design class like
`MinStack`). Test inputs are written the LeetCode way (`nums = [2,7,11,15], target = 9`, or one value per line).
Judge0 runs programs, so before a run the judge appends a driver that reads stdin, builds the arguments (linked
lists from `head`, trees from `root`, tree nodes for `p`/`q`), calls the method and prints the result as compact
JSON. Pass or fail is decided by `outputs_match`, which ignores JSON spacing.

The driver is plain Python and is only ever executed inside Judge0, never on this host (rule 10).
"""
import ast
import json
import re
from typing import List, Optional

DRIVER_MARK = "# ---- IREP judge driver (added when your code runs; not part of your solution) ----"

_PRELUDE = '''from typing import List, Optional, Dict, Tuple, Set


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

'''

_DRIVER = r'''
import sys as _irep_sys, json as _irep_json, ast as _irep_ast, inspect as _irep_inspect, re as _irep_re


def _irep_split(s):
    parts, depth, cur, quote, esc = [], 0, [], None, False
    for ch in s:
        if quote:
            cur.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _irep_value(t):
    t = t.strip()
    try:
        return _irep_json.loads(t)
    except Exception:
        pass
    try:
        return _irep_ast.literal_eval(t)
    except Exception:
        return t


def _irep_args(src):
    src = src.strip()
    if _irep_re.match(r"^[A-Za-z_]\w*\s*=", src):
        out = []
        for line in src.splitlines():
            for part in _irep_split(line):
                if "=" in part:
                    k, _, v = part.partition("=")
                    out.append((k.strip(), _irep_value(v)))
        return out
    return [(None, _irep_value(line)) for line in src.splitlines() if line.strip()]


def _irep_list(vals):
    head = cur = ListNode(0)
    for v in vals or []:
        cur.next = ListNode(v)
        cur = cur.next
    return head.next


def _irep_tree(vals):
    vals = list(vals or [])
    if not vals or vals[0] is None:
        return None
    root = TreeNode(vals[0])
    queue, i = [root], 1
    while queue and i < len(vals):
        node = queue.pop(0)
        if i < len(vals) and vals[i] is not None:
            node.left = TreeNode(vals[i])
            queue.append(node.left)
        i += 1
        if i < len(vals) and vals[i] is not None:
            node.right = TreeNode(vals[i])
            queue.append(node.right)
        i += 1
    return root


def _irep_find(root, val):
    queue = [root]
    while queue:
        node = queue.pop(0)
        if node is None:
            continue
        if node.val == val:
            return node
        queue += [node.left, node.right]
    return None


def _irep_plain(x):
    if isinstance(x, ListNode):
        out, seen = [], 0
        while x is not None and seen < 100000:
            out.append(x.val)
            x, seen = x.next, seen + 1
        return out
    if isinstance(x, TreeNode):
        return x.val
    if isinstance(x, (list, tuple)):
        return [_irep_plain(v) for v in x]
    return x


def _irep_print(x):
    x = _irep_plain(x)
    print(x if isinstance(x, str) else _irep_json.dumps(x, separators=(",", ":")))


def _irep_main():
    src = _irep_sys.stdin.read()
    g = globals()
    if "Solution" in g:
        cls = g["Solution"]
        name = next(n for n, v in vars(cls).items() if callable(v) and not n.startswith("_"))
        fn = getattr(cls(), name)
        params = list(_irep_inspect.signature(fn).parameters)
        args = _irep_args(src)
        named = {k: v for k, v in args if k}
        positional = [v for _, v in args]
        call, root, nodes = [], None, []
        for i, p in enumerate(params):
            v = named[p] if p in named else (positional[i] if i < len(positional) else None)
            if p in ("head", "l1", "l2", "list1", "list2") and isinstance(v, list):
                v = _irep_list(v)
                if p == "head":
                    n = v
                    while n is not None:
                        nodes.append(n)
                        n = n.next
            elif p == "root" and isinstance(v, list):
                v = _irep_tree(v)
                root = v
            call.append(v)
        if root is not None:
            call = [_irep_find(root, v) if p in ("p", "q") and not isinstance(v, TreeNode) else v for p, v in zip(params, call)]
        if name == "detectCycle":
            pos = named.get("pos", -1)
            if nodes and isinstance(pos, int) and 0 <= pos < len(nodes):
                nodes[-1].next = nodes[pos]
            got = fn(*call)
            idx = next((i for i, n in enumerate(nodes) if n is got), None) if got is not None else None
            print(f"tail connects to node index {idx}" if idx is not None else "no cycle")
            return
        _irep_print(fn(*call))
        return
    classes = [v for k, v in g.items() if isinstance(v, type) and v.__module__ == "__main__"
               and k not in ("ListNode", "TreeNode") and not k.startswith("_")]
    obj, outs = classes[-1](), []
    for op in _irep_value(src):
        m = _irep_re.match(r"^\s*(\w+)\s*\((.*)\)\s*$", op)
        name, argstr = (m.group(1), m.group(2)) if m else (op, "")
        r = getattr(obj, name)(*[_irep_value(a) for a in _irep_split(argstr)])
        if r is not None:
            outs.append(_irep_plain(r))
    _irep_print(outs)


_irep_main()
'''


def wrap_python(code: str) -> str:
    """The program Judge0 runs for a function problem: helper classes, the student's code, then the driver."""
    return f"{_PRELUDE}{code.rstrip()}\n\n\n{DRIVER_MARK}{_DRIVER}"


def make_stub(solution: str) -> str:
    """Starter code from a reference solution: imports, comments before the code, classes and method signatures,
    every body replaced by `pass`. Students never see the reference answer."""
    try:
        tree = ast.parse(solution)
    except SyntaxError:
        return solution
    lines = solution.splitlines()
    out: List[str] = []
    first = tree.body[0].lineno - 1 if tree.body else len(lines)
    out += [l for l in lines[:first] if l.strip().startswith("#")]

    def header(node: ast.AST, indent: str) -> List[str]:
        body_start = node.body[0].lineno - 1
        if isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
            body_start = node.body[0].end_lineno    # keep a docstring
        start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
        return [l for l in lines[start:body_start] if l.strip()]

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append(ast.get_source_segment(solution, node) or "")
        elif isinstance(node, ast.ClassDef):
            out.append("")
            out += header(node, "")
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for i, fn in enumerate(methods):
                if i:
                    out.append("")
                out += header(fn, "    ")
                indent = re.match(r"\s*", lines[fn.lineno - 1]).group(0) + "    "
                out.append(f"{indent}# Write your solution here")
                out.append(f"{indent}pass")
            if not methods:
                out.append("    pass")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append("")
            out += header(node, "")
            out.append("    pass")
    return "\n".join(out).strip("\n") + "\n"


STDIO_TEMPLATES = {
    "python": "import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n    # read your input from data, then print the answer\n    print(data)\n\n\nmain()\n",
    "java": ("import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n"
             "        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));\n"
             "        String line;\n        while ((line = in.readLine()) != null) {\n            // read your input, then print the answer\n"
             "            System.out.println(line);\n        }\n    }\n}\n"),
    "cpp": ("#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n"
            "    string line;\n    while (getline(cin, line)) {\n        // read your input, then print the answer\n        cout << line << \"\\n\";\n    }\n    return 0;\n}\n"),
    "javascript": ("const lines = require(\"fs\").readFileSync(0, \"utf8\").split(\"\\n\");\n\n"
                   "// read your input from lines, then print the answer\nfor (const line of lines) {\n  if (line.trim()) console.log(line);\n}\n"),
}


def _norm(text: Optional[str]):
    t = (text or "").strip()
    try:
        return ("json", json.loads(t))
    except Exception:
        return ("text", re.sub(r"\s+", " ", t))


def outputs_match(actual: Optional[str], expected: Optional[str]) -> bool:
    """Same answer: equal JSON values (spacing ignored), or the same text with runs of whitespace collapsed."""
    return _norm(actual) == _norm(expected)
