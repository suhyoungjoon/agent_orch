"""workflow_executor.py의 순수 함수 단위 테스트.

_topological_sort  — 노드/엣지 그래프를 위상 정렬
_build_context_from_edges — 엣지 매핑으로 이전 노드 결과를 context로 변환
"""
from app.services.workflow_executor import _topological_sort, _build_context_from_edges


# ════════════════════════════════════════════════════════════════════════
# _topological_sort
# ════════════════════════════════════════════════════════════════════════

class TestTopologicalSort:
    """위상 정렬 케이스."""

    def _nodes(self, *ids: str) -> list[dict]:
        return [{"id": i} for i in ids]

    def _edge(self, src: str, tgt: str) -> dict:
        return {"source": src, "target": tgt}

    def test_empty_graph_returns_empty(self):
        assert _topological_sort([], []) == []

    def test_single_node(self):
        assert _topological_sort(self._nodes("A"), []) == ["A"]

    def test_linear_chain(self):
        # A → B → C  순서 보장
        nodes = self._nodes("A", "B", "C")
        edges = [self._edge("A", "B"), self._edge("B", "C")]
        result = _topological_sort(nodes, edges)
        assert result.index("A") < result.index("B")
        assert result.index("B") < result.index("C")

    def test_diamond_shape(self):
        # A → B, A → C, B → D, C → D
        nodes = self._nodes("A", "B", "C", "D")
        edges = [
            self._edge("A", "B"),
            self._edge("A", "C"),
            self._edge("B", "D"),
            self._edge("C", "D"),
        ]
        result = _topological_sort(nodes, edges)
        assert result.index("A") < result.index("B")
        assert result.index("A") < result.index("C")
        assert result.index("B") < result.index("D")
        assert result.index("C") < result.index("D")

    def test_disconnected_nodes(self):
        # 연결 없는 독립 노드들도 모두 포함
        nodes = self._nodes("X", "Y", "Z")
        result = _topological_sort(nodes, [])
        assert set(result) == {"X", "Y", "Z"}

    def test_cycle_returns_all_nodes(self):
        # 사이클 A → B → A: 정렬 불가능 → 원래 node_ids 순서로 폴백
        nodes = self._nodes("A", "B")
        edges = [self._edge("A", "B"), self._edge("B", "A")]
        result = _topological_sort(nodes, edges)
        # 폴백이므로 모든 노드가 반환되어야 함
        assert set(result) == {"A", "B"}

    def test_unknown_edge_endpoints_ignored(self):
        # 존재하지 않는 노드를 참조하는 엣지는 무시
        nodes = self._nodes("A", "B")
        edges = [self._edge("A", "B"), self._edge("A", "GHOST")]
        result = _topological_sort(nodes, edges)
        assert result.index("A") < result.index("B")
        assert len(result) == 2

    def test_all_nodes_present_in_result(self):
        nodes = self._nodes("P", "Q", "R", "S")
        edges = [self._edge("P", "R"), self._edge("Q", "S")]
        result = _topological_sort(nodes, edges)
        assert set(result) == {"P", "Q", "R", "S"}


# ════════════════════════════════════════════════════════════════════════
# _build_context_from_edges
# ════════════════════════════════════════════════════════════════════════

class TestBuildContextFromEdges:
    """엣지 매핑 기반 context 구성 케이스."""

    def _edge(self, src: str, tgt: str, mapping: list | None = None) -> dict:
        data = {"mapping": mapping} if mapping is not None else {}
        return {"source": src, "target": tgt, "data": data}

    def test_no_incoming_edges_returns_empty(self):
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("X", "Y")],  # B와 무관한 엣지
            node_results={},
        )
        assert result == ""

    def test_no_mapping_uses_full_result(self):
        # 매핑 없음 → 이전 노드의 result 전체를 반환
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B")],
            node_results={
                "A": {"agent_name": "에이전트A", "result": "분석 결과입니다"}
            },
        )
        assert "에이전트A의 결과" in result
        assert "분석 결과입니다" in result

    def test_with_explicit_mapping(self):
        # 매핑 있음 → 지정된 필드만 추출
        mapping = [{"from": "result", "to": "input"}]
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B", mapping=mapping)],
            node_results={"A": {"result": "mapped content", "summary": "ignored"}},
        )
        assert "[input]" in result
        assert "mapped content" in result
        assert "ignored" not in result

    def test_mapping_with_missing_from_field(self):
        # from 필드 없으면 해당 매핑 항목은 건너뜀
        mapping = [{"from": "nonexistent_field", "to": "input"}]
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B", mapping=mapping)],
            node_results={"A": {"result": "hello"}},
        )
        # 비어있어야 함 (매핑이 있지만 from 필드가 없으므로)
        assert result == ""

    def test_multiple_incoming_edges(self):
        # 여러 incoming 엣지 → 모두 합쳐서 반환
        result = _build_context_from_edges(
            node_id="C",
            edges=[self._edge("A", "C"), self._edge("B", "C")],
            node_results={
                "A": {"agent_name": "에이전트A", "result": "A결과"},
                "B": {"agent_name": "에이전트B", "result": "B결과"},
            },
        )
        assert "A결과" in result
        assert "B결과" in result

    def test_source_with_empty_result_is_skipped(self):
        # result가 빈 문자열이면 해당 노드는 포함하지 않음
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B")],
            node_results={"A": {"agent_name": "에이전트A", "result": ""}},
        )
        assert result == ""

    def test_missing_source_in_node_results(self):
        # node_results에 없는 소스 → 빈 결과
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B")],
            node_results={},  # A 없음
        )
        assert result == ""

    def test_multiple_mapping_fields(self):
        # 여러 필드 매핑
        mapping = [
            {"from": "result",  "to": "main_output"},
            {"from": "summary", "to": "context"},
        ]
        result = _build_context_from_edges(
            node_id="B",
            edges=[self._edge("A", "B", mapping=mapping)],
            node_results={"A": {"result": "주요 결과", "summary": "요약"}},
        )
        assert "[main_output]" in result
        assert "주요 결과" in result
        assert "[context]" in result
        assert "요약" in result
