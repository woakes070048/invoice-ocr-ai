"""
OCR Agent
Cloud-safe LangGraph runner
NO dependency on ai/ocr_engine
"""

from langgraph.graph import StateGraph, END

from invoice_ocr.ai.ocr_nodes import (
    extract_header,
    extract_items,
    extract_taxes,
    score_confidence,
)


def run_ocr_agent(ocr_text: str) -> dict:
    """
    Execute LangGraph OCR pipeline
    """

    graph = StateGraph(dict)

    graph.add_node("header", extract_header)
    graph.add_node("items", extract_items)
    graph.add_node("taxes", extract_taxes)
    graph.add_node("confidence", score_confidence)

    graph.set_entry_point("header")

    graph.add_edge("header", "items")
    graph.add_edge("items", "taxes")
    graph.add_edge("taxes", "confidence")
    graph.add_edge("confidence", END)

    agent = graph.compile()

    return agent.invoke({
        "ocr_text": ocr_text,
        "header": {},
        "items": [],
        "taxes": [],
        "confidence": 0
    })
