from __future__ import annotations


def inspection_priority(evidence: dict, config: dict) -> dict:
    weights=config["inspection_priority"]["weights"]
    present={key:min(1.0,max(0.0,float(evidence[key]))) for key in weights if evidence.get(key) is not None}
    total=sum(weights[key] for key in present)
    score=sum(present[key]*weights[key] for key in present)/total if total else None
    bands=config["inspection_priority"]["bands"]
    band="unavailable" if score is None else "high" if score>=bands["high"] else "medium" if score>=bands["medium"] else "low"
    return {"label":"Inspection Priority","score":score,"band":band,"fields_used":list(present),"note":config["inspection_priority"]["note"]}
