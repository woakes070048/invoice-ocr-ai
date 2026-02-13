from langgraph.graph import StateGraph, END
from .ocr_nodes import extract_invoice
from .validation import validate_invoice
from .confidence import calculate_confidence


def run_ocr_agent(ocr_text: str) -> dict:

    graph = StateGraph(dict)

    graph.add_node("extract", extract_invoice)

    graph.set_entry_point("extract")
    graph.add_edge("extract", END)

    agent = graph.compile()

    result = agent.invoke({
        "ocr_text": ocr_text
    })

    data = result["data"]
    validation = validate_invoice(data)
    confidence = calculate_confidence(data, validation)

    return {
        "data": data,
        "validation": validation,
        "confidence": confidence
    }
