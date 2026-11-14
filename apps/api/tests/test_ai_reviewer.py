"""Unit tests for AI Code Review Engine — Phase 4.

Tests:
  - DSU with path compression + rank -> O(E · alpha(V)) complexity
  - DSU with path compression only -> O(E log V) complexity  
  - DSU with no optimizations -> warns about O(V) skew
  - BFS/DFS code -> identifies graph traversal
  - Empty code -> handles gracefully (no crash)
  - Python AST syntax error -> code_smells populated
  - Benchmark: deterministic path < 100ms
  - Hidden-test data NOT in review output (zero leakage)
  - Java code -> no crash
  - C++ code -> no crash
  - JavaScript code -> no crash
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest
from services.ai_reviewer_service import AICodeReviewEngine

engine = AICodeReviewEngine()

OPTIMAL_DSU_PYTHON = """
class Solution:
    def countComponents(self, n: int, edges):
        parent = list(range(n))
        rank = [0] * n
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        def union(x, y):
            rx, ry = find(x), find(y)
            if rx == ry:
                return 0
            if rank[rx] < rank[ry]:
                rx, ry = ry, rx
            parent[ry] = rx
            if rank[rx] == rank[ry]:
                rank[rx] += 1
            return 1
        return n - sum(union(u, v) for u, v in edges)
"""

PATH_COMPRESSION_ONLY_PYTHON = """
def find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]
def union(x, y):
    rx, ry = find(x), find(y)
    if rx != ry:
        parent[rx] = ry
        return 1
    return 0
parent = list(range(10))
"""

BASIC_DSU_NO_OPT = """
def find(x):
    while parent[x] != x:
        x = parent[x]
    return x
def union(x, y):
    parent[find(x)] = find(y)
