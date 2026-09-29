from __future__ import annotations
import csv,json
from pathlib import Path

from PIL import Image,ImageDraw

from .leakage import check_leakage


def write_artifacts(records: list[dict], split_records: list[dict], out_dir: str | Path, *, metrics: dict | None = None, limitations: list[str] | None = None, source_roles: dict[str,str] | None = None) -> dict:
    """Always writes observed manifests/leakage. Writes metric artifacts only when caller supplies metrics."""
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    leakage=check_leakage(split_records); (out/"leakage_report.json").write_text(json.dumps(leakage,indent=2))
    def csv_rows(name,rows):
        fields=list(dict.fromkeys(k for row in rows for k in row.keys()))
        with (out/name).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=fields or ["status"]); writer.writeheader()
            for row in rows: writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    csv_rows("dataset_manifest.csv",records); csv_rows("split_manifest.csv",split_records)
    if metrics is not None:
        (out/"metrics.json").write_text(json.dumps(metrics,indent=2))
        with (out/"metrics.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["metric","value"]); w.writerow(["mAP@0.5",metrics.get("mAP@0.5")]); w.writerow(["ground_truth_count",metrics.get("ground_truth_count")]); w.writerow(["prediction_count",metrics.get("prediction_count")])
        with (out/"per_class_metrics.csv").open("w",newline="",encoding="utf-8") as f:
            classes=metrics.get("per_class",{}); fields=["class","support","true_positives","false_positives","precision","recall","f1","ap50"]
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            for name,row in classes.items(): w.writerow({"class":name,**row})
        _confusion_png(metrics.get("confusion_matrix",[]),metrics.get("confusion_matrix_labels",[]),out/"confusion_matrix.png")
    else:
        (out/"metrics_status.json").write_text(json.dumps({"status":"NOT_COMPUTED","reason":"No real detector predictions and labeled evaluation records were supplied."},indent=2))
    report=["# Generalization and evaluation report","","## Detector metrics","",("Metrics were computed from explicitly supplied evaluation records." if metrics is not None else "Not available with current metadata and detector state; no project performance metrics were generated.")]
    if metrics is not None:
        report += ["",f"- mAP@0.5: {metrics.get('mAP@0.5')}",f"- Precision: {metrics.get('precision')}",f"- Recall: {metrics.get('recall')}","","### Per class",""]
        for name,row in metrics.get("per_class",{}).items(): report.append(f"- {name}: support {row.get('support')}, precision {row.get('precision')}, recall {row.get('recall')}, AP50 {row.get('ap50')}")
        report += ["","### Per dataset",""]
        if metrics.get("per_dataset"):
            for name,row in metrics["per_dataset"].items(): report.append(f"- {name}: precision {row.get('precision')}, recall {row.get('recall')}, F1 {row.get('f1')}")
        else: report.append("Not available with current metadata")
    report += ["","## Grouping strategy","", "Not available with current metadata" if not split_records else str(split_records[0].get("split_group_key","Not available with current metadata")),"","## Leakage check","",leakage["status"],"","## Seen-source vs held-out-source",""]
    roles=source_roles or {}
    if roles:
        for source,role in sorted(roles.items()):
            metric=metrics.get("per_dataset",{}).get(source) if metrics else None
            report.append(f"- {source} ({role}): {metric if metric is not None else 'Not available with current metadata'}")
    else: report.append("Not available with current metadata")
    report += ["","## Limitations",""]
    report += [f"- {item}" for item in (limitations or ["Engine 4 detector and validated predictions are pending.","No acquisition identifiers are inferred."])]
    (out/"generalization_report.md").write_text("\n".join(report)+"\n")
    return {"output_dir":str(out),"metrics_written":metrics is not None,"leakage":leakage}


def _confusion_png(matrix, labels, path):
    n=len(matrix); cell=70; margin=130; im=Image.new("RGB",(margin+n*cell+20,margin+n*cell+20),"white"); d=ImageDraw.Draw(im)
    maximum=max((max(row,default=0) for row in matrix),default=0)
    for i,row in enumerate(matrix):
        for j,value in enumerate(row):
            shade=255-int(180*value/maximum) if maximum else 255; x,y=margin+j*cell,margin+i*cell
            d.rectangle((x,y,x+cell-1,y+cell-1),fill=(shade,shade,255),outline="#777"); d.text((x+cell//2-5,y+cell//2-6),str(value),fill="#111")
    for i,label in enumerate(labels):
        d.text((5,margin+i*cell+cell//2-5),str(label)[:16],fill="#111"); d.text((margin+i*cell+3,margin-18),str(label)[:12],fill="#111")
    path.parent.mkdir(parents=True,exist_ok=True); im.save(path)