parent = list(range(10))
"""

BFS_CODE = """
from collections import deque
def bfs(graph, start):
    visited = set([start])
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited
"""

DFS_CODE = """
def dfs(node, visited, graph):
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs(neighbor, visited, graph)
"""

JAVA_CODE = """
class Solution {
    int[] parent;
    int[] rank;
    public int countComponents(int n, int[][] edges) {
        parent = new int[n];
        rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int components = n;
        for (int[] e : edges) components -= union(e[0], e[1]);
        return components;
    }
    int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    int union(int x, int y) {
        int rx = find(x), ry = find(y);
        if (rx == ry) return 0;
        if (rank[rx] < rank[ry]) { int t = rx; rx = ry; ry = t; }
        parent[ry] = rx;
        if (rank[rx] == rank[ry]) rank[rx]++;
        return 1;
    }
}
"""

CPP_CODE = """
class Solution {
public:
    vector<int> parent, rank_;
    int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    bool union_(int x, int y) {
        int rx = find(x), ry = find(y);
        if (rx == ry) return false;
        if (rank_[rx] < rank_[ry]) swap(rx, ry);
        parent[ry] = rx;
        if (rank_[rx] == rank_[ry]) rank_[rx]++;
        return true;
    }
    int countComponents(int n, vector<vector<int>>& edges) {
        parent.resize(n); rank_.resize(n, 0);
        iota(parent.begin(), parent.end(), 0);
        int comp = n;
        for (auto& e : edges) comp -= union_(e[0], e[1]);
        return comp;
    }
};
"""

JS_CODE = """
var countComponents = function(n, edges) {
    const parent = Array.from({length: n}, (_, i) => i);
    const rank = new Array(n).fill(0);
    function find(x) {
        if (parent[x] !== x) parent[x] = find(parent[x]);
        return parent[x];
    }
    function union(x, y) {
        const rx = find(x), ry = find(y);
        if (rx === ry) return 0;
        if (rank[rx] < rank[ry]) { [rx, ry] = [ry, rx]; }
        parent[ry] = rx;
        if (rank[rx] === rank[ry]) rank[rx]++;
        return 1;
    }
    return n - edges.reduce((acc, [u, v]) => acc + union(u, v), 0);
};
"""

SYNTAX_ERROR_PYTHON = """
def find(x
    return x
"""

# --- Tests ---

def test_dsu_with_path_compression_and_rank():
    result = engine.analyze_code(OPTIMAL_DSU_PYTHON, "python")
    assert "α" in result["time_complexity"] or "alpha" in result["time_complexity"].lower() or "E" in result["time_complexity"]
    assert "DSU" in " ".join(result["detected_patterns"]) or "Union" in " ".join(result["detected_patterns"])
    assert any("rank" in p.lower() or "compression" in p.lower() for p in result["good_practices"])


def test_dsu_path_compression_only():
    result = engine.analyze_code(PATH_COMPRESSION_ONLY_PYTHON, "python")
    assert "Union" in " ".join(result["detected_patterns"]) or "DSU" in " ".join(result["detected_patterns"])
    assert any("compression" in p.lower() for p in result["good_practices"])
    assert "rank" in result["try_next"].lower() or "union" in result["try_next"].lower()


def test_dsu_no_optimizations_warns_about_skew():
    result = engine.analyze_code(BASIC_DSU_NO_OPT, "python")
    assert "Union" in " ".join(result["detected_patterns"]) or "DSU" in " ".join(result["detected_patterns"])
    has_skew_warning = (
        any("compres" in s.lower() or "skew" in s.lower() or "linear" in s.lower() for s in result["code_smells"])
        or "V" in result["time_complexity"]
    )
    assert has_skew_warning, f"Expected skew warning. Got code_smells={result['code_smells']}, time={result['time_complexity']}"


def test_bfs_code_identifies_graph_traversal():
    result = engine.analyze_code(BFS_CODE, "python")
    assert any("BFS" in p or "Graph" in p or "Traversal" in p for p in result["detected_patterns"])


def test_dfs_code_identifies_graph_traversal():
    result = engine.analyze_code(DFS_CODE, "python")
    assert any("DFS" in p or "Graph" in p or "Traversal" in p for p in result["detected_patterns"])


def test_empty_code_no_crash():
    result = engine.analyze_code("", "python")
    assert isinstance(result, dict)
    assert "overall_evaluation" in result
    assert "time_complexity" in result
    assert "good_practices" in result


def test_python_syntax_error_populates_code_smells():
    result = engine.analyze_code(SYNTAX_ERROR_PYTHON, "python")
    assert isinstance(result, dict)
    has_syntax_note = any("syntax" in s.lower() or "line" in s.lower() for s in result.get("code_smells", []))
    assert has_syntax_note, f"Expected syntax error in code_smells. Got: {result.get('code_smells')}"


def test_benchmark_deterministic_under_100ms():
    """Deterministic analysis must complete in under 100ms."""
    start = time.perf_counter()
    result = engine.analyze_code(OPTIMAL_DSU_PYTHON, "python")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 100, f"Deterministic engine took {elapsed_ms:.1f}ms (must be < 100ms)"
    assert result.get("analysis_duration_ms", 999) < 100


def test_no_hidden_test_leakage_in_review():
    """Review output must not contain hidden test data."""
    result = engine.analyze_code(OPTIMAL_DSU_PYTHON, "python")
    result_str = str(result)
    forbidden_keywords = ["hidden_input", "hidden_expected", "test_input_secret", "reference_solution"]
    for kw in forbidden_keywords:
        assert kw not in result_str, f"Hidden test keyword '{kw}' found in review output!"


def test_java_code_no_crash():
    result = engine.analyze_code(JAVA_CODE, "java")
    assert isinstance(result, dict)
    assert "time_complexity" in result


def test_cpp_code_no_crash():
    result = engine.analyze_code(CPP_CODE, "cpp")
    assert isinstance(result, dict)
    assert "time_complexity" in result


def test_javascript_code_no_crash():
    result = engine.analyze_code(JS_CODE, "javascript")
    assert isinstance(result, dict)
    assert "time_complexity" in result
